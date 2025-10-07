# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the AMCAT (AllTrucks Mechanics Competency Assessment Test) platform - a Django 5.1.1 web application for evaluating and training AllTrucks mechanics. The application supports multiple languages (FR, ES, EN) and provides quiz-based assessments across 8 technical categories.

## Key Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Load test data (options: complete_data.json, only_admin.json, only_users.json)
python manage.py loaddata fixtures/complete_data.json

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Collect static files
python manage.py collectstatic --noinput
```

### Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test users
python manage.py test technician
python manage.py test manager
python manage.py test common

# Run specific test method
python manage.py test users.tests.TestClassName.test_method_name
```

### Database
```bash
# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Database shell
python manage.py dbshell
```

## Architecture Overview

### User Roles and Permissions
- **Technician**: Takes quizzes, views stats, manages account
- **Manager**: Oversees technicians in their company, views reports
- **Admin**: Full system access via Django admin

### Core Apps Structure
```
users/          # Custom User model, authentication, company management
├── models.py   # User, Company, Score models
├── forms.py    # Registration, login forms
├── decorators.py  # @technician_required, @manager_required
└── views/      # Auth views, user management

technician/     # Technician features
└── views/      # Modular view organization
    ├── quiz.py     # Quiz logic, Strapi integration, scoring
    ├── stats.py    # Performance statistics
    └── account.py  # Account management

manager/        # Manager features
└── views/      # Modular view organization
    ├── stats.py        # Manager dashboard
    ├── details.py      # Technician details
    ├── technicians.py  # Technician list
    └── account.py      # Manager account management

common/         # Shared functionality
├── views/      # Shared views
│   ├── lost_password.py    # Password reset request
│   ├── reset_password.py   # Password reset confirmation
│   ├── change_password.py  # Change password
│   ├── change_language.py  # Language switching
│   ├── download_pdf.py     # PDF certificate generation
│   └── activate_account.py # Account activation
└── useful/     # Utility modules
    ├── strapi.py  # Strapi CMS API integration
    └── email.py   # SendGrid email service
```

### Quiz System Architecture
- 8 technical categories: diagnostic, electricity, engine_exhaust, engine_injection, general_mechanic, powertrain, trailer_braking_system, truck_air_braking_system
- Questions fetched from Strapi CMS API via `common/useful/strapi.py`
- Question counts per category defined in `settings.QUESTION_NUMBER`
- Scoring: 1 point per correct answer per category
- Results stored in `Score` model (users/models.py) with category breakdown
- PDF certificates generated via `common/views/download_pdf.py`

### Frontend Structure
- Server-rendered Django templates with progressive enhancement
- Materialize CSS framework
- ES6 modules in `static/js/quiz/modules/`:
  - `quizSession.js`: Quiz timer, state management
  - `quizQuestion.js`: Question rendering and navigation
  - `quizService.js`: API communication
  - `quizUi.js`: UI updates and interactions
  - `storage.js`: LocalStorage persistence
  - `constants.js`: Shared constants
  - `timeUtils.js`: Time formatting utilities
- Main entry point: `static/js/quiz/main.js`

### Email System
- SendGrid integration via `common/useful/email.py`
- HTML email template in `staticfiles/mail/template.html`
- Custom password reset flow via `common/views/lost_password.py` and `reset_password.py`
- Multi-language support based on user preferences

### Configuration
- Environment variables (`.env` file):
  - `SECRET_KEY`, `DEBUG`, `ENV` (set to 'prod' for production)
  - `SITE_DOMAIN`
  - `SENDGRID_API_KEY`
  - `STRAPI_URL`, `STRAPI_EMAIL_TOKEN`
  - `CONTENT_CACHE_DURATION` (in minutes)
- Database: SQLite (development), PostgreSQL (production via `ENV=prod`)
- Static files served by WhiteNoise with compression
- Strapi content cached using Django's cache framework

### Deployment
- Configured for Heroku deployment
- `Procfile`: Uses Gunicorn WSGI server
- PostgreSQL database in production
- Static files collected and served by WhiteNoise

## Important Patterns

### View Organization
Both manager and technician views are modularized in their respective `views/` directories. Each module exports its views which are imported in `views/__init__.py`. This pattern improves maintainability and code organization.

### Form Handling
Custom forms in each app extend Django forms with Materialize CSS styling and additional validation. Forms are defined in `views/forms.py` within each app.

### Multi-language Support
- `django.middleware.locale.LocaleMiddleware` for language detection
- Supported languages: French (FR), Spanish (ES), English (EN)
- User language preference stored in `User.language` field
- Language switching via `common/views/change_language.py`
- Content fetched from Strapi CMS based on user's language preference

### Security
- CSRF protection enabled
- Custom `LoginRequiredMiddleware` in `alltrucks_training/middleware.py` redirects root to login
- Role-based access control via `@technician_required` and `@manager_required` decorators
- Company-based data isolation (managers only see their company's technicians)
- SSL redirect enabled in production (`ENV=prod`)

### Database Models
- Custom User model (`users.User`) extends `AbstractUser` with `company`, `language`, `user_type`, `ct_number`
- `Company` model with `name`, `city`, `country`, `cu_number`
- `Score` model tracks quiz results per user, category, and date
- Company-based multi-tenancy for data isolation
- Custom `USERNAME_FIELD = 'email'` for authentication

### URL Structure
- Root `/` redirects to appropriate dashboard based on user type
- `/technician/*` - Technician features (quiz, stats, account)
- `/manager/*` - Manager features (stats, technician management)
- `/common/*` - Shared features (password reset, language, PDFs)
- `/login/`, `/logout/` - Authentication
- `/admin/` - Django admin (custom admin site)