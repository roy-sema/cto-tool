from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.serializers import CurrentUserSerializer
from mvp.models import CustomUser


class CurrentUserView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CurrentUserSerializer
    queryset = CustomUser.objects.filter(is_active=True)

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        initials = request.data.get("initials")
        first_name = request.data["first_name"]
        last_name = request.data["last_name"]
        initials = initials or CustomUser.generate_initials_from_names(first_name, last_name)

        data = {
            "initials": initials.upper(),
            "first_name": first_name,
            "last_name": last_name,
            "email": request.data["email"],
        }
        profile_image = request.data.get("profile_image")
        if profile_image:
            data["profile_image"] = profile_image
            data["profile_image_thumbnail"] = profile_image

        serializer = self.get_serializer(request.user, data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)
