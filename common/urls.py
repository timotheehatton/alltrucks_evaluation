from django.urls import path
from .views import changePassword, changeLanguage, downloadPdf


app_name = 'common'

urlpatterns = [
    path('change-password/', changePassword, name='change-password'),
    path('change-language/', changeLanguage, name='change-language'),
    path('download-pdf/<int:user_id>/', downloadPdf, name='download-pdf')
]