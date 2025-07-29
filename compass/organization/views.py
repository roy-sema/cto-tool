from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from compass.organization.serializers import (
    OrganizationAuthorGroupSerializer,
    OrganizationRepositoryGroupSerializer,
    OrganizationUserSerializer,
)
from mvp.mixins import DecodePublicIdMixin
from mvp.models import AuthorGroup, CustomUser, RepositoryGroup


# TODO: reduce duplicated code
class OrganizationDeveloperGroupsView(DecodePublicIdMixin, PermissionRequiredMixin, ListAPIView):
    permission_required = "mvp.can_view_compass_organization_developer_groups"
    page_size = 50
    serializer_class = OrganizationAuthorGroupSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        organization = self.request.current_organization
        return AuthorGroup.objects.filter(organization=organization).order_by("name")

    def get(self, request, *args, **kwargs):
        paginator = self.pagination_class()
        paginator.page_size = self.page_size

        queryset = self.get_queryset()
        page = paginator.paginate_queryset(queryset, request)
        groups = self.get_serializer(page, many=True)

        response_data = {
            "count": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": (paginator.page.next_page_number() if paginator.page.has_next() else 0),
            "previous_page": (paginator.page.previous_page_number() if paginator.page.has_previous() else 0),
            "developer_groups": groups.data,
        }

        return Response(response_data)


class OrganizationRepositoryGroupsView(DecodePublicIdMixin, PermissionRequiredMixin, ListAPIView):
    permission_required = "mvp.can_view_compass_organization_repository_groups"
    page_size = 50
    serializer_class = OrganizationRepositoryGroupSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        organization = self.request.current_organization
        return RepositoryGroup.objects.filter(organization=organization).order_by("name")

    def get(self, request, *args, **kwargs):
        paginator = self.pagination_class()
        paginator.page_size = self.page_size

        queryset = self.get_queryset()
        page = paginator.paginate_queryset(queryset, request)
        groups = self.get_serializer(page, many=True)

        response_data = {
            "count": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": (paginator.page.next_page_number() if paginator.page.has_next() else 0),
            "previous_page": (paginator.page.previous_page_number() if paginator.page.has_previous() else 0),
            "repository_groups": groups.data,
        }

        return Response(response_data)


class OrganizationUsersView(DecodePublicIdMixin, PermissionRequiredMixin, ListAPIView):
    permission_required = "mvp.can_view_compass_organization_users"
    page_size = 50
    serializer_class = OrganizationUserSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        organization = self.request.current_organization
        return CustomUser.objects.filter(organization=organization)

    def get(self, request, *args, **kwargs):
        paginator = self.pagination_class()
        paginator.page_size = self.page_size

        queryset = self.get_queryset()
        page = paginator.paginate_queryset(queryset, request)
        users = self.get_serializer(page, many=True)

        response_data = {
            "count": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": (paginator.page.next_page_number() if paginator.page.has_next() else 0),
            "previous_page": (paginator.page.previous_page_number() if paginator.page.has_previous() else 0),
            "users": users.data,
        }

        return Response(response_data)
