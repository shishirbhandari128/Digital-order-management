# Phase 1: Visitor Flow Specification & Implementation Guide

This document contains the complete specification, ERD alignment, and implementation guide for **Phase 1: The Visitor Flow** of the Cafe Cucina Digital Order Management System. 

Hospital visitors and attendants order food by scanning a QR code and paying via **Cash on Delivery (COD)**.

---

## 1. ERD Assessment & Model Adjustments (Visitor Flow)

Reviewing [ERD.txt](file:///d:/Digital%20Order%20Management%20Sytem/ERD.txt) for the Visitor Flow:

| Entity in ERD | Current ERD / Code State | Adjustment Required for Phase 1 |
| :--- | :--- | :--- |
| **`VISITOR`** | ERD: `id id "mobile"`, `string name`, `string mobile`<br>Code: UUID PK + unique `mobile` | **Keep Code Pattern:** UUID primary key with indexed unique mobile number is cleaner. |
| **`ITEMS`** | `id`, `outlet_id`, `price`, `description`, `image_url`, `is_kot`, `is_bot`, `is_active` | **Add:** `name` (`CharField(max_length=255)`) so UI displays item title distinct from description. |
| **`ORDERS`** | `id`, `qr_id`, `order_id` (batch), `item_id`, `status`, `assigned_delivery_user_id`, `is_settled`, `visitor_id` | **Add:** `quantity` (`PositiveIntegerField(default=1)`) and `unit_price` (`DecimalField` snapshot at checkout). |
| **`FEEDBACK`** | Currently missing `feedback_type` in [feedback/models.py](file:///d:/Digital%20Order%20Management%20Sytem/feedback/models.py) | **Add:** `feedback_type` choices (`food_feedback`, `delivery_feedback`) and `rating` (1–5 integer). |
| **`HISTORICAL_ORDERS`** | ERD requires tracking order state changes | **Use `django-simple-history`**: Automatically tracks status transitions and timestamps. |

---

## 2. Status Tracking: How `django-simple-history` Fits In

> **Is `django-simple-history` enough for status tracking?**
>
> **Yes!** `django-simple-history` is the ideal backend engine for status tracking:
> 1. Adding `history = HistoricalRecords()` to `Order` automatically creates and populates the `HistoricalOrder` table whenever `order.status` changes (`confirmed` -> `preparing` -> `ready` -> `assigned` -> `picked_up` -> `delivered`).
> 2. It records the exact timestamp (`history_date`), changed fields, and user.
> 3. The public API tracking endpoint (`GET /api/v1/orders/batch/{batch_id}/`) simply queries `order.history.all()` and formats the timeline JSON for the customer's phone!

---

## 3. Visitor Journey & Architecture

```
                       [ Scanned QR Code ]
                                │
                                ▼
                 GET /api/v1/customers/qr/{qr_id}/
                                │
                                ▼
                 POST /api/v1/customers/visitors/
                 (Input: Name & Mobile Number)
                                │
                                ▼
                 GET /api/v1/outlets/
                 GET /api/v1/items/?outlet={id}
                 (Browse Menu & Select Items)
                                │
                                ▼
                 POST /api/v1/orders/visitor/checkout/
                 • Batch ID created
                 • Status set to: CONFIRMED
                 • Transaction: is_cod=True, status=PENDING
                                │
                                ▼
                 GET /api/v1/orders/batch/{batch_id}/
                 (Track status progression to delivery)
                                │
                                ▼
                 POST /api/v1/feedback/submit/
                 (Allowed only after order status is DELIVERED)
```

---

## 4. Phase 1 API Endpoints Specification

All endpoints are versioned under `/api/v1/`.

### Step 1: Resolve QR Code Location
#### `GET /api/v1/customers/qr/{qr_id}/`
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
    "is_public_space": true,
    "is_patient_space_only": false
  },
  "allowed_order_types": ["visitor", "patient"]
}
```
- **Error**: `404 Not Found` if QR is invalid or inactive.

---

### Step 2: Visitor Identification / Registration
#### `POST /api/v1/customers/visitors/`
- **Access**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "name": "Sarah Jenkins",
  "mobile": "9841234567"
}
```
- **Logic**: Performs `Visitor.objects.get_or_create(mobile=mobile, defaults={'name': name})`.
- **Response `200 OK` / `201 Created`**:
```json
{
  "id": "7fa12345-e89b-12d3-a456-426614174000",
  "name": "Sarah Jenkins",
  "mobile": "9841234567"
}
```

