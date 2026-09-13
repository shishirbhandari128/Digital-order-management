# Cafe Cucina: Patient & Visitor Flow API Specification & ERD Assessment

This document serves as the complete **API & Data Contract** for frontend developers and backend engineers implementing the **Patient Flow** and **Visitor Flow** for the Cafe Cucina Digital Order Management System at HAMS Hospital.

---

## 1. ERD Assessment: Is `ERD.txt` Sufficient?

Comparing [ERD.txt](file:///d:/Digital%20Order%20Management%20Sytem/ERD.txt) against the requirements of modern web/mobile ordering interfaces reveals that the ERD is **85% aligned**, but has **5 critical gaps** that must be addressed for seamless frontend integration and financial compliance:

### Critical ERD Gaps & Required Adjustments

| Entity in ERD | Current ERD Definition | Frontend / Operational Reality | Required ERD Adjustment |
| :--- | :--- | :--- | :--- |
| **`FEEDBACK`** | `id`, `order_id`, `feedback_and_others`, `created_at` | Feedback needs categorization (Food vs Delivery) and 1–5 star rating for UI widgets. | **Add:** `feedback_type` (`food_feedback` / `delivery_feedback`) and `rating` (integer 1-5). |
| **`ITEMS`** | `id`, `outlet_id`, `price`, `description`, `image_url`, `is_kot`, `is_bot`, `is_active` | Frontend menus require a concise item **title/name** (e.g., "Veg Sandwich") distinct from full description/ingredients. | **Add:** `name` (`CharField(max_length=255)`). |
| **`ORDERS`** | `id`, `qr_id`, `order_id` (batch), `item_id`, `status`, `assigned_delivery_user_id`, `is_settled`, `patient_id`, `visitor_id` | When a user adds "3 Coffees", storing 3 duplicate rows without quantity creates database bloat and awkward cart handling. Also prices can change after ordering. | **Add:** `quantity` (`PositiveIntegerField(default=1)`) and `unit_price` (`DecimalField` price snapshot at checkout). |
| **`TRANSACTIONS`** | `id`, `order_id`, `is_cod`, `is_midas_credit`, `status`, `created_at` | Patient billing via MIDAS requires recording the external MIDAS transaction reference / charge token for reconciliation and audit. | **Add:** `external_reference` (`CharField(max_length=128, blank=True)`) and `amount` (`DecimalField`). |
| **`VISITOR`** | `id id "mobile"`, `string name`, `string mobile` | Using mobile number as primary key complicates foreign keys if a user's number changes. | **Keep code standard:** UUID primary key with `mobile` as a unique indexed column. |

---

## 2. Frontend User Journey & Architecture

```
                                  [ Bedside / Table QR Code ]
                                               │
                                               ▼
                                  GET /api/v1/customers/qr/{qr_id}/
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
               [ Visitor Flow ]                                [ Patient Flow ]
       POST /api/v1/customers/visitors/             POST /api/v1/customers/patients/verify/
       (Provide Name & Mobile)                      (Provide MIDAS ID & Verify Bed Location)
                       │                                               │
                       └───────────────────────┬───────────────────────┘
                                               ▼
                                 [ Menu & Outlet Browsing ]
                                 GET /api/v1/outlets/
                                 GET /api/v1/items/?outlet={id}
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
          POST /orders/visitor/checkout/                  POST /orders/patient/checkout/
          • Cash on Delivery (COD)                        • MIDAS Credit Validation & Charge
          • Transaction status: PENDING                   • Transaction status: SUCCESS
                       │                                               │
                       └───────────────────────┬───────────────────────┘
                                               ▼
                                    [ Order Tracking Page ]
                               GET /api/v1/orders/batch/{batch_id}/
                                (Poll / WebSocket live status)
                                               │
                                               ▼
                                 [ Post-Delivery Feedback ]
                               POST /api/v1/feedback/submit/
```

---

## 3. Patient Verification Architecture: The `StubMidasClient` Adapter (Option 2)

To enable end-to-end development, testing, and future frontend integration without waiting for the live hospital MIDAS network, the system uses the **`StubMidasClient` Adapter Pattern** as prescribed by [CLAUDE.md](file:///d:/Digital%20Order%20Management%20Sytem/CLAUDE.md).

### How It Works Under the Hood
1. **Zero Manual Pre-Seeding**: You do **not** need to manually insert patient records in Django Admin or seed databases. The `StubMidasClient` simulates the hospital HMS patient registry directly in code.
2. **Automated Local Sync**: The local [Patient](file:///d:/Digital%20Order%20Management%20Sytem/customers/models.py) database table is preserved as an **automatic cache/reference record** so that `Order.patient` foreign keys work seamlessly:
   - When a patient enters `midas_id`, the backend calls `midas_client.verify_patient(midas_id)`.
   - On verification, the backend automatically updates or creates the local `Patient` entry:
     ```python
     patient, _ = Patient.objects.update_or_create(
         midas_id=midas_id,
         defaults={
             "name": verified_data["name"],
             "location": qr.location
         }
     )
     ```
   - Subsequent food orders link directly to this local `patient` record.

---

### Deterministic Test Patients (Simulated Registry)

The `StubMidasClient` includes built-in test accounts covering all frontend scenarios:

| Test MIDAS ID | Patient Name | Admitted Location | Credit Balance | Test Scenario & Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`HAMS-101`** | Ram Bahadur Shrestha | ICU Ward 3 / Bed 12 | Rs. 5,000.00 | **Happy Path**: Successful verification, room match & hospital credit checkout. |
| **`HAMS-102`** | Sita Devi Thapa | General Ward 1 / Bed 05 | Rs. 0.00 | **Credit Rejection**: Tests frontend handling of `402 Payment Required`. |
| **`HAMS-103`** | Hari Prasad Sharma | Discharged | Rs. 0.00 | **Discharged Error**: Tests `404 Not Found` (patient is no longer admitted). |
| **`HAMS-104`** | Gita Karki | Maternity Ward / Bed 02 | Rs. 3,000.00 | **Bed Mismatch**: Tests rejection when scanning Bed 12 QR code. |

---

### Seamless Production Switch (Zero Code Changes)

When the HAMS Hospital IT department provides the live REST endpoint, API key, and VPN credentials:
- **No changes** to frontend contracts, UI, views, or database models are required.
- You simply update one variable in `.env`:
```env
# Change from 'stub' to 'http' when connecting to live hospital server
MIDAS_BACKEND=stub
# MIDAS_BACKEND=http
# MIDAS_BASE_URL=https://hms.hamshospital.com/api/v1/
# MIDAS_API_KEY=your-production-secret-token
```
The application switches to `HttpMidasClient` dynamically at runtime.

---

## 4. Detailed API Endpoints Specification

All endpoints are versioned under `/api/v1/`.

---

### Phase 1: Location & QR Verification

#### `GET /api/v1/customers/qr/{qr_id}/`
Resolves and validates a scanned QR code.

- **Access**: Public (`AllowAny`)
- **URL Parameter**: `qr_id` (UUID)
- **Response `200 OK`**:
```json
{
  "qr_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "location": {
    "id": "e4b52c08-6f77-4b72-a169-2f57b8c2dfa1",
    "ward_name": "ICU Ward 3",
    "bed_number": "Bed 12",
    "is_public_space": false,
    "is_patient_space_only": true
  },
  "allowed_order_types": ["patient"]
}
```
- **Error Responses**:
  - `404 Not Found`: Invalid or deactivated QR code.
  - Frontend Action: If `is_patient_space_only` is true, prompt specifically for Patient verification; if `is_public_space` is true (e.g. Canteen table), allow Visitor checkout directly.

---

### Phase 2: Customer Identification

#### A. Visitor Identification
#### `POST /api/v1/customers/visitors/`
Registers or retrieves a returning visitor profile.

- **Access**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "name": "Sarah Jenkins",
  "mobile": "9841234567"
}
```
- **Response `200 OK` / `201 Created`**:
```json
{
  "id": "7fa12345-e89b-12d3-a456-426614174000",
  "name": "Sarah Jenkins",
  "mobile": "9841234567"
}
```
- **Frontend Storage**: Store `visitor_id`, `name`, and `mobile` in `localStorage` for auto-filling subsequent visits.

---

#### B. Patient MIDAS Verification
#### `POST /api/v1/customers/patients/verify/`
Verifies patient admission status, bed alignment, and billing credit via the MIDAS adapter.

- **Access**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "midas_id": "MIDAS-HAMS-9921",
  "qr_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```
- **Response `200 OK`**:
```json
{
  "patient": {
    "id": "c1a23b45-1234-5678-9abc-def012345678",
    "midas_id": "MIDAS-HAMS-9921",
    "name": "Ram Bahadur Shrestha",
    "admission_status": "admitted",
    "ward": "ICU Ward 3",
    "bed": "Bed 12"
  },
  "billing_eligible": true,
  "credit_limit": 5000.00,
  "session_token": "eyJhbGciOiJIUzI1NiIsInR5..."
}
```
- **Error Responses**:
  - `400 Bad Request`: Location mismatch (e.g., patient admitted to Ward 2, but QR scanned is in Ward 4).
  - `402 Payment Required`: Patient account has credit hold in MIDAS.
  - `404 Not Found`: MIDAS patient ID not found or discharged.

---

### Phase 3: Outlets & Menu Browsing

#### A. List Active Outlets
#### `GET /api/v1/outlets/`
Returns Cafe Cucina outlets available for ordering.

- **Access**: Public (`AllowAny`)
- **Response `200 OK`**:
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Bakery",
    "is_open": true
  },
  {
    "id": "4da85f64-5717-4562-b3fc-2c963f66afa7",
    "name": "Canteen",
    "is_open": true
  },
  {
    "id": "5ea85f64-5717-4562-b3fc-2c963f66afa8",
    "name": "Restaurant",
    "is_open": true
  }
]
```

---

#### B. List Menu Items
#### `GET /api/v1/items/?outlet={outlet_id}&search={query}`
Returns active food items with authoritative prices.

- **Access**: Public (`AllowAny`)
- **Query Parameters**:
  - `outlet` (UUID, optional): Filter by outlet.
  - `search` (string, optional): Search by item description/title.
- **Response `200 OK`**:
```json
{
  "count": 2,
  "results": [
    {
      "id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
      "outlet": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "name": "Bakery"
      },
      "name": "Fresh Croissant",
      "description": "Butter flaky croissant baked fresh daily",
      "price": "150.00",
      "image_url": "https://hams.cafecucina.com/media/croissant.jpg",
      "is_kot": true,
      "is_bot": false,
      "is_active": true
    }
  ]
}
```

---

### Phase 4: Order Placement & Checkout

#### A. Visitor Checkout (Cash on Delivery)
#### `POST /api/v1/orders/visitor/checkout/`
Creates a visitor order batch with pending COD payment.

- **Access**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "visitor": {
    "name": "Sarah Jenkins",
    "mobile": "9841234567"
  },
  "qr_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "items": [
    { "item_id": "d290f1ee-6c54-4b01-90e6-d701748f0851", "quantity": 2 },
    { "item_id": "e390f1ee-6c54-4b01-90e6-d701748f0852", "quantity": 1 }
  ],
  "special_instructions": "Deliver near bedside chair"
}
```
- **Response `201 Created`**:
```json
{
  "batch_id": "a50c822e-8395-4673-847e-2cf0f95b5030",
  "status": "confirmed",
  "payment_method": "cash_on_delivery",
  "payment_status": "pending",
  "total_amount": "450.00",
  "delivery_location": "ICU Ward 3 - Bed 12",
  "items_count": 3,
  "created_at": "2026-09-13T22:45:00Z"
}
```

