# AMCAT - AllTrucks Mechanics Competency Assessment Test

A Django-based evaluation and training platform for AllTrucks mechanics, supporting multiple languages (FR, ES, EN) with quiz-based assessments across 8 technical categories.

## Prerequisites

- Python 3.8+
- pip
- PostgreSQL (for production) or SQLite (for development)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd alltrucks_evaluation
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the project root with the following variables:
   ```
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   
   # Database (optional - defaults to SQLite if not set)
   DATABASE_URL=sqlite:///db.sqlite3
   
   # Email configuration
   SENDGRID_API_KEY=your-sendgrid-api-key
   DEFAULT_FROM_EMAIL=noreply@alltrucks.com
   
   # Strapi CMS configuration
   STRAPI_BASE_URL=your-strapi-url
   STRAPI_API_TOKEN=your-strapi-api-token
   ```

5. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

6. **Load initial data (optional)**
   ```bash
   python manage.py loaddata fixtures/test_data.json
   ```

7. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

8. **Collect static files**
   ```bash
   python manage.py collectstatic --noinput
   ```

## Running the Application

1. **Start the development server**
   ```bash
   python manage.py runserver
   ```

2. **Access the application**
   - Main site: http://localhost:8000
   - Admin panel: http://localhost:8000/admin

## First Steps

1. Log in to the admin panel with your superuser credentials
2. Create a Company
3. Create users and assign them roles (Technician or Manager)
4. Technicians can take quizzes and view their statistics
5. Managers can oversee technicians in their company and generate reports

## Features

- **Multi-language support**: French, Spanish, and English
- **8 Technical categories**: Different quiz categories for comprehensive evaluation
- **Role-based access**: Technician, Manager, and Admin roles
- **Company management**: Organize users by company
- **Progress tracking**: Detailed statistics and performance metrics
- **PDF certificates**: Automatic generation for scores ≥ 80%
- **Progressive Web App**: Installable on mobile devices

## Development

### Running Tests
```bash
python manage.py test
```

### Making Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Debugging
- Check logs in the console
- Enable `DEBUG=True` in `.env` for detailed error pages
- Use Django's built-in debugging tools

## Deployment

The application is configured for Heroku deployment. See `Procfile` for the production server configuration.

## Support

For issues or questions, please contact the development team.