# Postman Test Plan — Cafe Cucina Digital Order Management System API

This document walks through **every API endpoint** currently implemented in the project, in the order you should run them in Postman so that each test's output feeds the next test's input (IDs, tokens, batch numbers, etc.).

Run tests **in order, top to bottom**, on a fresh database if possible.

---

## 0. Setup

### 0.1 Start the stack
```sh
docker compose up --build
docker compose exec web python manage.py migrate
```

### 0.2 Create the first Administrator (CLI only)
`POST /api/v1/accounts/register/` requires an authenticated **admin** caller, so the very first user must be created from the CLI:
```sh
docker compose exec web python manage.py createsuperuser
```
Enter a username, email, and password when prompted. The custom `CustomUserManager` automatically sets `role=administrator` and `is_staff=is_superuser=True` for this user.

### 0.3 Postman Environment Variables
Create a Postman environment named **Cafe Cucina Local** with these variables (leave values empty except `base_url`):

| Variable | Initial Value |
| :--- | :--- |
| `base_url` | `http://localhost:8000` |
| `access_token` | |
| `refresh_token` | |
| `outlet_id` | |
| `item_id` | |
| `inactive_item_id` | |
| `location_id` | |
| `qr_id` | |
| `patient_id` | |
| `visitor_id` | |
| `order_id` | |
| `batch_id` | |
| `patient_batch_id` | |
| `transaction_id` | |
| `feedback_id` | |

For every request below that returns `access` in its body, add this to the request's **Tests** tab so later requests stay authenticated automatically:
```js
if (pm.response.code < 300) {
  const body = pm.response.json();
  if (body.access) pm.environment.set('access_token', body.access);
  if (body.refresh) pm.environment.set('refresh_token', body.refresh);
}
```
For every authenticated request, set header `Authorization: Bearer {{access_token}}`.

### 0.4 Built-in MIDAS stub test patients
The `midas` app ships a stub registry used by every patient-flow test below:

| MIDAS ID | Name | Ward / Bed | Credit | Scenario |
| :--- | :--- | :--- | :--- | :--- |
| `HAMS-101` | Ram Bahadur Shrestha | ICU Ward 3 / Bed 12 | Rs. 5,000.00 | Happy path |
| `HAMS-102` | Sita Devi Thapa | General Ward 1 / Bed 05 | Rs. 0.00 | Credit rejection |
| `HAMS-103` | Hari Prasad Sharma | Discharged | Rs. 0.00 | Discharged / not found |
| `HAMS-104` | Gita Karki | Maternity Ward / Bed 02 | Rs. 3,000.00 | Bed mismatch |

---

## 1. API Root & Discovery

### Test 1 — API root lists all endpoints
- **GET** `{{base_url}}/`
- Auth: none
- Expected: `200 OK`, JSON body with `status: "online"` and an `endpoints` object listing every route used below.

---

## 2. Accounts (Auth)

### Test 2 — Login as the superuser
- **POST** `{{base_url}}/api/v1/accounts/login/`
- Auth: none
- Body:
```json
{ "username": "<your-superuser-username>", "password": "<your-superuser-password>" }
```
- Expected: `200 OK`, body has `access`, `refresh`, and `user.role = "administrator"`.
- Save: use the Tests-tab script from §0.3 to store `access_token` / `refresh_token`.

### Test 3 — Login rejects wrong password
- **POST** `{{base_url}}/api/v1/accounts/login/`
- Body: same username, wrong password.
- Expected: `401 Unauthorized`.

### Test 4 — Register a new staff user (admin-only)
- **POST** `{{base_url}}/api/v1/accounts/register/`
- Auth: `Bearer {{access_token}}`
- Body:
```json
{
  "username": "outlet_mgr_bakery",
  "email": "bakery.mgr@example.com",
  "name": "Bakery Manager",
  "role": "outlet_manager",
  "password": "StrongPass123!"
}
```
- Expected: `201 Created`, `role: "outlet_manager"`.

