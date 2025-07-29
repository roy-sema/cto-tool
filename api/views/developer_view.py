from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Case, IntegerField, When
from django.db.models.functions import Lower
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from mvp.mixins import DecodePublicIdMixin
from mvp.models import Author
from mvp.serializers import AuthorSerializer


class DeveloperView(DecodePublicIdMixin, PermissionRequiredMixin, ListAPIView):
    permission_required = "mvp.can_view_ai_code_monitor"
    page_size = 50
    serializer_class = AuthorSerializer
    pagination_class = PageNumberPagination
    valid_ordering_fields = [
        "name",
        "code_ai_percentage",
        "code_ai_pure_percentage",
        "code_ai_blended_percentage",
    ]

    def get_queryset(self):
        public_id = self.kwargs.get("public_id")
        order_criteria = self.request.query_params.get("order", "name")
        order_key = order_criteria.lstrip("-")
        if order_key not in self.valid_ordering_fields:
            order_criteria = "name"

        group_id = self.decode_id(public_id)
        queryset = Author.objects.filter(
            organization=self.request.current_organization,
            group_id=group_id,
            linked_author__isnull=True,
        )
        if order_key != "name":
            queryset = queryset.annotate(
                num_lines=Case(
                    When(code_num_lines=0, then=1),
                    default=0,
                    num_lines=IntegerField(),
                )
            ).order_by("num_lines", order_criteria, Lower("name"))
        else:
            # Lower can't handle descending order, so we need to handle it separately
            queryset = queryset.order_by(Lower("name") if order_criteria == "name" else Lower("name").desc())
        return queryset

    def get(self, request, *args, **kwargs):
        paginator = self.pagination_class()
        paginator.page_size = self.page_size

        queryset = self.get_queryset()
        page = paginator.paginate_queryset(queryset, request)
        developers = self.get_serializer(page, many=True)

        response_data = {
            "count": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": (paginator.page.next_page_number() if paginator.page.has_next() else 0),
            "previous_page": (paginator.page.previous_page_number() if paginator.page.has_previous() else 0),
            "developers": developers.data,
        }

        return Response(response_data)
