from django.urls import path

from .views import activateAccount, changeLanguage, changePassword, downloadPdf

app_name = 'common'

urlpatterns = [
    path('change-password/', changePassword, name='change-password'),
    path('change-language/', changeLanguage, name='change-language'),
    path('download-pdf/<int:user_id>/', downloadPdf, name='download-pdf'),
    path('activate/<uidb64>/<token>/', activateAccount, name='activate-account'),
]