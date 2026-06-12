# -*- coding: utf-8 -*-
"""Téléchargement des sauvegardes back-office."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.utils import timezone

from ..backup_service import BackupError, create_full_backup_zip
from ..models import JournalAudit


@staff_member_required
def bo_backup_download(request):
    if not request.user.is_superuser:
        raise Http404("Page introuvable.")
    if request.method != "POST":
        raise Http404("Méthode non autorisée.")
    try:
        archive_path, archive_name = create_full_backup_zip()
        JournalAudit.objects.create(acteur=request.user, action="backup_download", donnees={"filename": archive_name, "created_at": timezone.now().isoformat()})
        return FileResponse(open(archive_path, "rb"), as_attachment=True, filename=archive_name)
    except BackupError as exc:
        messages.error(request, f"Sauvegarde impossible : {exc}")
        raise Http404(str(exc))
    except Exception:
        messages.error(request, "Une erreur inattendue est survenue lors de la génération de la sauvegarde.")
        raise Http404("Erreur de sauvegarde.")
