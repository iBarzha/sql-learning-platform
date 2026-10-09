import string
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from PIL import Image

from .models import Invite


def login_email_key(group, request) -> str:
    """Rate-limit key: the account being tried. JSON bodies never reach request.POST,
    so django-ratelimit's built-in 'post:email' key would be empty for every request."""
    try:
        email = request.data.get('email') if hasattr(request, 'data') else None
    except Exception:  # noqa: BLE001 - malformed body; fall back to the client address
        email = None
    return (str(email or '').strip().lower()) or request.META.get('REMOTE_ADDR', '')
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    SetPasswordSerializer,
    InviteAcceptSerializer,
    AdminCreateUserSerializer,
    AdminUserListSerializer,
    AdminUserUpdateSerializer,
)
from config.permissions import IsAdmin
from courses.models import Course, Enrollment

User = get_user_model()


def generate_temporary_password(length: int = 10) -> str:
    return ''.join(
        secrets.choice(string.ascii_letters + string.digits)
        for _ in range(length)
    )


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    @method_decorator(ratelimit(key='ip', rate='5/h', method='POST'))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user, context={'request': request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    # A whole class logs in from one NAT address at the start of a lesson, so the
    # per-IP limit must allow a room of students; brute force is bounded per account.
    @method_decorator(ratelimit(key='ip', rate='60/m', method='POST'))
    @method_decorator(ratelimit(key=login_email_key, rate='10/m', method='POST'))
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

        # Tokens are issued here, not by SimpleJWT's own view, so its
        # UPDATE_LAST_LOGIN setting never fires; the admin dashboard relies on this.
        update_last_login(None, user)

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user, context={'request': request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'Successfully logged out'})
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            pass  # Token already blacklisted or invalid
        return Response({'detail': 'Successfully logged out'})


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
    MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

    def get(self, request):
        return Response(UserSerializer(request.user, context={'request': request}).data)

    def patch(self, request):
        avatar = request.FILES.get('avatar')
        if avatar:
            if avatar.content_type not in self.ALLOWED_IMAGE_TYPES:
                return Response(
                    {'avatar': 'Only JPG, PNG, WebP, and GIF images are allowed.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if avatar.size > self.MAX_AVATAR_SIZE:
                return Response(
                    {'avatar': 'Image size must not exceed 2MB.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                img = Image.open(avatar)
                img.verify()
                avatar.seek(0)
            except Exception:
                return Response(
                    {'avatar': 'File is not a valid image.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = UserSerializer(
            request.user, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key='user', rate='5/m', method='POST'))
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

    @method_decorator(ratelimit(key='user', rate='5/m', method='POST'))
    def post(self, request):
        if not request.user.must_change_password:
            return Response(
                {'detail': 'Password change not required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        if serializer.validated_data.get('first_name'):
            user.first_name = serializer.validated_data['first_name']
        if serializer.validated_data.get('last_name'):
            user.last_name = serializer.validated_data['last_name']
        user.must_change_password = False
        user.save()

        return Response({'detail': 'Password set successfully'})


class InviteAcceptView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST'))
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

        with transaction.atomic():
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
            'user': UserSerializer(user, context={'request': request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class InviteCheckView(APIView):
    """Check if an invitation token is valid."""
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


class AdminCreateUserView(APIView):
    """Admin-only: create a new user with a random password."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser and request.user.role != 'admin':
            return Response(
                {'detail': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = AdminCreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        password = generate_temporary_password()

        course_id = serializer.validated_data.get('course_id')
        if course_id:
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return Response(
                    {'detail': 'Course not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            course = None

        with transaction.atomic():
            user = User.objects.create_user(
                email=serializer.validated_data['email'],
                password=password,
                role=serializer.validated_data['role'],
                must_change_password=True,
                first_name='',
                last_name='',
            )

            if course:
                Enrollment.objects.create(
                    student=user,
                    course=course,
                    status='active',
                )

        return Response({
            'user': AdminUserListSerializer(user, context={'request': request}).data,
            'password': password,
        }, status=status.HTTP_201_CREATED)


class AdminUsersListView(APIView):
    """Admin-only: list users with search/filter/pagination."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser and request.user.role != 'admin':
            return Response(
                {'detail': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )

        queryset = User.objects.all().order_by('-created_at')

        role = request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )

        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page = 1
            page_size = 20
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        users = queryset[start:end]

        next_url = None
        previous_url = None
        if end < total:
            next_url = f'?page={page + 1}&page_size={page_size}'
        if page > 1:
            previous_url = f'?page={page - 1}&page_size={page_size}'

        return Response({
            'count': total,
            'next': next_url,
            'previous': previous_url,
            'results': AdminUserListSerializer(
                users, many=True, context={'request': request}
            ).data,
        })


class AdminUserDetailView(APIView):
    """Admin-only: change a user's role / active flag, or delete the user."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def _get_user(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None

    def patch(self, request, pk):
        user = self._get_user(pk)
        if user is None:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if user.pk == request.user.pk:
            if 'is_active' in data and not data['is_active']:
                return Response(
                    {'detail': 'You cannot deactivate your own account'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if 'role' in data and data['role'] != 'admin':
                return Response(
                    {'detail': 'You cannot remove your own admin role'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if 'role' in data:
            user.role = data['role']
        if 'is_active' in data:
            user.is_active = data['is_active']
        user.save(update_fields=['role', 'is_active', 'updated_at'])

        return Response(AdminUserListSerializer(user, context={'request': request}).data)

    def delete(self, request, pk):
        user = self._get_user(pk)
        if user is None:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if user.pk == request.user.pk:
            return Response(
                {'detail': 'You cannot delete your own account'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Courses cascade on instructor deletion; refuse rather than wipe them silently.
        owned_courses = list(Course.objects.filter(instructor=user).values_list('title', flat=True))
        if owned_courses:
            return Response(
                {
                    'detail': 'This user teaches courses. Reassign or delete them first.',
                    'courses': owned_courses,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminResetPasswordView(APIView):
    """Admin-only: issue a new temporary password the user must change on login."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        password = generate_temporary_password()
        user.set_password(password)
        user.must_change_password = True
        user.save(update_fields=['password', 'must_change_password', 'updated_at'])

        return Response({
            'user': AdminUserListSerializer(user, context={'request': request}).data,
            'temporary_password': password,
        })
