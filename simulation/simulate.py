"""Standalone simulation of a client using the e-commerce API over real HTTP.

This script lives outside the app and outside the containers: it only talks
to the API (``API_URL``, default http://localhost:8000). Start the stack with
``docker compose up --build`` and then run:

    python simulation/simulate.py

Flow:

1. Register a new customer through ``POST /api/v1/auth/register``.
2. (Optional) If a Mailpit URL is provided via ``--mailpit-url`` /
   ``MAILPIT_URL``, poll it for the verification email and "click" the link
   like a real user would. Without it, verification is skipped — the API does
   not require a verified email to log in or place orders.
3. Log in, create a shipping address.
4. Browse the catalog, add two variants to the cart, create an order.
5. Pay: create a Stripe payment intent through ``POST /api/v1/payments/intent``
   and confirm it by sending a signed ``payment_intent.succeeded`` webhook to
   ``POST /api/v1/payments/webhook`` (exactly what ``stripe trigger`` would
   do). This requires Stripe to be reachable (real keys, or the optional
   ``stripe-mock`` service with ``STRIPE_API_BASE``) and ``STRIPE_WEBHOOK_SECRET``
   to sign the event. If payment is not available, the seeded admin marks the
   order as paid instead.
6. The seeded admin moves the order through processing -> shipped ->
   delivered via the admin endpoints.

Configuration (environment variables, .env, or CLI flags):
API_URL, ADMIN_EMAIL, ADMIN_PASSWORD, MAILPIT_URL (optional),
STRIPE_WEBHOOK_SECRET (optional, enables the real payment flow).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import random
import re
import sys
import time
import uuid
from pathlib import Path

import httpx

# fmt: off
_STREETS = [
    "123 Main St", "456 Oak Avenue", "789 Pine Road", "101 Maple Blvd",
    "202 Elm Street", "303 Cedar Lane", "404 Birch Way", "505 Spruce Drive",
]

_CITIES = [
    ("Springfield", "IL", "62701"), ("Austin", "TX", "73301"),
    ("Denver", "CO", "80201"), ("Seattle", "WA", "98101"),
    ("Boston", "MA", "02101"), ("Miami", "FL", "33101"),
]
# fmt: on

VERIFY_SUBJECT = "Verify your email"


def _load_dotenv(path: str = ".env") -> dict[str, str]:
    """Read simple KEY=VALUE pairs from a .env file (no export of values)."""
    env_path = Path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_DOTENV = _load_dotenv()


def _setting(name: str, default: str | None = None) -> str | None:
    """Environment variable wins, then .env, then the default."""
    return os.environ.get(name) or _DOTENV.get(name) or default


class ApiClient:
    """Thin httpx wrapper that raises with the response body on errors."""

    def __init__(self, base_url: str, token: str | None = None) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=30.0)

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
        return response

    def get_json(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs).json()

    def post_json(self, path: str, payload: dict, **kwargs):
        return self.request("POST", path, json=payload, **kwargs).json()

    def patch_json(self, path: str, payload: dict, **kwargs):
        return self.request("PATCH", path, json=payload, **kwargs).json()


def wait_for_api(api: ApiClient, timeout: float = 180.0) -> None:
    """Wait until the API finishes migrations/seed and serves requests."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            api.get_json("/api/v1/products/categories")
            return
        except (httpx.TransportError, RuntimeError):
            time.sleep(3)
    raise TimeoutError("API did not become ready in time")


