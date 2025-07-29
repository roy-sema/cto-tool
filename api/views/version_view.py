from rest_framework.response import Response
from rest_framework.views import APIView


class VersionView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        return Response({"version": request.version})
