from django.urls import path

from . import views

app_name = 'mail_parser'

urlpatterns = [
    path('inbound-email/', views.inbound_email_webhook, name='inbound_email_webhook'),
    path('review/<str:review_token>/', views.review_email, name='review_email'),
]