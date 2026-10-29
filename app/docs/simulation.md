# Client Simulation (simulation/simulate.py)

`simulation/simulate.py` is a standalone script that lives **outside the app**
and runs **on the host** (never inside the containers). It exercises the
e-commerce API the same way a real customer would: exclusively through HTTP
calls to `API_URL` (default `http://localhost:8000`).

## Overview

The script walks a complete customer journey from registration to order
delivery, without touching the database, the service layer, Stripe, or SMTP.

## Step-by-Step Flow

| Step | Action | Description |
|------|--------|-------------|
| **1** | Registration | Creates a new customer account via `POST /api/v1/auth/register` |
| **2** | Email Verification (optional) | If `--mailpit-url` is set, polls Mailpit for the verification email and "clicks" the link |
| **3** | Login | Authenticates via `POST /api/v1/auth/login` and gets a JWT |
| **4** | Address Creation | Creates a shipping address with random US location data |
| **5** | Cart Addition | Picks 2 in-stock variants from the public catalog and adds them to the cart |
| **6** | Order Creation | Creates an order from the cart (`POST /api/v1/orders`) |
| **7** | Payment Intent | Creates a real Stripe payment intent via `POST /api/v1/payments/intent` |
| **8** | Payment Confirmation | Signs a `payment_intent.succeeded` event and posts it to `POST /api/v1/payments/webhook` (what `stripe trigger` does); the order flips to `paid` |
| **9** | Fulfillment Lifecycle | Logs in as the seeded admin and moves the order through `processing → shipped → delivered` |

If step 7 or 8 is not possible (Stripe unreachable, or `STRIPE_WEBHOOK_SECRET`
not set), the simulation warns and falls back to the admin marking the order
`paid` through the status endpoint before the fulfillment lifecycle.

## Key Points

- **No mocks, no internals**: everything goes through the public HTTP API,
  exactly like a browser or mobile client.
- **Email verification is optional**: the API does not require a verified
  email to log in or place orders, so without a Mailpit URL the step is
  skipped with a note. To exercise it, start the optional service
  (`docker compose --profile mailpit up -d`), point the API at it in `.env`
  (`MAIL_SERVER=mailpit`, `MAIL_PORT=1025`, `MAIL_STARTTLS=False`,
  `MAIL_SSL_TLS=False`) and set `MAILPIT_URL=http://localhost:8025` — the
  script then "clicks" the real verification link from Mailpit.
- **Stripe payment is real (with a graceful fallback)**: the payment intent is
  created through the API, and the success webhook is a correctly signed
  `payment_intent.succeeded` event (HMAC-SHA256 with `STRIPE_WEBHOOK_SECRET`,
  the same scheme `stripe trigger` uses) — the app verifies the signature and
  flips the order to `paid`. To run this locally you need Stripe reachable:
  either real test keys, or the optional `stripe-mock` service
  (`docker compose --profile stripe up -d`) plus
  `STRIPE_API_BASE=http://stripe-mock:12111` and a webhook secret in `.env`.
  Without it, the seeded admin registers the payment via the status endpoint
  and the run continues.
- **Defaults come from `.env`**: `MAILPIT_URL`, `SEED_ADMIN_EMAIL` /
  `SEED_ADMIN_PASSWORD` and `STRIPE_WEBHOOK_SECRET` are read from the repo's
  `.env` automatically; environment variables and CLI flags take precedence.

## Running the Simulation

Start the stack first:

```bash
docker compose up --build
```

Then, from the repo root (with the project's dependencies installed, e.g. the
project venv or Poetry):

```bash
python simulation/simulate.py

# Custom API location
python simulation/simulate.py --api-url http://localhost:8000

# Also auto-verify the registration email via a local Mailpit
MAILPIT_URL=http://localhost:8025 python simulation/simulate.py
```

## Configuration

| Env var / flag | Default | Purpose |
|----------------|---------|---------|
| `API_URL` / `--api-url` | `http://localhost:8000` | Base URL of the API |
| `ADMIN_EMAIL` / `--admin-email` | `SEED_ADMIN_EMAIL` from `.env`, else `admin@example.com` | Admin account (fallback payment + fulfillment) |
| `ADMIN_PASSWORD` / `--admin-password` | `SEED_ADMIN_PASSWORD` from `.env`, else `Admin123!` | Admin password |
| `MAILPIT_URL` / `--mailpit-url` | *(unset)* | Optional Mailpit API URL to auto-verify the registration email |
| `STRIPE_WEBHOOK_SECRET` / `--webhook-secret` | *(unset)* | Optional Stripe webhook secret to sign the simulated `payment_intent.succeeded` event |

## Expected Output

```
1) Registering customer client.xxxx@example.com...
   Registration accepted, verification email pending

2) No Mailpit URL configured; skipping email verification

3) Logging in...
   Logged in as user id=...

...

7) Creating payment intent (Stripe)...
   Payment intent: pi_...

8) Simulating Stripe webhook (payment_intent.succeeded)...
   Webhook delivered and verified: evt_sim_xxxxxxxx
   Order status: paid

9) Logging in as admin...

10) Running the fulfillment lifecycle...
   Order status: processing
   Order status: shipped
   Order status: delivered

==================================================
SIMULATION COMPLETE
==================================================
Customer:     client.xxxx@example.com
Order ID:     ...
Total:        $...
Final status: delivered
```
