from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    LogoutView,
    MeView,
    ChangePasswordView,
    SetPasswordView,
    InviteAcceptView,
    InviteCheckView,
    AdminCreateUserView,
    AdminUsersListView,
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('set-password/', SetPasswordView.as_view(), name='set_password'),
    path('invite/accept/', InviteAcceptView.as_view(), name='invite_accept'),
    path('invite/check/<str:token>/', InviteCheckView.as_view(), name='invite_check'),
    path('admin/create-user/', AdminCreateUserView.as_view(), name='admin_create_user'),
    path('admin/users/', AdminUsersListView.as_view(), name='admin_users_list'),
]
