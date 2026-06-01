from django.contrib.auth.models import AbstractUser
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255, default=None)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, choices=(
        ('FR', 'FR'),
        ('ES', 'ES'),
        ('PL', 'PL'),
        ('DE', 'DE'),
        ('IT', 'IT'),
    ), default='FR')
    cu_number = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} ({self.city}, {self.country})"


class User(AbstractUser):
    user_type = models.CharField(max_length=55, blank=True, null=True)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, null=True, blank=True)
    ct_number = models.CharField(max_length=20, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    email = models.EmailField(unique=True)

    @property
    def language(self):
        """Language is no longer stored — it's derived from the user's
        company country. A user without a company (e.g. superuser) falls
        back to FR so any Strapi locale lookup still gets a sensible value.
        Returns the 2-letter ISO code in upper case to match the legacy
        field semantics; existing callers that do `.language.lower()`
        continue to work unchanged.
        """
        if self.company_id and self.company.country:
            return self.company.country
        return 'FR'


class Score(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField()
    question_type = models.CharField(max_length=255)
    score = models.IntegerField()

    def __str__(self):
        return f"Score for user {self.user} is {self.score} for {self.question_type}"
