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
- **Python 3.12** (required)
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
python3.12 -m venv saas_env
source saas_env/bin/activate  # On Windows: saas_env\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up pre-commit hooks:**
```bash
pre-commit install
```

5. **Set up environment variables:**
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

6. **Run migrations:**
```bash
python manage.py migrate
```

7. **Create superuser:**
```bash
python manage.py createsuperuser
# Email: admin@saaslaunchpad.com
# Password: admin123
```

8. **Run development server:**
```bash
python manage.py runserver
```

9. **Run tests:**
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

## Security Scanning

Automated security checks run on every PR:
- **Secret detection** (Gitleaks, TruffleHog)
- **Dependency vulnerabilities** (Safety, pip-audit)
- **SAST** (Bandit, Semgrep)
- **Code quality** (Ruff, Black, Pylint, Radon)

**Install Gitleaks (one-time):**
```bash
cd /tmp
wget https://github.com/gitleaks/gitleaks/releases/download/v8.18.0/gitleaks_8.18.0_linux_x64.tar.gz
tar -xzf gitleaks_8.18.0_linux_x64.tar.gz
mkdir -p ~/bin
mv gitleaks ~/bin/
rm gitleaks_8.18.0_linux_x64.tar.gz
```

**Run locally:**
```bash
~/bin/gitleaks detect --config .gitleaks.toml
safety check --file requirements.txt
bandit -r . -ll -x './saas_env/*,./venv/*,./tests/*'
radon cc . -a --total-average
```

**Config files:** `.gitleaks.toml`, `.bandit`, `.pylintrc`

---


## Pre-commit Hooks Usage Guide


### Quick Start fro first time set-up

1. **Install pre-commit** (if not already installed):
   ```bash
   pip install pre-commit
   ```

2. **Install the git hooks**:
   ```bash
   pre-commit install
   ```

   This installs hooks that will run automatically on every commit.

3. **Test the setup**:
   ```bash
   pre-commit run --all-files
   ```

   This runs all hooks on all files to ensure everything is working.

#### Daily Usage

Once installed, the hooks run automatically when you commit:

```bash
git add .
git commit -m "Your commit message"
# Hooks run automatically here
```

If any hook fails, fix the issues and commit again. The hooks will re-run.




#### Bypassing Hooks (When Needed)

If you need to bypass hooks (not recommended):

```bash
git commit --no-verify -m "Emergency commit"
git push --no-verify
```

**Warning**: Only bypass hooks when absolutely necessary. Security checks are important!

---

### Pre-commit Tools Overview

### Code Quality Tools

#### 1. **Black** - Code Formatter
- **What it does**: Automatically formats Python code to a consistent style
- **Config**: `pyproject.toml`
- **Auto-fixes**: Yes (reformats code automatically)
- **Line length**: 88 characters
- **Target**: Python 3.11

#### 2. **Ruff** - Fast Linter & Formatter
- **What it does**:
  - Lints code for errors (pycodestyle, pyflakes)
  - Formats code (alternative to Black)
  - Sorts imports
- **Config**: `pyproject.toml`
- **Auto-fixes**: Yes (safe fixes only)
- **Rules enabled**:
  - `E`: pycodestyle errors
  - `F`: pyflakes
  - `W`: warnings
  - `I`: import sorting

#### 3. **Pylint** - Code Analyzer
- **What it does**: Deep code analysis for bugs, code smells, and style issues
- **Config**: `.pylintrc`
- **Auto-fixes**: No (reports issues only)
- **Ignores**: migrations, venv, tests
- **Disabled rules**: Docstrings, naming conventions, some Django-specific patterns

#### 4. **Pyright** - Type Checker
- **What it does**: Static type checking for Python
- **Config**: Uses project defaults
- **Auto-fixes**: No (reports type errors only)

### Security Tools

#### 5. **Bandit** - Security Linter
- **What it does**: Scans for common security issues in Python code
- **Config**: `bandit.yml`
- **Severity**: HIGH
- **Confidence**: HIGH
- **Excludes**: tests, venv, .venv