---

### Step 3: Browse Outlets & Active Menu
#### `GET /api/v1/outlets/`
- **Access**: Public (`AllowAny`)
- **Response `200 OK`**:
```json
[
  { "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "name": "Bakery", "is_open": true },
  { "id": "4da85f64-5717-4562-b3fc-2c963f66afa7", "name": "Canteen", "is_open": true },
  { "id": "5ea85f64-5717-4562-b3fc-2c963f66afa8", "name": "Restaurant", "is_open": true }
]
```

#### `GET /api/v1/items/?outlet={outlet_id}&search={query}`
- **Access**: Public (`AllowAny`)
- **Filters**: Returns only `is_active=True` items.
- **Response `200 OK`**:
```json
{
  "count": 2,
  "results": [
    {
      "id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
      "outlet": { "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "name": "Bakery" },
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

### Step 4: Visitor Order Checkout (Cash on Delivery)
#### `POST /api/v1/orders/visitor/checkout/`
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
- **Business Logic (`@transaction.atomic`)**:
  1. Retrieve or create `Visitor` via mobile.
  2. Validate `QRCode` exists and location is valid.
  3. Validate all items are active; snapshot current prices.
  4. Generate a unique `batch_id` (UUID).
  5. Create `Order` row for each item/quantity with `status='confirmed'` and `visitor=visitor`.
  6. Create linked `billing.Transaction` with `is_cod=True`, `is_midas_credit=False`, and `status='pending'`.
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

### Step 5: Live Order Tracking
#### `GET /api/v1/orders/batch/{batch_id}/`
- **Access**: Public (`AllowAny`)
- **Logic**: Reads batch items and leverages `django-simple-history` to compute timestamps for each progression stage.
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
  "delivery_person": { "name": "Bikash Thapa", "assigned": true },
  "is_delivered": false,
  "feedback_submitted": false
}
```

#### `GET /api/v1/orders/visitor/history/?mobile={mobile}`
- **Access**: Public (`AllowAny`)
- Retrieves active and past order batches placed by this visitor phone number.

---

### Step 6: Post-Delivery Feedback
#### `POST /api/v1/feedback/submit/`
- **Access**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "order_id": "e4b52c08-6f77-4b72-a169-2f57b8c2dfa1",
  "feedback_type": "food_feedback",
  "rating": 5,
  "feedback_and_others": "Food was warm, fresh, and delivered promptly."
}
```
- **Validation**:
  - Rejects with `400 Bad Request` if `order.status != 'delivered'`.
  - Rejects if feedback has already been submitted for this order.
- **Response `201 Created`**:
```json
{
  "id": "8fa12345-e89b-12d3-a456-426614174099",
  "message": "Thank you for your feedback!"
}
```

---

## 5. Phase 1 Implementation Steps

1. **Install `django-simple-history`**:
   Add to `requirements.txt` and `settings.py` `INSTALLED_APPS`, configure middleware.
2. **Update Models**:
   - `feedback/models.py`: Add `feedback_type` choices and `rating`.
   - `menu/models.py`: Add `name = models.CharField(max_length=255)`.
   - `orders/models.py`: Add `quantity`, `unit_price`, and `history = HistoricalRecords()`.
   - Run `makemigrations` and `migrate`.
3. **Build Views & Serializers**:
   - Public QR lookup in `customers`.
   - Visitor registration in `customers`.
   - Visitor checkout in `orders` (with atomic COD transaction in `billing`).
   - Batch tracking in `orders`.
   - Gated feedback submission in `feedback`.
4. **Register URLs**:
   Mount `/api/v1/customers/`, `/api/v1/orders/`, `/api/v1/billing/`, and `/api/v1/feedback/` in `digital_order_management_system/urls.py`.
5. **Add Automated Tests**:
   Create tests covering visitor checkout, COD creation, order tracking progression, and feedback gating.
