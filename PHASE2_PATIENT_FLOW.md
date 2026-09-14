# Phase 2: Patient Flow Specification & Implementation Guide

This document contains the complete specification, ERD alignment, and implementation guide for **Phase 2: The Patient Flow with MIDAS Integration** of the Cafe Cucina Digital Order Management System.

In this flow, admitted patients verify their identity via the hospital's **MIDAS Hospital Management System (HMS)** and charge their food orders directly to their **hospital bill (MIDAS Credit)**.

---

## 1. ERD Assessment & Model Adjustments (Patient Flow)

Reviewing [ERD.txt](file:///d:/Digital%20Order%20Management%20Sytem/ERD.txt) for the Patient Flow:

| Entity in ERD | Current ERD / Code State | Adjustment Required for Phase 2 |
| :--- | :--- | :--- |
| **`PATIENT`** | `id`, `midas_id`, `location_id`, `name` | **Keep Model:** Retain as local cache/reference table; automatically synchronized whenever MIDAS verifies a patient. |
| **`TRANSACTIONS`** | `id`, `order_id`, `is_cod`, `is_midas_credit`, `status`, `created_at` | **Add:** `external_reference` (`CharField(max_length=128, blank=True)`) to store the MIDAS transaction token, and `amount` (`DecimalField`). |
| **`HISTORICAL_TRANSACTIONS`** | ERD specifies tracking financial records | Handled via `django-simple-history` on `billing.Transaction`. |

---

## 2. Patient Verification Architecture: The `StubMidasClient` (Option 2)

Per `CLAUDE.md`, patient verification and billing are decoupled from vendor specifics using an **adapter service pattern**. In development and staging, a **`StubMidasClient`** is used so that frontend and backend developers can build without live MIDAS network dependency.

### How Automated Synchronization Works
1. **Zero Manual Entry**: Developers never manually insert patient records. The stub simulates the live hospital registry in memory.
2. **Automatic Local Upsert**: When a patient enters their `midas_id`, the adapter verifies them, and the backend automatically synchronizes your local [Patient](file:///d:/Digital%20Order%20Management%20Sytem/customers/models.py) database table:
   ```python
   patient, _ = Patient.objects.update_or_create(
       midas_id=midas_id,
       defaults={
           "name": verified_data["name"],
           "location": qr.location
       }
   )
   ```
3. **Foreign Key Integrity**: Food orders link to `patient` seamlessly via `Order.patient`.

### Built-in Test Patient Registry

| Test MIDAS ID | Patient Name | Admitted Location | Credit Balance | Test Scenario & Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`HAMS-101`** | Ram Bahadur Shrestha | ICU Ward 3 / Bed 12 | Rs. 5,000.00 | **Happy Path**: Verification success, bed match, and successful hospital bill charge. |
| **`HAMS-102`** | Sita Devi Thapa | General Ward 1 / Bed 05 | Rs. 0.00 | **Credit Rejection**: Tests `402 Payment Required` handling when credit is zero. |
| **`HAMS-103`** | Hari Prasad Sharma | Discharged | Rs. 0.00 | **Discharged Error**: Tests `404 Not Found` (patient no longer admitted). |
| **`HAMS-104`** | Gita Karki | Maternity Ward / Bed 02 | Rs. 3,000.00 | **Bed Mismatch**: Tests rejection when scanning Bed 12 QR code. |

### Production Switch (Zero Code Changes)
To switch to live hospital servers in production, simply update `.env`:
```env
# Toggle from 'stub' to 'http'
MIDAS_BACKEND=stub
# MIDAS_BACKEND=http
# MIDAS_BASE_URL=https://hms.hamshospital.com/api/v1/
# MIDAS_API_KEY=your-production-secret-token
```

---

## 3. Patient Journey & Architecture

```
                    [ Bedside Scanned QR Code ]
                                 │
                                 ▼
                  GET /api/v1/customers/qr/{qr_id}/
                                 │
                                 ▼
             POST /api/v1/customers/patients/verify/
             • Verifies MIDAS ID & admission status
             • Verifies patient is assigned to this bed
             • Synchronizes local Patient record
             • Checks credit eligibility
                                 │
                                 ▼
                  GET /api/v1/outlets/
                  GET /api/v1/items/?outlet={id}
                  (Browse Menu & Select Items)
                                 │
                                 ▼
             POST /api/v1/orders/patient/checkout/
             • Re-checks authoritative item prices
             • Pre-checks credit limit
             • Calls MIDAS post_charge()
             • Atomically confirms Order & Transaction (is_midas_credit=True)
                                 │
                                 ▼
             GET /api/v1/orders/batch/{batch_id}/
             GET /api/v1/orders/patient/active/?midas_id={id}
             (Track status progression to delivery)
                                 │
                                 ▼
             POST /api/v1/feedback/submit/
             (Gated on DELIVERED status)
```

---

## 4. Phase 2 API Endpoints Specification

All endpoints are versioned under `/api/v1/`.

### Step 1: Patient Verification & Bed Matching
#### `POST /api/v1/customers/patients/verify/`
- **Access**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "midas_id": "HAMS-101",
  "qr_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```
- **Validation Logic**:
  1. Retrieve `QRCode` and its `Location` (e.g. Ward "ICU Ward 3", Bed "Bed 12").
  2. Call `midas_client.verify_patient(midas_id)`.
  3. Validate admission status: must be active/admitted.
  4. Validate location match: patient's admitted bed must match the scanned QR bed.
  5. Upsert local `Patient` record.
  6. Query credit eligibility.
- **Response `200 OK`**:
```json
{
  "patient": {
    "id": "c1a23b45-1234-5678-9abc-def012345678",
    "midas_id": "HAMS-101",
    "name": "Ram Bahadur Shrestha",
    "admission_status": "admitted",
    "ward": "ICU Ward 3",
    "bed": "Bed 12"
  },
  "billing_eligible": true,
  "credit_limit": 5000.00,
  "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6..."
}
```
- **Error Responses**:
  - `400 Bad Request`: Location mismatch (e.g., patient is admitted to Ward 2, but scanned QR is Ward 3).
  - `402 Payment Required`: Patient has an active credit freeze in MIDAS.
  - `404 Not Found`: MIDAS ID not found or patient discharged.

---

### Step 2: Patient Checkout (Charge to Hospital Bill)
#### `POST /api/v1/orders/patient/checkout/`
- **Access**: Public or Session-gated
- **Request Body**:
```json
{
  "midas_id": "HAMS-101",
  "qr_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "items": [
    { "item_id": "d290f1ee-6c54-4b01-90e6-d701748f0851", "quantity": 1 }
  ],
  "special_instructions": "Low sodium preparation"
}
```
- **Business Logic (`@transaction.atomic`)**:
  1. Look up `Patient` and `QRCode`.
  2. Calculate authoritative order total.
  3. Check MIDAS credit eligibility: `midas_client.check_credit_eligibility(midas_id, total_amount)`. If insufficient, return `402 Payment Required`.
  4. Generate a unique `batch_id` and `idempotency_key`.
  5. Post charge to MIDAS: `midas_client.post_charge(midas_id, total_amount, idempotency_key)`.
  6. Upon successful charge confirmation:
     - Create `Order` line items with `status='confirmed'` and `patient=patient`.
     - Create `billing.Transaction` with `is_midas_credit=True`, `status='success'`, `amount=total_amount`, and `external_reference=midas_charge_ref`.
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

---

### Step 3: Patient Active Orders & Order Tracking
#### `GET /api/v1/orders/patient/active/?midas_id={midas_id}`
- **Access**: Public / Session-gated
- Returns all orders currently in progress (`confirmed`, `preparing`, `ready`, `assigned`, `picked_up`) for the patient's bedside.

#### `GET /api/v1/orders/batch/{batch_id}/`
- Shared tracking endpoint detailing timeline status progression.

---

## 5. Phase 2 Implementation Steps

1. **Create `midas` App**:
   - Run `python manage.py startapp midas`.
   - Implement `midas/client.py` with `MidasClientInterface`, `StubMidasClient`, and `HttpMidasClient`.
   - Implement `midas/services.py` with `get_midas_client()` factory.
   - Add `midas` to `LOCAL_APPS` in `settings.py`.
2. **Update `billing/models.py`**:
   - Add `external_reference = models.CharField(max_length=128, blank=True)`.
   - Add `amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)`.
   - Run `makemigrations billing` and `migrate`.
3. **Build Patient Verification & Checkout**:
   - Add `POST /api/v1/customers/patients/verify/` in `customers`.
   - Add `POST /api/v1/orders/patient/checkout/` in `orders`.
   - Add `GET /api/v1/orders/patient/active/` in `orders`.
4. **Add Automated Tests**:
   - Test patient verification with happy path, bed mismatch, and discharged patient.
   - Test patient checkout with credit approval, credit limit rejection, and idempotency.
   - Test that failed charges never create confirmed orders.
