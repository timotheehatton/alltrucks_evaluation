from django.contrib.auth.models import AbstractUser
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255, default=None)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    cu_number = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} ({self.city}, {self.country})"


class User(AbstractUser):
    user_type = models.CharField(max_length=55, blank=True, null=True)
    language = models.CharField(max_length=2, choices=(('FR', 'French'), ('ES', 'Spanish')), default='FR')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    ct_number = models.CharField(max_length=20, null=True)


class Score(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    question_type = models.CharField(max_length=255)
    score = models.IntegerField()

    def __str__(self):
        return f"Score for user {self.user} is {self.score} for {self.question_type}"
