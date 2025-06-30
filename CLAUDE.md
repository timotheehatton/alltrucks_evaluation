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

# Load test data
python manage.py loaddata fixtures/test_data.json

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Collect static files
python manage.py collectstatic
```

### Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test users
python manage.py test technician
python manage.py test manager
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
├── models.py   # User, Company, Role models
├── forms.py    # Registration, login forms
└── views.py    # Auth views, user management

technician/     # Technician features
├── quiz.py     # Quiz logic, scoring system
├── stats.py    # Performance statistics
└── views.py    # Technician dashboard, quiz interface

manager/        # Manager features
├── views/      # Modular view organization
│   ├── dashboard.py
│   ├── reports.py
│   └── technicians.py
└── reports.py  # PDF certificate generation

common/         # Shared functionality
├── password_reset.py  # Custom password reset flow
├── email_utils.py     # SendGrid integration
└── language.py        # Language switching
```

### Quiz System Architecture
- 8 technical categories stored in `Question` and `Category` models
- Questions fetched from Strapi CMS API (configurable)
- Scoring: 10 points per correct answer, -5 for incorrect
- Results stored in `QuizScore` model with detailed question tracking
- PDF certificates generated for scores ≥ 80%

### Frontend Structure
- Server-rendered Django templates with progressive enhancement
- Materialize CSS framework
- ES6 modules for interactive components:
  - `quiz.js`: Quiz timer, navigation, answer handling
  - `stats.js`: Chart.js visualizations
  - `language.js`: Client-side language switching
  - `pwa.js`: Service worker registration

### Email System
- SendGrid for transactional emails
- Templates in `templates/emails/`
- Custom password reset flow with 4-hour expiry tokens
- Multi-language email support

### Configuration
- Environment variables (`.env` file):
  - `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
  - `DATABASE_URL` (PostgreSQL in production)
  - `SENDGRID_API_KEY`, `DEFAULT_FROM_EMAIL`
  - `STRAPI_BASE_URL`, `STRAPI_API_TOKEN`
- Static files served by WhiteNoise in production
- Media files for quiz images

### Deployment
- Configured for Heroku deployment
- `Procfile`: Uses Gunicorn WSGI server
- PostgreSQL database in production
- Static files collected and served by WhiteNoise

## Important Patterns

### View Organization
Manager views are modularized in `manager/views/` for better organization. Each module exports its views which are imported in `manager/views/__init__.py`.

### Form Handling
Custom forms in each app extend Django forms with Materialize CSS styling and additional validation.

### Multi-language Support
- `LocaleMiddleware` for language detection
- Translation files in `locale/` directory
- Language stored in session and user preferences

### Security
- CSRF protection enabled
- Secure password reset tokens
- Login required decorators on protected views
- Company-based data isolation

### Database Models
- Soft delete pattern used for some models
- Company-based multi-tenancy
- Detailed audit fields (created_at, updated_at)