def wait_for_verification_token(mailpit_url: str, email: str, timeout: float = 90.0) -> str:
    """Poll Mailpit until the verification email for ``email`` arrives."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            search = httpx.get(
                f"{mailpit_url}/api/v1/search",
                params={"query": f"to:{email}"},
                timeout=10.0,
            )
            search.raise_for_status()
            for message in search.json().get("messages", []):
                if message.get("Subject") != VERIFY_SUBJECT:
                    continue
                full = httpx.get(f"{mailpit_url}/api/v1/message/{message['ID']}", timeout=10.0)
                full.raise_for_status()
                html = full.json().get("HTML") or ""
                match = re.search(r"verify-email\?token=([^\"'\s<>]+)", html)
                if match:
                    return match.group(1)
        except httpx.TransportError:
            pass  # Mailpit may not be up yet
        time.sleep(2)
    raise TimeoutError(f"Verification email for {email} never arrived in Mailpit")


def pick_variants(api: ApiClient, count: int = 2) -> list[dict]:
    """Pick ``count`` in-stock variants from the public catalog."""
    items = api.get_json("/api/v1/products", params={"limit": 20})["items"]
    random.shuffle(items)
    for item in items:
        product = api.get_json(f"/api/v1/products/{item['slug']}")
        variants = [v for v in product["variants"] if v["is_active"] and v["stock_quantity"] >= 5]
        if len(variants) >= count:
            return variants[:count]
    raise RuntimeError("Not enough in-stock product variants in the catalog")


def _sign_webhook(payload: bytes, secret: str) -> str:
    """Build a Stripe-Signature header for ``payload`` (same scheme stripe-cli uses)."""
    timestamp = int(time.time())
    signed = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def simulate_stripe_webhook(api: ApiClient, payment_intent_id: str, secret: str) -> None:
    """Send a signed payment_intent.succeeded event to the API's Stripe webhook."""
    event = {
        "id": f"evt_sim_{uuid.uuid4().hex[:16]}",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": payment_intent_id}},
    }
    payload = json.dumps(event).encode()
    signature = _sign_webhook(payload, secret)
    api.request(
        "POST",
        "/api/v1/payments/webhook",
        content=payload,
        headers={"Stripe-Signature": signature},
    )
    print(f"   Webhook delivered and verified: {event['id']}")


