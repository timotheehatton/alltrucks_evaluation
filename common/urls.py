from django.urls import path

from .views import activateAccount, changeLanguage, changePassword, downloadPdf, lostPassword, resetPassword

app_name = 'common'

urlpatterns = [
    path('change-password/', changePassword, name='change-password'),
    path('change-language/', changeLanguage, name='change-language'),
    path('download-pdf/<int:user_id>/', downloadPdf, name='download-pdf'),
    path('activate/<uidb64>/<token>/', activateAccount, name='activate-account'),
    path('lost-password/', lostPassword, name='lost-password'),
    path('reset/<uidb64>/<token>/', resetPassword, name='reset-password'),
]