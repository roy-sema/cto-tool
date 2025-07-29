from rest_framework import permissions


class CanEditAttestationPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm("mvp.can_view_pull_request_scans")
