from django.http import JsonResponse


def health_check(request):
    # You can add additional health check logic here if needed
    return JsonResponse({"status": "ok"})
