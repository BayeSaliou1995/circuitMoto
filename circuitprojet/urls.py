# circuitprojet/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from circuitMoto.views import home
from django.views.i18n import JavaScriptCatalog

from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from circuitMoto.sitemaps import CircuitSitemap

# Déclare les handlers globaux (Django les résout au runtime)
handler400 = "circuitMoto.errors.bad_request"
handler403 = "circuitMoto.errors.permission_denied"
handler404 = "circuitMoto.errors.page_not_found"
handler500 = "circuitMoto.errors.server_error"

sitemaps = {
    "circuits": CircuitSitemap,
}

urlpatterns = [
    path("administration/", admin.site.urls),

    # Endpoint Django pour changer la langue (POST)
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),

    # Endpoint pour le sitemap XML
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain"), name="robots"),
]

# URLs “visiteurs” multilingues
urlpatterns += i18n_patterns(
    path("", home, name="home"),
    path("", include("circuitMoto.urls")),
    prefix_default_language=False,  # /en/… pour EN, rien pour FR
)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Routes de prévisualisation pratique (à garder ou retirer)
def _preview(viewfunc, status_code):
    def _inner(request, *args, **kwargs):
        # appelle le handler pour voir le rendu final
        return viewfunc(request, exception=None) if status_code != 500 else viewfunc(request)
    return _inner

from circuitMoto import errors as error_views
from django.core.exceptions import PermissionDenied

def boom(request):
    raise Exception("Crash test 500")

def test_403(request):
    raise PermissionDenied("Test 403")

urlpatterns += [
    path("__preview/errors/400/", _preview(error_views.bad_request, 400)),
    path("__preview/errors/403/", test_403),
    path("__preview/errors/404/", _preview(error_views.page_not_found, 404)),
    path("__preview/errors/500/", boom),
]