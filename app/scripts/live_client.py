"""Live client that exercises the e-commerce API over real HTTP calls.

Unlike ``app.scripts.simulate_client``, this client never touches the
database, the service layer, Stripe, or SMTP directly. It only talks to:

- the API (``API_URL``, default http://localhost:8000)
- Mailpit (``MAILPIT_URL``, default http://localhost:8025), where the API's
  outgoing SMTP mail lands, so the client can "click" the verification link
  like a real user would.

Flow:

1. Register a new customer through ``POST /api/v1/auth/register``.
2. Poll Mailpit for the verification email and extract the token.
3. Verify the email, log in, create a shipping address.
4. Browse the catalog, add two variants to the cart, create an order.
5. Skip Stripe: the seeded admin account marks the order as paid, then moves
   it through processing -> shipped -> delivered via the admin endpoints.

Run with:

    python -m app.scripts.live_client

Or as a container (see docker-compose.client.yml).
"""

from __future__ import annotations

import argparse
import os
import random
import re
import sys
import time
import uuid

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
    """Wait until the API container finishes migrations/seed and serves requests."""
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


def run(api_url: str, mailpit_url: str, admin_email: str, admin_password: str) -> None:
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
            "first_name": "Live",
            "last_name": "Client",
            "phone": "+1 555 0100",
        },
    )
    print("   Registration accepted, verification email pending")

    # 2. Read the real email from Mailpit and "click" the link
    print("\n2) Waiting for the verification email in Mailpit...")
    token = wait_for_verification_token(mailpit_url, user_email)
    anonymous.post_json("/api/v1/auth/verify-email", {"token": token})
    print("   Email verified via the link in the real email")

    # 3. Login
    print("\n3) Logging in...")
    tokens = anonymous.post_json("/api/v1/auth/login", {"email": user_email, "password": password})
    user = ApiClient(api_url, token=tokens["access_token"])
    me = user.get_json("/api/v1/users/me")
    print(f"   Logged in as user id={me['id']}")

    # 4. Shipping address
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
    print(f"   Address: {address['street']}, {address['city']}, {address['state']} {address['postal_code']}")

    # 5. Cart
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

    # 6. Order
    print("\n6) Creating order...")
    order = user.post_json(
        "/api/v1/orders",
        {"shipping_address_id": address["id"], "notes": "Please leave the package at the front door."},
    )
    print(f"   Order #{order['id']}: total=${order['total']}, status={order['status']}")

    # 7-9. No Stripe: the seeded admin registers the payment and fulfills the
    # order through the real admin endpoints.
    print("\n7) Logging in as admin to register the payment (Stripe skipped)...")
    admin_tokens = anonymous.post_json(
        "/api/v1/auth/login", {"email": admin_email, "password": admin_password}
    )
    admin = ApiClient(api_url, token=admin_tokens["access_token"])

    print("\n8) Marking order as paid and running the fulfillment lifecycle...")
    for status in ("paid", "processing", "shipped", "delivered"):
        order = admin.patch_json(f"/api/v1/orders/{order['id']}/status", {"status": status})
        print(f"   Order status: {order['status']}")

    print("\n" + "=" * 50)
    print("CLIENT RUN COMPLETE")
    print("=" * 50)
    print(f"Customer:     {user_email}")
    print(f"Order ID:     {order['id']}")
    print(f"Subtotal:     ${order['subtotal']}")
    print(f"Shipping:     ${order['shipping_cost']}")
    print(f"Tax:          ${order['tax_amount']}")
    print(f"Total:        ${order['total']}")
    print(f"Final status: {order['status']}")
    print(f"Emails:       Mailpit UI at {mailpit_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live HTTP client for the e-commerce API.")
    parser.add_argument("--api-url", default=os.environ.get("API_URL", "http://localhost:8000"))
    parser.add_argument("--mailpit-url", default=os.environ.get("MAILPIT_URL", "http://localhost:8025"))
    parser.add_argument("--admin-email", default=os.environ.get("ADMIN_EMAIL", "admin@example.com"))
    parser.add_argument(
        "--admin-password", default=os.environ.get("ADMIN_PASSWORD", "Admin123!")
    )
    args = parser.parse_args()

    try:
        run(args.api_url, args.mailpit_url, args.admin_email, args.admin_password)
    except (RuntimeError, TimeoutError, httpx.TransportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
