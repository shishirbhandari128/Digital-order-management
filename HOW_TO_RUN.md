# How to Run the Project

This guide provides step-by-step instructions to run the **Cafe Cucina Digital Order Management System** both with **Docker** (recommended) and **Locally with Python Virtualenv**.

---

## Method 1: Run with Docker (Recommended)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running on your system.

### Step 1: Ensure `.env` exists
Make sure you have a `.env` file in the project root (copied from `.env.example` if not already present):
```powershell
cp .env.example .env
```

### Step 2: Build and Start Containers
Start both the **Django web server** and **PostgreSQL database** containers:
```powershell
docker compose up --build
```
> Add `-d` at the end if you want to run containers in the background: `docker compose up --build -d`

### Step 3: Run Database Migrations
In a new terminal window:
```powershell
docker compose exec web python manage.py migrate
```

### Step 4: Create a Superuser / Admin Account
```powershell
docker compose exec web python manage.py createsuperuser
```
Follow the prompts to enter a username, email, and password.

### Step 5: Stop the Containers
When you are done:
```powershell
docker compose down
```
> *Note: Use `docker compose down -v` only if you want to wipe the database volume and start completely fresh.*

---

## Method 2: Run Locally (Without Docker)

### Prerequisites
- Python 3.12+ (or existing `.venv`)
- A running PostgreSQL server on `localhost:5432` with a database named `digital_order_management_db` (or updated credentials in `.env`).

### Step 1: Activate Virtual Environment
In PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```
*(Or in Command Prompt: `.\.venv\Scripts\activate.bat`)*

### Step 2: Install Dependencies (If not already installed)
```powershell
pip install -r requirements.txt
```

### Step 3: Run Migrations
```powershell
python manage.py migrate
```

### Step 4: Create Superuser
```powershell
python manage.py createsuperuser
```

### Step 5: Start the Development Server
```powershell
python manage.py runserver
```

---

## Available Endpoints Right Now

Once the server is running, open your browser to:

| Endpoint | URL | Description |
|---|---|---|
| **API Root** | [http://127.0.0.1:8000/](http://127.0.0.1:8000/) | Browsable API overview with links to all endpoints |
| **Django Admin** | [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) | Admin dashboard (login with superuser) |
| **JWT Login / Obtain Token** | [http://127.0.0.1:8000/api/token/](http://127.0.0.1:8000/api/token/) | `POST` endpoint to obtain JWT access & refresh tokens |
| **JWT Token Refresh** | [http://127.0.0.1:8000/api/token/refresh/](http://127.0.0.1:8000/api/token/refresh/) | `POST` endpoint to refresh an expired access token |
| **Browsable API Auth** | [http://127.0.0.1:8000/api-auth/login/](http://127.0.0.1:8000/api-auth/login/) | Session-based login for browser API testing |

---

## Useful Commands

```powershell
# System check
docker compose exec web python manage.py check

# Run tests
docker compose exec web python manage.py test

# View real-time container logs
docker compose logs -f web

# Open a Django interactive shell
docker compose exec web python manage.py shell
```