### Test 5 — Register rejects an invalid role
- **POST** `{{base_url}}/api/v1/accounts/register/`
- Auth: `Bearer {{access_token}}`
- Body: same as Test 4 but `"role": "superadmin"`.
- Expected: `400 Bad Request` on the `role` field.

### Test 6 — Register is forbidden for non-admins
- **POST** `{{base_url}}/api/v1/accounts/register/`
- Auth: none (or a non-admin token, once you have one).
- Expected: `401 Unauthorized` (or `403 Forbidden` if using a non-admin token).

### Test 7 — Refresh the access token
- **POST** `{{base_url}}/api/token/refresh/`
- Auth: none
- Body:
```json
{ "refresh": "{{refresh_token}}" }
```
- Expected: `200 OK`, new `access` token returned. Update `{{access_token}}` from this response too.

### Test 8 — Logout blacklists the refresh token
- **POST** `{{base_url}}/api/v1/accounts/logout/`
- Auth: `Bearer {{access_token}}`
- Body:
```json
{ "refresh": "{{refresh_token}}" }
```
- Expected: `205 Reset Content`.

### Test 9 — Blacklisted refresh token can no longer refresh
- **POST** `{{base_url}}/api/token/refresh/`
- Body: `{ "refresh": "{{refresh_token}}" }` (the one just blacklisted).
- Expected: `401 Unauthorized`.
- **Re-run Test 2** now to get a fresh `access_token`/`refresh_token` for the rest of the plan.

---

## 3. Outlets

### Test 10 — Create an outlet
- **POST** `{{base_url}}/api/v1/outlets/`
- Auth: `Bearer {{access_token}}`
- Body: `{ "name": "Bakery" }`
- Expected: `201 Created`. Save `id` → `{{outlet_id}}`.

### Test 11 — Creating a duplicate outlet name fails
- **POST** `{{base_url}}/api/v1/outlets/`
- Body: `{ "name": "Bakery" }`
- Expected: `400 Bad Request` (unique constraint on `name`).

### Test 12 — List outlets (public)
- **GET** `{{base_url}}/api/v1/outlets/`
- Auth: none
- Expected: `200 OK`, paginated list containing "Bakery".

### Test 13 — Retrieve one outlet
- **GET** `{{base_url}}/api/v1/outlets/{{outlet_id}}/`
- Expected: `200 OK`.

### Test 14 — Creating an outlet without auth fails
- **POST** `{{base_url}}/api/v1/outlets/` (no Authorization header)
- Body: `{ "name": "Canteen" }`
- Expected: `401 Unauthorized`.

### Test 15 — Update an outlet
- **PATCH** `{{base_url}}/api/v1/outlets/{{outlet_id}}/`
- Auth: `Bearer {{access_token}}`
- Body: `{ "name": "Cafe Cucina Bakery" }`
- Expected: `200 OK`, name updated. (Reset back to `"Bakery"` afterwards if you want the rest of the plan's names to match, or just keep the new name — it doesn't matter downstream.)

---

## 4. Menu Items

### Test 16 — Create an active item
- **POST** `{{base_url}}/api/v1/items/`
- Auth: `Bearer {{access_token}}`
- Body:
```json
{
  "outlet": "{{outlet_id}}",
  "name": "Croissant",
  "price": "150.00",
  "description": "Buttery croissant",
  "is_kot": false,
  "is_bot": true,
  "is_active": true
}
```
- Expected: `201 Created`. Save `id` → `{{item_id}}`. Response's `outlet` field is expanded to the full outlet object.

### Test 17 — Create an inactive item (for negative tests later)
- **POST** `{{base_url}}/api/v1/items/`
- Body: same as Test 16 with `"name": "Stale Bun"`, `"price": "10.00"`, `"is_active": false`.
- Expected: `201 Created`. Save `id` → `{{inactive_item_id}}`.

