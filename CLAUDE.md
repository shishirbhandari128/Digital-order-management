# CLAUDE.md

## Product

Build the **Cafe Cucina Digital Order Management System for HAMS Hospital** using Django, Django REST Framework, PostgreSQL, and Docker. It is a web/mobile ordering platform for patients, visitors, attendants, outlet staff, kitchen staff, delivery staff, and administrators.

Cafe Cucina operates three independently managed outlets: **Bakery**, **Canteen**, and **Restaurant**. MIDAS Hospital Management System is an external REST/JSON service and the source of truth for patient identity, admission, ward/room/bed, billing credit, and hospital charge posting.

## Goal

Deliver a seamless food-ordering experience for HAMS patients and visitors while improving Cafe Cucina's routing, preparation, delivery, billing, feedback, and reporting operations.

## Actors

- **Patient:** verified through MIDAS; may charge an eligible order to the hospital bill.
- **Visitor/attendant:** provides name and mobile number and pays cash on delivery.
- **Outlet manager:** manages menus, availability, prices, orders, and outlet reports.
- **Kitchen staff:** receives KOT/BOT tickets and updates preparation status.
- **Delivery staff:** accepts assignments, collects orders, delivers, and records cash collection.
- **Administrator:** manages users, roles, outlets, configuration, integrations, and reporting.
- **MIDAS:** provides patient/admission data and handles credit checks, charges, refunds, and reversals.

## End-to-end workflow

1. **Access:** scan a QR code at a bedside, ward, or outlet, or open the web/mobile app.
2. **Identify:** verify a patient ID through MIDAS, or collect a visitor's name and mobile number. Record the ward/room/bed or outlet delivery location.
3. **Browse:** show outlet-specific menus, item details, prices, images, and real-time availability. One cart may contain items from multiple outlets.
4. **Payment:** check patient credit and post the charge through MIDAS. Visitor orders use cash on delivery and remain unpaid until collection.
5. **Route:** split a multi-outlet order into outlet-specific fulfillment orders and create a KOT/BOT for each outlet.
6. **Prepare:** kitchen staff receives the ticket and changes its state from `preparing` to `ready`.
7. **Deliver:** assign delivery staff, record pickup, deliver to the patient/visitor, collect cash when required, and update delivery status.
8. **Feedback:** accept a 1–5 rating and optional comments for a completed order, linked to the order and outlet.

## Django app boundaries

- `accounts`: users, staff profiles, roles, and permissions.
- `customers`: patient references, visitor profiles, and delivery locations.
- `outlets`: Bakery, Canteen, Restaurant, operating hours, and service availability.
- `menu`: categories, items, prices, images, outlet assignment, and availability.
- `orders`: carts, checkout, parent orders, outlet orders, line items, totals, and status history.
- `kitchen`: KOT/BOT tickets, preparation queues, and timestamps.
- `delivery`: assignments, pickup/delivery flow, and cash collection.
- `billing`: payment state, patient charges, COD records, refunds, and reversals.
- `feedback`: ratings and comments for completed orders and outlets.
- `midas`: authenticated client, payload mapping, retries, and integration audit records.
- `reporting`: operational and management reporting APIs.

Store only the minimum patient/admission references required for verification, delivery, and billing reconciliation. Do not duplicate clinical information.

## Business invariants

- Snapshot item name, outlet, unit price, discount, tax, and quantity on each order line at checkout.
- A customer order may span outlets; each fulfillment order belongs to exactly one outlet.
- Recheck availability and authoritative prices during checkout.
- Validate every status transition and record its actor and timestamp.
- Confirm a patient order only after successful MIDAS credit validation and charge posting.
- Keep visitor COD orders unpaid until authorized staff confirms collection.
- Make MIDAS charges, refunds, and reversals idempotent and auditable.
- Never repeat an ambiguous financial request until its reference key has been reconciled.
- Accept feedback only for delivered orders according to a defined duplicate-submission rule.
- Expose patient, destination, and contact data only to roles that need it.

## State model

Use explicit transition rules:

`draft -> pending_payment -> confirmed -> routed -> preparing -> ready -> assigned -> picked_up -> delivered`

Allow cancellation only from approved states. If a patient order was already charged, cancellation must trigger a tracked refund/reversal workflow. Keep payment status separate from fulfillment status.

## API conventions

- Put versioned business endpoints under `/api/v1/`; retain `/api/health/` for health checks.
- Use DRF serializers for all input validation and output representation.
- Use UUIDs for externally visible identifiers.
- Return consistent errors containing a stable code, message, and field details where relevant.
- Paginate collections; add filtering and ordering deliberately.
- Require authentication for staff APIs and object-level, outlet-scoped authorization.
- Document introduced APIs with OpenAPI.
- Use database transactions for checkout, order splitting, status changes, and other multi-write actions.
- Move slow or failure-prone integration work to durable background jobs when that infrastructure is added.

## MIDAS integration

The adapter must support patient verification, patient/admission and ward/room/bed lookup, billing eligibility, charge posting, refund/reversal, and authenticated REST/JSON transport.

Keep MIDAS payloads inside the `midas` adapter. Domain code calls typed service methods rather than constructing vendor requests. Use configurable timeouts and bounded retries only for safe operations. Store idempotency keys and external references. Log correlation ID, latency, outcome, and safe error metadata—never credentials or unnecessary patient data. Provide a stub for development and contract testing.

## Security and privacy

- Deny access by default and apply least privilege to every role.
- Keep secrets in environment variables; never commit `.env` or credentials.
- Encrypt production traffic and use a deployment secret store.
- Validate QR/location identifiers, user input, and MIDAS responses.
- Audit verification, financial actions, status changes, and privileged configuration changes.
- Keep patient data out of URLs, routine logs, analytics, and user-facing errors.
- Define retention, deletion, backup, restore, and incident-response procedures before production.

## Engineering rules

- Put business rules in domain services or model methods, not views.
- Prevent N+1 queries with deliberate `select_related` and `prefetch_related` usage.
- Enforce invariants with database constraints and add indexes for measured query patterns.
- Commit migrations with model changes; never edit an applied migration.
- Keep containers stateless and persist PostgreSQL through managed storage/volumes.
- Add type hints at service and integration boundaries.
- Make small, reviewable changes with tests and documentation.

## Testing requirements

Cover patient verification success/failure/timeouts, visitor and patient checkout, insufficient credit, ambiguous MIDAS results, multi-outlet splitting, KOT/BOT routing, availability races, valid and invalid transitions, role/outlet authorization, delivery and COD collection, idempotent refunds, feedback eligibility, and query counts for important endpoints.

Before completing work, run:

```sh
docker compose exec web python manage.py check
docker compose exec web python manage.py test
```

## Local commands

```sh
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Use `docker compose down -v` only when intentionally deleting local PostgreSQL data.

## Delivery phases

1. Confirm requirements, Cafe Cucina processes, and MIDAS contracts.
2. Finalize architecture, UX, integration design, schema, security, and rollout plan.
3. Implement modular APIs, MIDAS integration, customer UI, staff workflows, and tests.
4. Pilot in one outlet or ward, train users, and incorporate feedback.
5. Roll out to all outlets with training and go-live support.
6. Monitor, support, improve performance, and add evidence-based enhancements.