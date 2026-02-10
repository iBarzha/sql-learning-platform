from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Invite
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    SetPasswordSerializer,
    InviteAcceptSerializer,
)
from courses.models import Enrollment

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {'detail': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'detail': 'Account is disabled'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'detail': 'Successfully logged out'})
        except Exception:
            return Response({'detail': 'Successfully logged out'})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.must_change_password = False
        request.user.save()

        return Response({'detail': 'Password changed successfully'})


class SetPasswordView(APIView):
    """For users who must change their password."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.must_change_password:
            return Response(
                {'detail': 'Password change not required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.must_change_password = False
        request.user.save()

        return Response({'detail': 'Password set successfully'})


class InviteAcceptView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InviteAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']

        try:
            invite = Invite.objects.get(token=token, is_used=False)
        except Invite.DoesNotExist:
            return Response(
                {'detail': 'Invalid or expired invitation'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if invite.expires_at < timezone.now():
            return Response(
                {'detail': 'Invitation has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=invite.email).exists():
            return Response(
                {'detail': 'User with this email already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            email=invite.email,
            password=serializer.validated_data['password'],
            role=invite.role,
            first_name=serializer.validated_data.get('first_name', ''),
            last_name=serializer.validated_data.get('last_name', ''),
        )

        invite.is_used = True
        invite.save()

        if invite.course:
            Enrollment.objects.create(student=user, course=invite.course)

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class InviteCheckView(APIView):
    """Check if an invitation token is valid."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invite = Invite.objects.get(token=token, is_used=False)
        except Invite.DoesNotExist:
            return Response(
                {'valid': False, 'detail': 'Invalid invitation'},
                status=status.HTTP_404_NOT_FOUND
            )

        if invite.expires_at < timezone.now():
            return Response(
                {'valid': False, 'detail': 'Invitation has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'valid': True,
            'email': invite.email,
            'role': invite.role,
            'course': invite.course.title if invite.course else None,
        })