### Test 18 — Public item list hides inactive items
- **GET** `{{base_url}}/api/v1/items/` (no Authorization header)
- Expected: `200 OK`; `Stale Bun` is **not** in the results, `Croissant` is.

### Test 19 — Authenticated item list shows inactive items too
- **GET** `{{base_url}}/api/v1/items/`
- Auth: `Bearer {{access_token}}`
- Expected: both `Croissant` and `Stale Bun` present.

### Test 20 — Filter items by outlet
- **GET** `{{base_url}}/api/v1/items/?outlet={{outlet_id}}`
- Expected: only items belonging to that outlet.

### Test 21 — Search items by name/description
- **GET** `{{base_url}}/api/v1/items/?search=croissant`
- Expected: `Croissant` returned, `Stale Bun` not.

### Test 22 — Retrieve, then update an item's price
- **GET** `{{base_url}}/api/v1/items/{{item_id}}/` → `200 OK`.
- **PATCH** `{{base_url}}/api/v1/items/{{item_id}}/` with `{ "price": "175.00" }`, auth required → `200 OK`.

---

## 5. Customers — Locations, QR Codes, Visitors

### Test 23 — Create a ward/bed location
- **POST** `{{base_url}}/api/v1/customers/locations/`
- Auth: `Bearer {{access_token}}`
- Body:
```json
{ "ward_name": "ICU Ward 3", "bed_number": "Bed 12", "is_public_space": false, "is_patient_space_only": false }
```
- Expected: `201 Created`. Save `id` → `{{location_id}}`.

### Test 24 — List/retrieve locations requires auth
- **GET** `{{base_url}}/api/v1/customers/locations/` (no auth) → `401 Unauthorized`.
- **GET** `{{base_url}}/api/v1/customers/locations/` (with auth) → `200 OK`.

### Test 25 — Create a QR code for the location
- **POST** `{{base_url}}/api/v1/customers/qr-codes/`
- Auth: `Bearer {{access_token}}`
- Body: `{ "location": "{{location_id}}", "image_url": "" }`
- Expected: `201 Created`. Save `id` → `{{qr_id}}`.

### Test 26 — Public QR lookup (bedside scan)
- **GET** `{{base_url}}/api/v1/customers/qr/{{qr_id}}/`
- Auth: none
- Expected: `200 OK`, body has `location.ward_name = "ICU Ward 3"` and `allowed_order_types: ["visitor", "patient"]`.

### Test 27 — QR lookup 404 for unknown id
- **GET** `{{base_url}}/api/v1/customers/qr/00000000-0000-0000-0000-000000000000/`
- Expected: `404 Not Found`.

### Test 28 — Patient-only space restricts order types
- **POST** `{{base_url}}/api/v1/customers/locations/` → `{ "ward_name": "NICU", "bed_number": "Bed 1", "is_public_space": false, "is_patient_space_only": true }` (auth) → `201 Created`.
- **POST** `{{base_url}}/api/v1/customers/qr-codes/` → `{ "location": "<NICU location id>" }` (auth) → `201 Created`.
- **GET** `{{base_url}}/api/v1/customers/qr/<that qr id>/` (no auth) → `allowed_order_types: ["patient"]` only.

### Test 29 — Register a visitor (public, self-service)
- **POST** `{{base_url}}/api/v1/customers/visitors/`
- Auth: none
- Body: `{ "name": "Sarah Jenkins", "mobile": "9841234567" }`
- Expected: `201 Created`. Save `id` → `{{visitor_id}}`.

### Test 30 — Re-registering the same mobile returns the existing visitor
- **POST** `{{base_url}}/api/v1/customers/visitors/`
- Body: `{ "name": "Different Name", "mobile": "9841234567" }`
- Expected: `200 OK` (not 201), same `id` as Test 29.

### Test 31 — Visitor list requires auth
- **GET** `{{base_url}}/api/v1/customers/visitors/` (no auth) → `401 Unauthorized`.
- **GET** `{{base_url}}/api/v1/customers/visitors/` (auth) → `200 OK`.

