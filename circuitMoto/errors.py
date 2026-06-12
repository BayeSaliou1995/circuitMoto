# circuitMoto/errors.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import requires_csrf_token

def _want_json(request):
    acc = (request.headers.get("accept") or "").lower()
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in acc
        or "text/json" in acc
    )

def _payload(code, title, message, request):
    return {
        "ok": False,
        "error": {
            "code": code,
            "title": title,
            "message": message,
            "path": getattr(request, "path", ""),
        },
        "support": {
            "name": "Baye Saliou DIAW",
            "email": "diawbayesaliou463@gmail.com",
        }
    }

def _render(request, template_name, status, title, message, extra_ctx=None):
    if _want_json(request):
        return JsonResponse(_payload(status, title, message, request), status=status)

    ctx = {
        "code": status,
        "title": title,
        "message": message,
        "request_path": getattr(request, "path", ""),

        # ✅ Infos support (HTML)
        "support": {
            "team": "Équipe support",
            "dev_name": "Baye Saliou DIAW",
            "email": "diawbayesaliou463@gmail.com",
            "hint": "Si le problème persiste, contactez l’équipe support en indiquant le code d’erreur et l’URL."
        }
    }
    if extra_ctx:
        ctx.update(extra_ctx)
    return render(request, template_name, ctx, status=status)

def bad_request(request, exception=None):
    return _render(
        request, "400.html", 400,
        "Requête invalide",
        "La requête n’a pas pu être traitée."
    )

def permission_denied(request, exception=None):
    return _render(
        request, "403.html", 403,
        "Accès refusé",
        "Vous n’avez pas les droits nécessaires pour accéder à cette ressource."
    )

def page_not_found(request, exception=None):
    return _render(
        request, "404.html", 404,
        "Page introuvable",
        "La ressource demandée est introuvable ou a été déplacée."
    )

def server_error(request):
    # pas de param exception ici selon le contrat Django
    return _render(
        request, "500.html", 500,
        "Erreur interne",
        "Une erreur est survenue de notre côté. L’équipe a été notifiée."
    )

@requires_csrf_token
def csrf_failure(request, reason=""):
    return _render(
        request, "403_csrf.html", 403,
        "Vérification CSRF échouée",
        "Le jeton de sécurité n’a pas été validé.", {"reason": reason}
    )