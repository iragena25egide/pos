# Nexus POS - API Documentation

**Base URL:** `https://194.164.72.181.nip.io/api`

This documentation guides frontend/UI developers on how to integrate with the Nexus POS Backend. 

---

## 1. Global Conventions

### Authentication
All endpoints (except `/token/`) require a JWT Access Token. 
Include it in the request headers:
```http
Authorization: Bearer <your_access_token>
```

### Standardized Response Envelope
Every successful API response will be wrapped in this exact JSON structure:
```json
{
  "status": "success",
  "message": "Request processed successfully.",
  "data": { ... } // Or an Array [...]
}
```

### Pagination Response
For endpoints that return lists (e.g., `GET /sales/`), the response includes pagination keys alongside the data:
```json
{
  "status": "success",
  "message": "Request processed successfully.",
  "data": [ { ... }, { ... } ],
  "count": 42,
  "next": "https://.../?page=2",
  "previous": null
}
```

### Error Response
If a request fails (e.g., 400 Bad Request or 401 Unauthorized), the backend returns a standardized error envelope:
```json
{
  "status": "error",
  "message": "Validation failed.",
  "data": {
    "payment_amount": ["Payment amount cannot exceed the total sale amount."]
  }
}
```

---

## 2. Authentication Endpoints

### Login (Obtain Tokens)
* **URL:** `POST /token/`
* **Payload:**
  ```json
  {
    "username": "pos_admin", // Can also be the user's email
    "password": "yourpassword"
  }
  ```
* **Response `data`:**
  ```json
  {
    "access": "eyJhbGciOi...",
    "refresh": "eyJhbGciOi...",
    "username": "pos_admin",
    "email": "admin@pos.com",
    "role": "admin"
  }
  ```

### Refresh Token
* **URL:** `POST /token/refresh/`
* **Payload:** `{ "refresh": "<refresh_token>" }`
* **Response `data`:** `{ "access": "<new_access_token>" }`

---

## 3. Core Resource Endpoints

These endpoints support standard CRUD operations (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`).
Append the ID to target a specific resource (e.g., `GET /products/1/`).

* **`/users/`** - Manage staff and users.
  * *Special:* `GET /users/me/` returns the currently authenticated user's profile.
* **`/companies/`** - Manage supplier companies.
* **`/products/`** - Manage inventory.
* **`/customers/`** - Manage clients/customers.
* **`/sales/`** - Manage sales transactions.
* **`/loans/`** - View customer credit/loans.
* **`/payments/`** - Manage loan repayment slips.

### Example: Creating a Sale (`POST /sales/`)
When creating a sale, you can pass nested `items`.
```json
{
  "customer": 1,
  "total_amount": "1500.00",
  "payment_amount": "1000.00", // Will automatically create a $500 loan if total > payment
  "items": [
    {
      "product": 5,
      "quantity": 2,
      "unit_price": "750.00"
    }
  ]
}
```

---

## 4. Dashboard & Reports

### Get Dashboard Statistics
* **URL:** `GET /dashboard/stats/`
* **Description:** Returns aggregate counts, total revenue, total outstanding loans, and lists of recent sales and loans.
* **Response `data` Example:**
  ```json
  {
    "total_companies": 12,
    "total_products": 340,
    "total_customers": 85,
    "total_sales": 1240,
    "total_revenue": "45000.00",
    "total_outstanding_loans": "2500.00",
    "recent_sales": [ ... ],
    "recent_loans": [ ... ]
  }
  ```

### Revenue Report
* **URL:** `GET /reports/revenue/`
* **Query Params:** `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
* **Description:** Returns aggregated sales data grouped by company.

---

## 5. Soft Deletion & Trash System

By default, deleting a resource (`DELETE /products/1/`) performs a **Soft Delete**. It is hidden from standard API requests but remains in the database.

* **View Trash:** `GET /trash/`
  * Returns an object mapping resource names to arrays of their deleted items.
* **Restore Item:** `POST /{resource}/{id}/restore/` (e.g., `POST /products/1/restore/`)
  * Restores the item to active status.
* **Permanently Delete:** `DELETE /{resource}/{id}/force_delete/`
  * *Requires Admin Privileges.* Permanently wipes the record from the database.
