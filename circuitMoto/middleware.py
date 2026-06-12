from django.urls import reverse
from django.utils.cache import patch_cache_control


class NoCacheHtmlMiddleware:
    """Force les pages HTML à être revalidées pour récupérer les nouveaux assets hashés."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get("Content-Type", "")

        if response.status_code == 200 and content_type.startswith("text/html"):
            patch_cache_control(response, no_cache=True, must_revalidate=True, max_age=0)
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response


class ForcePasswordChangeMiddleware:
    """Si must_change_password=True -> redirige vers la page de changement, sauf pour cette page et /logout."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            flags = getattr(user, "flags", None)
            if flags and flags.must_change_password:
                allowed = {
                    reverse("force_password_change"),
                    reverse("logout"),
                }
                # autorise aussi les assets statiques
                if not request.path.startswith("/static/") and request.path not in allowed:
                    from django.shortcuts import redirect
                    return redirect("force_password_change")
        return self.get_response(request)
