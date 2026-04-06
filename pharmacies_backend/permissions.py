from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    allowed_roles: set[str] = set()

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        return user.role in self.allowed_roles


class IsAdmin(RolePermission):
    allowed_roles = {'admin'}


class IsPharmacy(RolePermission):
    allowed_roles = {'pharmacy'}


class IsDriver(RolePermission):
    allowed_roles = {'driver'}


class IsCustomer(RolePermission):
    allowed_roles = {'customer'}


class IsAdminOrPharmacy(RolePermission):
    allowed_roles = {'admin', 'pharmacy'}
