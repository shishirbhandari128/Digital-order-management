# SKILLS.md

Capabilities required to design, build, review, and operate the Cafe Cucina Digital Order Management System for HAMS Hospital.

## Requirements and domain analysis

- Convert patient, visitor, kitchen, delivery, outlet, and administrator journeys into acceptance criteria.
- Confirm Cafe Cucina processes before encoding business rules.
- Treat Bakery, Canteen, and Restaurant as separate fulfillment outlets within one customer order.
- Clarify cancellation windows, partial availability, split delivery, refund ownership, and feedback rules.
- Separate food-ordering requirements from clinical data and minimize stored patient information.

## Django and PostgreSQL

- Organize code into focused domain apps and keep workflow rules out of views.
- Use constraints for uniqueness, valid values, relationships, and idempotency.
- Use transactions and row locks where concurrent checkout or status updates can conflict.
- Create forward-safe schema/data migrations and never modify applied migrations.
- Optimize measured hot paths with indexes, `select_related`, `prefetch_related`, and query-plan analysis.
- Plan low-risk production migrations and test backup restoration.

## Django REST Framework

- Design versioned APIs with serializers, viewsets, routers, filtering, ordering, and pagination.
- Validate nested orders without trusting client-provided prices, totals, roles, or statuses.
- Implement role-based and object-level authorization for outlet, kitchen, delivery, and admin scopes.
- Return clear validation and workflow-conflict responses.
- Maintain OpenAPI documentation and realistic examples.
- Make retryable write endpoints idempotent, especially checkout and billing actions.

## Order orchestration

- Build checkout from authoritative prices and current availability.
- Snapshot commercial data onto order lines.
- Atomically split multi-outlet orders into outlet fulfillment orders.
- Route KOT/BOT tickets to the correct Bakery, Canteen, or Restaurant queue.
- Enforce finite-state transitions for preparation, assignment, pickup, delivery, and cancellation.
- Maintain immutable status history with actor and timestamp.

## MIDAS integration

- Build an authenticated REST/JSON adapter for verification, admission lookup, credit checks, charges, refunds, and reversals.
- Convert external payloads into typed internal results; do not leak vendor schemas into domain/public APIs.
- Configure timeouts and classify retryable versus permanent failures.
- Use idempotency keys and store external references for financial requests.
- Reconcile ambiguous outcomes before retrying charges or refunds.
- Record safe audit details and correlation IDs without exposing sensitive data.
- Supply test doubles and contract tests so local development does not require live MIDAS access.

## Billing safety

- Keep payment and fulfillment states separate.
- Confirm patient orders only after successful MIDAS charge posting.
- Track visitor orders as cash on delivery; only authorized staff can confirm collection.
- Model refunds/reversals as explicit audit-friendly workflows, never destructive edits.
- Use decimal arithmetic with defined currency, rounding, tax, discount, and reconciliation rules.
- Prevent duplicate charges with service design and database constraints.

## Kitchen and delivery operations

- Create outlet-specific preparation queues for printer, tablet, or screen use.
- Record ticket creation, acknowledgement, preparation, and ready timestamps.
- Support delivery assignment, pickup, completion, and COD collection.
- Reveal only the contact and destination details needed for an active delivery.
- Prevent completion when required fulfillment or collection steps are missing.
- Make status updates safe to retry from intermittently connected devices.

## Security, privacy, and audit

- Apply least privilege and deny access by default.
- Protect patient identity, location, contact, and billing references as sensitive data.
- Keep sensitive values out of source control, URLs, logs, traces, and analytics.
- Use secure secret storage and credential rotation.
- Audit authentication, verification, billing, status, role, and configuration actions.
- Apply throttling, secure token/session handling, CSRF protection where relevant, and dependency patching.

## Docker and operations

- Build reproducible images with pinned dependencies and a non-root runtime user.
- Use Compose for local services, health checks, and persistent PostgreSQL data.
- Keep containers stateless and configure them through environment variables.
- Run migrations as a controlled production deployment step with one migration actor.
- Expose liveness/readiness signals and use structured logs, metrics, alerts, and correlation IDs.
- Monitor MIDAS failures, reconciliation gaps, queue age, preparation/delivery time, refunds, and outlet availability.

## Testing and QA

- Write unit tests for domain invariants and API tests for validation and permissions.
- Test against PostgreSQL and a controlled MIDAS stub.
- Cover concurrency, duplicate requests, retries, rollback, and failure recovery.
- Exercise patient and visitor journeys for single- and multi-outlet orders.
- Add container startup, migration, health-check, security, performance, and user-acceptance tests.

## UI/UX collaboration

- Design mobile-first flows for bedside, ward, and outlet QR access.
- Clearly distinguish patient verification from visitor checkout.
- Present outlet, availability, price, payment, preparation, and delivery status unambiguously.
- Optimize kitchen and delivery screens for fast, low-interaction operation.
- Meet accessibility requirements for contrast, keyboard use, focus, and error recovery.

## Reporting and analytics

- Define order volume, revenue, preparation time, delivery time, cancellations, refunds, ratings, and outlet-performance metrics.
- Preserve historical order facts after menus and prices change.
- Restrict reports by role and outlet and exclude unnecessary patient identifiers.
- Reconcile report totals with MIDAS billing and COD records.

## Definition of done

1. Acceptance criteria and authorization rules are explicit.
2. Required migrations, indexes, and constraints are included.
3. Success, failure, edge-case, concurrency, and permission tests pass.
4. MIDAS and financial actions are safely idempotent or explicitly reconcilable.
5. Logs and audit events are useful without containing sensitive data.
6. API documentation and environment examples are current.
7. Django checks and relevant tests pass inside the application container.
8. The workflow is verified from the end user's perspective.