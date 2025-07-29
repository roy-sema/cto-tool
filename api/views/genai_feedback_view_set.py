import hashlib

from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from api.models import GenAIFeedback
from api.serializers import GenAIFeedbackSerializer
from mvp.mixins import DecodePublicIdMixin


class GenAIFeedbackViewSet(ModelViewSet, DecodePublicIdMixin):
    permission_classes = [IsAuthenticated & TokenHasReadWriteScope]
    serializer_class = GenAIFeedbackSerializer
    queryset = GenAIFeedback.objects.all()
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file = request.data.get("file")
        content = file.file.read()
        file.file.seek(0)
        content_hash = hashlib.sha256(content).hexdigest()

        gen_ai_feedback = GenAIFeedback.objects.filter(
            user=request.user,
            content_hash=content_hash,
            code_line_start=request.data["code_line_start"],
            code_line_end=request.data["code_line_end"],
            status=request.data["status"],
            file_path=request.data["file_path"],
        ).first()

        request.content_hash = content_hash

        if gen_ai_feedback:
            serializer.instance = gen_ai_feedback
            serializer.partial = kwargs.pop("partial", False)
            status_code = status.HTTP_200_OK
        else:
            status_code = status.HTTP_201_CREATED

        gen_ai_feedback = serializer.save()

        response = Response(serializer.data, status=status_code)
        response.headers = self.get_success_headers(serializer.data)
        response.data["id"] = gen_ai_feedback.public_id()
        response.data.pop("file")

        return response