def run(
    api_url: str,
    mailpit_url: str | None,
    admin_email: str,
    admin_password: str,
    webhook_secret: str | None,
) -> None:
    anonymous = ApiClient(api_url)
    wait_for_api(anonymous)

    user_email = f"client.{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"

    # 1. Register
    print(f"\n1) Registering customer {user_email}...")
    anonymous.post_json(
        "/api/v1/auth/register",
        {
            "email": user_email,
            "password": password,
            "first_name": "Sim",
            "last_name": "Client",
            "phone": "+1 555 0100",
        },
    )
    print("   Registration accepted, verification email pending, limit 5/minute applies")

    # 2. (Optional) Read the real email from Mailpit and "click" the link
    assert mailpit_url, "Mailpit URL must be provided to verify the email (for simulation purposes)"
    print("\n2) Waiting for the verification email in Mailpit...")
    
    token = wait_for_verification_token(mailpit_url, user_email)
    
    anonymous.post_json("/api/v1/auth/verify-email", {"token": token})
    print("   Email verified via the link in the real email")

    # 3.  ==================================== Login =========================================
    print("\n3) Logging in...")
    tokens = anonymous.post_json("/api/v1/auth/login", {"email": user_email, "password": password})
    user = ApiClient(api_url, token=tokens["access_token"])
    me = user.get_json("/api/v1/users/me")
    print(f"   Logged in as user id={me['id']}")

    # 4. ==================================== Shipping address ====================================
    print("\n4) Creating shipping address...")
    city, state, postal_code = random.choice(_CITIES)
    address = user.post_json(
        "/api/v1/users/me/addresses",
        {
            "label": "Home",
            "street": random.choice(_STREETS),
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": "US",
            "is_default": True,
        },
    )
    print(
        f"   Address: {address['street']}, {address['city']}, {address['state']} {address['postal_code']}")

    # 5. ========================================= Cart ========================================
    print("\n5) Adding items to cart...")
    variants = pick_variants(user)
    cart = None
    for variant in variants:
        cart = user.post_json(
            "/api/v1/cart/items",
            {"variant_id": variant["id"], "quantity": random.randint(1, 2)},
        )
    total_qty = sum(item["quantity"] for item in cart["items"])
    print(f"   Cart items: {total_qty}")

    # 6. ========================================= Order ========================================
    print("\n6) Creating order...")
    order = user.post_json(
        "/api/v1/orders",
        {"shipping_address_id": address["id"], "notes": "Please leave the package at the front door."},
    )
    print(f"   Order #{order['id']}: total=${order['total']}, status={order['status']}")

    # 7-8. Payment: create a real Stripe payment intent through the API, then
    # confirm it with a signed webhook. Falls back to the admin marking the
    # order paid when Stripe/webhook secret are not available.
    paid_via_stripe = False
    print("\n7) Creating payment intent (Stripe)...")
    # try:
    intent = user.post_json("/api/v1/payments/intent", {"order_id": order["id"]})
    print(f"   Payment intent: {intent['payment_intent_id']}")
    assert webhook_secret, "Stripe webhook secret must be provided to simulate the payment_intent.succeeded event"
    # if webhook_secret:
    print("\n8) Simulating Stripe webhook (payment_intent.succeeded)...")
    simulate_stripe_webhook(anonymous, intent["payment_intent_id"], webhook_secret)
    order = user.get_json(f"/api/v1/orders/{order['id']}")
    print(f"   Order status: {order['status']}")
    paid_via_stripe = order["status"] == "paid"
    # else:
    #     print("   STRIPE_WEBHOOK_SECRET not set; skipping webhook simulation")
    #except RuntimeError as exc:
    #    print(f"   Payment via Stripe unavailable ({exc})")

    if not paid_via_stripe:
        print("   Falling back: the admin will register the payment")

    # 9. (Payment fallback +) fulfillment lifecycle through the admin endpoints.
    print("\n9) Logging in as admin...")
    admin_tokens = anonymous.post_json(
        "/api/v1/auth/login", {"email": admin_email, "password": admin_password}
    )
    admin = ApiClient(api_url, token=admin_tokens["access_token"])

    statuses = ("processing", "shipped", "delivered") if paid_via_stripe else (
        "paid",
        "processing",
        "shipped",
        "delivered",
    )
    print("\n10) Running the fulfillment lifecycle...")
    for status in statuses:
        order = admin.patch_json(f"/api/v1/orders/{order['id']}/status", {"status": status})
        print(f"   Order status: {order['status']}")

    print("\n" + "=" * 50)
    print("SIMULATION COMPLETE")
    print("=" * 50)
    print(f"Customer:     {user_email}")
    print(f"Order ID:     {order['id']}")
    print(f"Subtotal:     ${order['subtotal']}")
    print(f"Shipping:     ${order['shipping_cost']}")
    print(f"Tax:          ${order['tax_amount']}")
    print(f"Total:        ${order['total']}")
    print(f"Final status: {order['status']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate a complete client interaction with the e-commerce API over HTTP."
    )
    parser.add_argument("--api-url", default=_setting("API_URL", "http://localhost:8000"))
    parser.add_argument(
        "--mailpit-url",
        default=_setting("MAILPIT_URL"),
        help="Optional Mailpit URL to auto-verify the registration email (e.g. http://localhost:8025).",
    )
    parser.add_argument("--admin-email", default=_setting("ADMIN_EMAIL") or _DOTENV.get("SEED_ADMIN_EMAIL", "admin@example.com"))
    parser.add_argument("--admin-password", default=_setting("ADMIN_PASSWORD") or _DOTENV.get("SEED_ADMIN_PASSWORD", "Admin123!"))
    parser.add_argument(
        "--webhook-secret",
        default=_setting("STRIPE_WEBHOOK_SECRET"),
        help="Optional Stripe webhook secret used to sign the simulated payment_intent.succeeded event.",
    )
    parser.add_argument(
        "--every",
        type=float,
        metavar="MINUTES",
        default=None,
        help="Re-run the simulation every N minutes (omit to run once).",
    )
    args = parser.parse_args()

    iteration = 0
    while True:
        iteration += 1
        if args.every is not None:
            print(f"\n### Run #{iteration} at {time.strftime('%Y-%m-%d %H:%M:%S')} ###")
        try:
            run(
                args.api_url,
                args.mailpit_url,
                args.admin_email,
                args.admin_password,
                args.webhook_secret,
            )
        except (RuntimeError, TimeoutError, httpx.TransportError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            if args.every is None:
                sys.exit(1)
        if args.every is None:
            break
        print(f"\nSleeping {args.every} minute(s) until the next run...")
        try:
            time.sleep(args.every * 60)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


if __name__ == "__main__":
    main()