### Test 32 — Direct Patient CRUD (administrative, not the MIDAS flow)
- **POST** `{{base_url}}/api/v1/customers/patients/`
- Auth: `Bearer {{access_token}}`
- Body: `{ "midas_id": "MANUAL-001", "location": "{{location_id}}", "name": "Manual Test Patient" }`
- Expected: `201 Created`. Save `id` → `{{patient_id}}`.
- **GET** `{{base_url}}/api/v1/customers/patients/{{patient_id}}/` (auth) → `200 OK`.

---

## 6. Patient Verification (MIDAS Integration)

### Test 33 — Verify happy path (HAMS-101 at the matching bed)
- **POST** `{{base_url}}/api/v1/customers/patients/verify/`
- Auth: none
- Body: `{ "midas_id": "HAMS-101", "qr_id": "{{qr_id}}" }` (the ICU Ward 3 / Bed 12 QR from Test 25)
- Expected: `200 OK`.
  - `patient.name = "Ram Bahadur Shrestha"`, `admission_status = "admitted"`, `ward = "ICU Ward 3"`, `bed = "Bed 12"`.
  - `billing_eligible: true`, `credit_limit: "5000.00"`.
  - `session_token` is a non-empty JWT string.
- Confirm the sync: **GET** `{{base_url}}/api/v1/customers/patients/` (auth) now also lists a `HAMS-101` patient row.

### Test 34 — Re-verifying updates (not duplicates) the local patient
- Repeat Test 33.
- Expected: still `200 OK`; **GET** the patient list again and confirm there is still only **one** `HAMS-101` row (upsert, not insert).