---

#### B. Patient Checkout (MIDAS Credit / Hospital Bill Charge)
#### `POST /api/v1/orders/patient/checkout/`
Validates credit with MIDAS, posts the charge, and confirms order lines atomically.

- **Access**: Public or Session-gated
- **Request Body**:
```json
{
  "midas_id": "MIDAS-HAMS-9921",
  "qr_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "items": [
    { "item_id": "d290f1ee-6c54-4b01-90e6-d701748f0851", "quantity": 1 }
  ],
  "special_instructions": "Low salt preparation"
}
```
- **Response `201 Created`**:
```json
{
  "batch_id": "b60c822e-8395-4673-847e-2cf0f95b5031",
  "status": "confirmed",
  "payment_method": "midas_hospital_credit",
  "payment_status": "success",
  "midas_charge_reference": "MIDAS-CHG-20260913-8821",
  "total_charged": "150.00",
  "patient_name": "Ram Bahadur Shrestha",
  "delivery_location": "ICU Ward 3 - Bed 12",
  "created_at": "2026-09-13T22:46:00Z"
}
```
- **Error Response `402 Payment Required`**:
```json
{
  "error": "insufficient_credit",
  "message": "Order exceeds approved MIDAS credit limit. Please contact hospital billing counter."
}
```

---