#### 6. **Gitleaks** - Secret Detection
- **What it does**: Detects hardcoded secrets, API keys, passwords in your code
- **Config**: `.gitleaks.toml`, `.gitleaksignore`
- **Auto-fixes**: No (blocks commit if secrets found)
- **Scans**: Only changed files (diff between HEAD~1 and HEAD)
- **Custom rules**: Razorpay keys, Django SECRET_KEY, AWS keys
- **Ignored files**: `.secrets.baseline`, test files, venv

#### 7. **detect-secrets** - Alternative Secret Scanner
- **What it does**: Another tool for detecting secrets
- **Config**: `.detect-secrets.yaml`, `.secrets.baseline`
- **Auto-fixes**: No
- **Baseline**: Uses `.secrets.baseline` to track known false positives
- **Excludes**: tests, venv, cache directories

---

### Common Issues






### Issue: Handling False Positive Secrets

If gitleaks or detect-secrets flags something that's not actually a secret:

**For Gitleaks:**
1. Get the fingerprint from the error message
2. Add it to `.gitleaksignore`:
   ```bash
   echo "fingerprint:file:rule:line" >> .gitleaksignore
   ```
3. Commit the change

**For detect-secrets:**
1. Update the baseline:
   ```bash
   detect-secrets scan --update .secrets.baseline
   ```


### Issue: Bandit Finding False Positives

**Problem**: Bandit flags code that's safe.

**Solutions**:
1. **Add inline ignore**:
   ```python
   # nosec B601  # Bandit ignore for this line
   subprocess.run(command)
   ```

2. **Update bandit.yml** to exclude specific paths or tests

### Issue: Pylint Complaining About Django Code

**Problem**: Pylint doesn't understand Django patterns.

**Solution**: Already configured in `.pylintrc` - Django-specific rules are disabled. If you see new issues, they may be legitimate.

### Issue: Secrets Detected in Test Files

**Problem**: Gitleaks/detect-secrets flag test data.

**Solutions**:
1. **Already configured**: Test directories are in allowlists
2. **If still flagged**: Add specific fingerprint to ignore files
3. **For detect-secrets**: Update baseline with `detect-secrets scan --update .secrets.baseline`

### Issue: Ruff and Black Conflicts

**Problem**: Ruff and Black format code differently.

**Solution**: They're configured to be compatible. If conflicts occur:
1. Run Black first: `black .`
2. Then Ruff: `ruff format .`
3. Or use Ruff format only (it's faster)

---

## Manual Execution

### Run All Hooks on All Files

```bash
pre-commit run --all-files
```

### Run Specific Hook

```bash
# Run only Black
pre-commit run black --all-files

# Run only Bandit
pre-commit run bandit --all-files

# Run only Gitleaks
pre-commit run gitleaks --all-files
```

### Run on Specific Files

```bash
pre-commit run --files accounts/views.py organizations/models.py
```



### Run Individual Tools Manually

```bash
# Black
black .

# Ruff (lint)
ruff check .

# Ruff (format)
ruff format .

# Ruff (fix)
ruff check --fix .

# Pylint
pylint --rcfile=.pylintrc accounts/

# Bandit
bandit -c bandit.yml -r .

# Gitleaks
gitleaks detect --source . --config .gitleaks.toml --gitleaks-ignore-path .gitleaksignore

# detect-secrets
detect-secrets scan --baseline .secrets.baseline

# Pyright
pyright .
```

---





### PR Checks

#### Blocking (PR Fails)

Secret Detection
- TruffleHog: Verified secrets
- Gitleaks: Any secrets
Dependency Vulnerabilities
- Safety: ANY vulnerabilities
- pip-audit: ANY vulnerabilities
Code Security (SAST)
- Bandit: Medium/High severity issues (-ll flag)
- Semgrep: Any security findings

#### Non Blocking (Reports)

Code Quality
- Ruff: Code style issues
- Black: Formatting issues
- Pylint: Code smells
- Radon: Complexity metrics

---

**Note:** This is an active development project. More features (subscriptions, invoices, feature flags, analytics) coming soon.
