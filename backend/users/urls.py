from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    ChangePasswordView,
    SetPasswordView,
    InviteAcceptView,
    InviteCheckView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('set-password/', SetPasswordView.as_view(), name='set_password'),
    path('invite/accept/', InviteAcceptView.as_view(), name='invite_accept'),
    path('invite/check/<str:token>/', InviteCheckView.as_view(), name='invite_check'),
]