### Test 35 — Bed mismatch is rejected
- **POST** `{{base_url}}/api/v1/customers/patients/verify/`
- Body: `{ "midas_id": "HAMS-104", "qr_id": "{{qr_id}}" }` (HAMS-104 belongs in Maternity Ward / Bed 02, but you're scanning Bed 12).
- Expected: `400 Bad Request`, `detail` explains the ward/bed mismatch.

### Test 36 — Discharged patient is rejected
- **POST** `{{base_url}}/api/v1/customers/patients/verify/`
- Body: `{ "midas_id": "HAMS-103", "qr_id": "{{qr_id}}" }`
- Expected: `404 Not Found`.

### Test 37 — Unknown MIDAS id is rejected
- **POST** `{{base_url}}/api/v1/customers/patients/verify/`
- Body: `{ "midas_id": "HAMS-DOES-NOT-EXIST", "qr_id": "{{qr_id}}" }`
- Expected: `404 Not Found`.

### Test 38 — Unknown QR id is rejected
- **POST** `{{base_url}}/api/v1/customers/patients/verify/`
- Body: `{ "midas_id": "HAMS-101", "qr_id": "00000000-0000-0000-0000-000000000000" }`
- Expected: `404 Not Found`.

### Test 39 — Zero-credit patient still verifies, but is not billing-eligible
- Create a matching location/QR first: **POST** `/api/v1/customers/locations/` → `{ "ward_name": "General Ward 1", "bed_number": "Bed 05" }` (auth), then **POST** `/api/v1/customers/qr-codes/` with that location id (auth).
- **POST** `{{base_url}}/api/v1/customers/patients/verify/` → `{ "midas_id": "HAMS-102", "qr_id": "<that qr id>" }`
- Expected: `200 OK`, `billing_eligible: false`, `credit_limit: "0.00"`.

---

## 7. Orders — Visitor Flow (Cash on Delivery)

### Test 40 — Visitor checkout (public, cash on delivery)
- **POST** `{{base_url}}/api/v1/orders/visitor/checkout/`
- Auth: none
- Body:
```json
{
  "visitor": { "name": "Sarah Jenkins", "mobile": "9841234567" },
  "qr_id": "{{qr_id}}",
  "items": [{ "item_id": "{{item_id}}", "quantity": 2 }],
  "special_instructions": "Deliver near bedside chair"
}
```
- Expected: `201 Created`.
  - `status: "confirmed"`, `payment_method: "cash_on_delivery"`, `payment_status: "pending"`.
  - `total_amount: "350.00"` (2 × 175.00 from Test 22's price update).
- Save `batch_id` → `{{batch_id}}`.

### Test 41 — Checkout rejects an inactive item
- **POST** `{{base_url}}/api/v1/orders/visitor/checkout/`
- Body: same as Test 40 but `items: [{ "item_id": "{{inactive_item_id}}", "quantity": 1 }]`.
- Expected: `400 Bad Request`. No order rows created for this call.

### Test 42 — Checkout rejects an unknown QR code
- **POST** `{{base_url}}/api/v1/orders/visitor/checkout/`
- Body: same as Test 40 but `"qr_id": "00000000-0000-0000-0000-000000000000"`.
- Expected: `404 Not Found`.

### Test 43 — A mixed valid/invalid item list creates nothing (atomicity)
- **POST** `{{base_url}}/api/v1/orders/visitor/checkout/`
- Body: `items` array containing both `{{item_id}}` and a random UUID.
- Expected: `400 Bad Request`. Verify via Test 45 (order list) that no stray order was created from this call.

### Test 44 — Visitor order history by mobile
- **GET** `{{base_url}}/api/v1/orders/visitor/history/?mobile=9841234567`
- Auth: none
- Expected: `200 OK`, at least one batch entry with `items_count: 2`, `total_amount: "350.00"`.

### Test 45 — Visitor history requires the mobile query param
- **GET** `{{base_url}}/api/v1/orders/visitor/history/` (no query param)
- Expected: `400 Bad Request`.

---

## 8. Orders — Direct CRUD & Status Transitions

### Test 46 — List orders (auth required)
- **GET** `{{base_url}}/api/v1/orders/` (no auth) → `401 Unauthorized`.
- **GET** `{{base_url}}/api/v1/orders/` (auth) → `200 OK`. Find the order created in Test 40; save its `id` → `{{order_id}}`.

### Test 47 — Retrieve a single order
- **GET** `{{base_url}}/api/v1/orders/{{order_id}}/`
- Auth: `Bearer {{access_token}}`
- Expected: `200 OK`, `status: "confirmed"`.

### Test 48 — Invalid status transition is rejected
- **PATCH** `{{base_url}}/api/v1/orders/{{order_id}}/`
- Auth required. Body: `{ "status": "ready" }` (skipping `routed`/`preparing`).
- Expected: `400 Bad Request` — the serializer enforces the state machine `draft → pending_payment → confirmed → routed → preparing → ready → assigned → picked_up → delivered`.

### Test 49 — Walk the order through valid transitions
Run each of these as a separate **PATCH** `{{base_url}}/api/v1/orders/{{order_id}}/` (auth), in order, expecting `200 OK` each time:
1. `{ "status": "routed" }`
2. `{ "status": "preparing" }`
3. `{ "status": "ready" }`
4. `{ "status": "assigned" }`
5. `{ "status": "picked_up" }`
6. `{ "status": "delivered" }`

### Test 50 — Terminal state rejects further transitions
- **PATCH** `{{base_url}}/api/v1/orders/{{order_id}}/` with `{ "status": "confirmed" }` (trying to go backwards from `delivered`).
- Expected: `400 Bad Request`.

### Test 51 — An order must have exactly one of patient/visitor
- **POST** `{{base_url}}/api/v1/orders/` with both `patient` and `visitor` set (or neither) on an otherwise valid payload.
- Expected: `400 Bad Request` either way.

### Test 52 — Batch tracking reflects the delivered state
- **GET** `{{base_url}}/api/v1/orders/batch/{{batch_id}}/`
- Auth: none
- Expected: `200 OK`, `overall_status: "delivered"`, `is_delivered: true`, every `status_progression` entry has `completed: true` with a timestamp, `feedback_submitted: false`.

### Test 53 — Batch tracking 404 for an unknown batch
- **GET** `{{base_url}}/api/v1/orders/batch/00000000-0000-0000-0000-000000000000/`
- Expected: `404 Not Found`.

---

## 9. Orders — Patient Flow (MIDAS Hospital Credit)

> Uses `HAMS-101` verified in Test 33 against `{{qr_id}}` (ICU Ward 3 / Bed 12).

### Test 54 — Patient checkout succeeds and charges MIDAS
- **POST** `{{base_url}}/api/v1/orders/patient/checkout/`
- Auth: none
- Body:
```json
{
  "midas_id": "HAMS-101",
  "qr_id": "{{qr_id}}",
  "items": [{ "item_id": "{{item_id}}", "quantity": 1 }],
  "special_instructions": "Low sodium preparation"
}
```
- Expected: `201 Created`.
  - `payment_method: "midas_hospital_credit"`, `payment_status: "success"`.
  - `midas_charge_reference` starts with `MIDAS-CHG-`.
  - `patient_name: "Ram Bahadur Shrestha"`, `delivery_location: "ICU Ward 3 - Bed 12"`.
- Save `batch_id` → `{{patient_batch_id}}`.

### Test 55 — Checkout for a never-verified MIDAS id is rejected
- **POST** `{{base_url}}/api/v1/orders/patient/checkout/`
- Body: same shape as Test 54 but `"midas_id": "HAMS-104"` (not yet verified against any QR in this run).
- Expected: `404 Not Found` — "Patient must be verified via MIDAS before checkout."

### Test 56 — Insufficient MIDAS credit is rejected and creates nothing
- First verify `HAMS-102` against its own ward/bed QR (from Test 39) if you haven't already.
- **POST** `{{base_url}}/api/v1/orders/patient/checkout/` with `"midas_id": "HAMS-102"` and any valid item.
- Expected: `402 Payment Required`.
- Confirm via Test 58 (below) that no order/transaction was created for this attempt.

### Test 57 — Patient checkout rejects an inactive item
- **POST** `{{base_url}}/api/v1/orders/patient/checkout/` with `"midas_id": "HAMS-101"` and `items: [{ "item_id": "{{inactive_item_id}}", "quantity": 1 }]`.
- Expected: `400 Bad Request`, no charge attempted.

### Test 58 — Patient's active orders list
- **GET** `{{base_url}}/api/v1/orders/patient/active/?midas_id=HAMS-101`
- Auth: none
- Expected: `200 OK`, one batch entry with `status: "confirmed"`, `delivery_location: "ICU Ward 3 - Bed 12"`. The `HAMS-102` attempt from Test 56 must **not** appear anywhere (it was never created).

### Test 59 — Active orders requires the midas_id query param
- **GET** `{{base_url}}/api/v1/orders/patient/active/` (no query param)
- Expected: `400 Bad Request`.

### Test 60 — Delivered patient orders drop out of the active list
- Advance the order from Test 54 through all transitions to `delivered` (repeat the PATCH sequence from Test 49, using that order's `id` — fetch it from `GET /api/v1/orders/` filtered by `{{patient_batch_id}}`).
- **GET** `{{base_url}}/api/v1/orders/patient/active/?midas_id=HAMS-101` again.
- Expected: that batch is no longer listed (only active statuses `confirmed/preparing/ready/assigned/picked_up` are returned).

---

## 10. Billing

### Test 61 — List transactions (auth required)
- **GET** `{{base_url}}/api/v1/transactions/` (no auth) → `401 Unauthorized`.
- **GET** `{{base_url}}/api/v1/transactions/` (auth) → `200 OK`. Confirm you can see:
  - a `is_cod: true, is_midas_credit: false, status: "pending"` row from the visitor checkout (Test 40).
  - a `is_cod: false, is_midas_credit: true, status: "success"` row from the patient checkout (Test 54), with a non-empty `external_reference` and `amount` matching the item price.
- Save any transaction `id` → `{{transaction_id}}`.

### Test 62 — Retrieve a single transaction
- **GET** `{{base_url}}/api/v1/transactions/{{transaction_id}}/`
- Auth required. Expected: `200 OK`.

### Test 63 — Manually record a COD cash collection
- **PATCH** `{{base_url}}/api/v1/transactions/{{transaction_id}}/` (use the COD transaction from Test 40)
- Auth required. Body: `{ "status": "success" }`
- Expected: `200 OK`, `status: "success"`.

---

## 11. Feedback

### Test 64 — Feedback submission is gated on delivered status
- **POST** `{{base_url}}/api/v1/feedback/submit/`
- Auth: none
- Body: `{ "order_id": "{{order_id}}", "feedback_type": "food_feedback", "rating": 3, "feedback_and_others": "" }` — but use an order that is **not yet delivered** (e.g. create a fresh visitor checkout and use its order id without advancing status).
- Expected: `400 Bad Request` — "Feedback can only be submitted for delivered orders."

### Test 65 — Feedback submission succeeds for a delivered order
- **POST** `{{base_url}}/api/v1/feedback/submit/`
- Body: `{ "order_id": "{{order_id}}", "feedback_type": "food_feedback", "rating": 5, "feedback_and_others": "Great food, fast delivery!" }` (the order from Test 40, delivered by Test 49).
- Expected: `201 Created`, `{ "id": "...", "message": "Thank you for your feedback!" }`.
- Save `id` → `{{feedback_id}}`.

### Test 66 — Duplicate feedback for the same order is rejected
- Repeat Test 65 with the same `order_id`.
- Expected: `400 Bad Request` — "Feedback has already been submitted for this order."

### Test 67 — Rating outside 1–5 is rejected
- **POST** `{{base_url}}/api/v1/feedback/submit/` with `"rating": 6` on a different delivered order.
- Expected: `400 Bad Request`.

### Test 68 — Batch tracking now shows feedback_submitted: true
- **GET** `{{base_url}}/api/v1/orders/batch/{{batch_id}}/`
- Expected: `feedback_submitted: true` (flips from Test 52's `false`).

### Test 69 — Feedback list/detail requires auth
- **GET** `{{base_url}}/api/v1/feedback/` (no auth) → `401 Unauthorized`.
- **GET** `{{base_url}}/api/v1/feedback/` (auth) → `200 OK`.
- **GET** `{{base_url}}/api/v1/feedback/{{feedback_id}}/` (auth) → `200 OK`.

---

## 12. Admin & Browsable API (manual/browser checks)

### Test 70 — Django admin is reachable
- Open `{{base_url}}/admin/` in a browser, log in with the superuser from §0.2.
- Expected: dashboard loads with `Accounts`, `Billing` (including `Historical transactions`), `Customers`, `Menu`, `Midas` (`Midas audit logs`), `Orders`, `Outlets` sections.

### Test 71 — MIDAS audit log recorded every integration call
- In `{{base_url}}/admin/midas/midasauditlog/`, confirm rows exist for `verify_patient`, `check_credit`, and `post_charge` actions from the tests above, each with an `outcome` of `success` or `failure` and a `latency_ms` value. No patient name or ward/bed data should appear in this table — only `midas_id`, action, and reference/timing metadata.

### Test 72 — Browsable API session login
- Open `{{base_url}}/api-auth/login/`, log in, then browse `{{base_url}}/api/v1/orders/` in the browser.
- Expected: the DRF browsable API renders instead of returning `401`.

---

## Known gap (not yet implemented)

`CLAUDE.md` calls for a `/api/health/` health-check endpoint; it does not exist in the codebase yet, so there is no test for it above. Flag this if you need it for uptime monitoring.