### Phase 5: Order Tracking & Status Progression

#### `GET /api/v1/orders/batch/{batch_id}/`
Live polling endpoint for the frontend tracking screen.

- **Access**: Public (`AllowAny`)
- **Response `200 OK`**:
```json
{
  "batch_id": "a50c822e-8395-4673-847e-2cf0f95b5030",
  "overall_status": "preparing",
  "status_progression": [
    { "status": "confirmed", "timestamp": "2026-09-13T22:45:00Z", "completed": true },
    { "status": "preparing", "timestamp": "2026-09-13T22:47:30Z", "completed": true },
    { "status": "ready", "timestamp": null, "completed": false },
    { "status": "picked_up", "timestamp": null, "completed": false },
    { "status": "delivered", "timestamp": null, "completed": false }
  ],
  "delivery_person": {
    "name": "Bikash Thapa",
    "assigned": true
  },
  "is_delivered": false,
  "feedback_submitted": false
}
```

#### Order Status Enum Values
- `confirmed` -> Order received and split by outlet.
- `preparing` -> Kitchen accepted KOT/BOT ticket.
- `ready` -> Kitchen marked food prepared and boxed.
- `assigned` -> Delivery rider assigned.
- `picked_up` -> Rider collected order from outlet.
- `delivered` -> Food handed over to patient/visitor.
- `cancelled` -> Cancelled (triggers MIDAS refund if patient order).

