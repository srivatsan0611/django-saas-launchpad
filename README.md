# Django SaaS Launchpad

## Overview

**What it solves:**
- Boilerplate code for paid SaaS products
- Vendor lock-in with single payment provider
- Weeks rebuilding common SaaS features
- Multi-tenant organization management complexity
- Payment gateway integration from scratch

**How it solves:**
- Production-ready Django starter with batteries included
- Pluggable payment gateway abstraction layer
- Built-in multi-tenancy with org/team RBAC
- Razorpay integration ready out-of-box
- Switch payment providers in one line

**Example use case:**
You're building a project management SaaS. Clone this repo, configure Razorpay keys, and you instantly get user auth, organization management, subscription billing, and team invitations - launch your MVP in hours instead of weeks.

---

## Dev Setup Instructions

### Prerequisites
- Python 3.11+
- PostgreSQL (or SQLite for quick testing)
- Redis (for Celery background tasks)

### Quick Start

1. **Clone and enter project:**
```bash
git clone <repo-url>
cd django-saas-launchpad
```

2. **Create virtual environment:**
```bash
python3 -m venv saas_env
source saas_env/bin/activate  # On Windows: saas_env\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables:**
```bash
cp .env.example .env 
```

Add to `.env`:
```
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/saas_db  # Or sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0

# Razorpay (use test keys for development)
RAZORPAY_KEY_ID=rzp_test_your_key_here
RAZORPAY_KEY_SECRET=your_secret_here
RAZORPAY_WEBHOOK_SECRET=whsec_your_webhook_secret
DEFAULT_PAYMENT_GATEWAY=razorpay

# Email (console backend for local dev)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

5. **Run migrations:**
```bash
python manage.py migrate
```

6. **Create superuser:**
```bash
python manage.py createsuperuser
# Email: admin@saaslaunchpad.com
# Password: admin123
```

7. **Run development server:**
```bash
python manage.py runserver
```

8. **Run tests:**
```bash
# All tests
pytest

# Specific app tests
pytest accounts/tests/
pytest organizations/tests/
pytest billing/tests/

# With coverage
pytest --cov=. --cov-report=html
```


### Project Structure
```
django-saas-launchpad/
├── accounts/          # User auth, JWT, magic links
├── organizations/     # Multi-tenancy, teams, invitations
├── billing/           # Payment gateways, subscriptions
│   └── gateways/      # Pluggable payment providers
├── feature_flags/     # Feature toggles (planned)
├── analytics/         # Usage metrics (planned)
└── config/            # Django settings
```

---

**Note:** This is an active development project. More features (subscriptions, invoices, feature flags, analytics) coming soon.
