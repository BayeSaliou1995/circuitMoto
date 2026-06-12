# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import datetime as dt
import os
import re
import secrets
import string
import time
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

from django import forms  # type: ignore
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import (
    ValidationError as PwValidationError,
    validate_password,
)
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator  # type: ignore
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce, ExtractYear, TruncMonth
from django.forms import formset_factory, inlineformset_factory
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.http import urlencode
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from openpyxl import Workbook  # type: ignore
from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore
from openpyxl.utils import get_column_letter  # type: ignore

from ..backup_service import BackupError, create_full_backup_zip
from ..emails import (
    _abs_url,
    notify_document_refuse,
    notify_inscription_validee,
    notify_paiement_resume_compose,
)
from ..models import (
    Circuit,
    ContactMessage,
    ContactUrgence,
    DechargeSignee,
    Document,
    InfosMedicales,
    Inscription,
    JournalAudit,
    LibellePaiement,
    Moto,
    NewsletterSubscriber,
    OptionCircuit,
    Paiement,
    Personne,
    SelectionOption,
    SitePrefs,
    StatutCircuit,
    StatutDocument,
    StatutInscription,
    StatutPaiement,
    initialiser_plan_paiement_par_defaut,
)


EMAIL_SPLIT_RE = re.compile(r"[,\n;\t ]+")


def _is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _json_ok(message="", **payload):
    return JsonResponse({"ok": True, "message": message, **payload})


def _json_err(message="Erreur inconnue", status=400, **payload):
    return JsonResponse({"ok": False, "message": message, **payload}, status=status)


def _ordered_payments_for_display(ins):
    order_map = {
        LibellePaiement.ACOMPTE1: 1,
        LibellePaiement.ACOMPTE2: 2,
        LibellePaiement.SOLDE: 3,
        LibellePaiement.AUTRE: 4,
    }
    paiements = list(ins.paiements.all())
    paiements.sort(
        key=lambda p: (
            order_map.get(p.libelle, 99),
            p.echeance_le or datetime.date.max,
            p.pk,
        )
    )
    return paiements


def _build_email_payment_rows(ins):
    rows = []
    for p in _ordered_payments_for_display(ins):
        attendu = Decimal(p.montant_du or 0)
        encaisse = Decimal(p.montant_encaisse or 0)

        if encaisse >= attendu and attendu > 0:
            statut_label = "Payé"
        elif encaisse > 0:
            statut_label = "Partiellement payé"
        else:
            statut_label = "À payer"

        rows.append(
            {
                "libelle": p.get_libelle_display(),
                "attendu": attendu,
                "encaisse": encaisse,
                "date": p.encaisse_le,
                "statut": statut_label,
            }
        )
    return rows


def _parse_emails_blob(raw: str) -> Tuple[List[str], List[str]]:
    if not raw:
        return [], []

    candidates = [item.strip() for item in EMAIL_SPLIT_RE.split(raw) if item.strip()]
    valid_emails, invalid_emails, seen = [], [], set()

    for email in candidates:
        email_norm = email.lower()
        try:
            validate_email(email_norm)
            if email_norm not in seen:
                seen.add(email_norm)
                valid_emails.append(email_norm)
        except ValidationError:
            invalid_emails.append(email)

    return valid_emails, invalid_emails


def _get_newsletter_config() -> dict:
    return {
        "enabled": getattr(settings, "NEWSLETTER_ENABLED", True),
        "max_recipients": int(getattr(settings, "NEWSLETTER_MAX_RECIPIENTS_PER_SEND", 1500)),
        "batch_size": int(getattr(settings, "NEWSLETTER_BATCH_SIZE", 50)),
        "sleep_seconds": float(getattr(settings, "NEWSLETTER_SLEEP_SECONDS", 1)),
        "max_attachment_bytes": int(getattr(settings, "NEWSLETTER_MAX_ATTACHMENT_BYTES", 25 * 1024 * 1024)),
        "hide_old_emailing": bool(getattr(settings, "NEWSLETTER_HIDE_OLD_EMAILING", True)),
    }


def _send_newsletter_in_batches(
    *,
    subject: str,
    message: str,
    recipients: List[str],
    attachments: List[Tuple[str, bytes, str]],
    from_email: str,
    batch_size: int,
    sleep_seconds: float,
) -> int:
    sent = 0
    if not recipients:
        return sent

    with get_connection(fail_silently=False) as conn:
        for start in range(0, len(recipients), batch_size):
            batch = recipients[start:start + batch_size]
            for to_email in batch:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=strip_tags(message),
                    from_email=from_email,
                    to=[to_email],
                    connection=conn,
                )
                if "<" in message and ">" in message:
                    msg.attach_alternative(message, "text/html")
                for name, data, ctype in attachments:
                    msg.attach(name, data, ctype)
                msg.send()
                sent += 1
            if sleep_seconds > 0 and (start + batch_size) < len(recipients):
                time.sleep(sleep_seconds)
    return sent


def _safe_str(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Oui" if v else "Non"
    return str(v)