---

### Phase 6: Post-Delivery Feedback

#### `POST /api/v1/feedback/submit/`
Allows rating and comments only after an order is marked `delivered`.

- **Access**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "order_id": "e4b52c08-6f77-4b72-a169-2f57b8c2dfa1",
  "feedback_type": "food_feedback",
  "rating": 5,
  "feedback_and_others": "Food was fresh, warm, and delivered right to the bedside."
}
```
- **Response `201 Created`**:
```json
{
  "id": "8fa12345-e89b-12d3-a456-426614174099",
  "message": "Thank you for your feedback!"
}
```
- **Error Response `400 Bad Request`**:
  - If order status is not `delivered`.
  - If duplicate feedback has already been submitted for this order.

---

## 5. Summary of Recommendations for Backend Implementation

1. **Update `feedback/models.py`**:
   Add `feedback_type` choices (`food_feedback`, `delivery_feedback`) and optional `rating` field.
2. **Add `name` to `menu/models.py`**:
   Add `name = models.CharField(max_length=255)` so items have clean titles in the UI.
3. **Add `quantity` to `orders/models.py`**:
   Add `quantity = models.PositiveIntegerField(default=1)` and `unit_price = models.DecimalField(max_digits=10, decimal_places=2)`.
4. **Create `midas` Adapter App**:
   Support `StubMidasClient` for local testing and `HttpMidasClient` for production.
5. **Register URLs in `digital_order_management_system/urls.py`**:
   Mount `/api/v1/customers/`, `/api/v1/orders/`, `/api/v1/billing/`, and `/api/v1/feedback/`.
