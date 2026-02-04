from rest_framework import permissions


class IsInstructor(permissions.BasePermission):
    """Only allow instructors and admins."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_instructor


class IsStudent(permissions.BasePermission):
    """Only allow students."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_student


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Only allow owners to edit."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.instructor == request.user


class IsEnrolledOrInstructor(permissions.BasePermission):
    """Allow access to enrolled students or the course instructor."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if hasattr(obj, 'instructor') and obj.instructor == user:
            return True
        if hasattr(obj, 'course'):
            course = obj.course
        else:
            course = obj

        if user.is_instructor:
            return course.instructor == user

        return course.enrollments.filter(student=user, status='active').exists()


class IsCourseInstructor(permissions.BasePermission):
    """Only allow the course instructor."""

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'course'):
            return obj.course.instructor == request.user
        return obj.instructor == request.user


class IsSubmissionOwner(permissions.BasePermission):
    """Only allow the submission owner or course instructor."""

    def has_object_permission(self, request, view, obj):
        if obj.student == request.user:
            return True
        return obj.assignment.course.instructor == request.user
