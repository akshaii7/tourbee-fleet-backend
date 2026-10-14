from rest_framework import permissions

class IsAdminUserRole(permissions.BasePermission):
    """
    Allows access only to Admin / Fleet Owner users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)

class IsDriverUserRole(permissions.BasePermission):
    """
    Allows access only to Driver users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_driver)

class IsOwnerDriverOrAdmin(permissions.BasePermission):
    """
    Allows Drivers to access only their own data, and Admins to access all data.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        # If object has user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        # If object is Driver and user has driver
        if hasattr(obj, 'driver'):
            return hasattr(request.user, 'driver_profile') and obj.driver == request.user.driver_profile
        return False
