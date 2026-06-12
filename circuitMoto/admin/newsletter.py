# -*- coding: utf-8 -*-
"""Module newsletter du back-office."""
from __future__ import annotations

import time
from typing import List, Tuple

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives, get_connection
from django.shortcuts import redirect, render
from django.utils.html import strip_tags

from .forms import NewsletterBroadcastForm


def get_newsletter_config() -> dict:
    return {
        "enabled": getattr(settings, "NEWSLETTER_ENABLED", True),
        "max_recipients": int(getattr(settings, "NEWSLETTER_MAX_RECIPIENTS_PER_SEND", 1500)),
        "batch_size": int(getattr(settings, "NEWSLETTER_BATCH_SIZE", 50)),
        "sleep_seconds": float(getattr(settings, "NEWSLETTER_SLEEP_SECONDS", 1)),
        "max_attachment_bytes": int(getattr(settings, "NEWSLETTER_MAX_ATTACHMENT_BYTES", 25 * 1024 * 1024)),
        "hide_old_emailing": bool(getattr(settings, "NEWSLETTER_HIDE_OLD_EMAILING", True)),
    }


def send_newsletter_in_batches(*, subject: str, message: str, recipients: List[str], attachments: List[Tuple[str, bytes, str]], from_email: str, batch_size: int, sleep_seconds: float) -> int:
    sent = 0
    if not recipients:
        return sent
    with get_connection(fail_silently=False) as conn:
        for start in range(0, len(recipients), batch_size):
            batch = recipients[start:start + batch_size]
            for to_email in batch:
                msg = EmailMultiAlternatives(subject=subject, body=strip_tags(message), from_email=from_email, to=[to_email], connection=conn)
                if "<" in message and ">" in message:
                    msg.attach_alternative(message, "text/html")
                for name, data, ctype in attachments:
                    msg.attach(name, data, ctype)
                msg.send()
                sent += 1
            if sleep_seconds > 0 and (start + batch_size) < len(recipients):
                time.sleep(sleep_seconds)
    return sent


@staff_member_required
def newsletter_broadcast(request):
    config = get_newsletter_config()
    if not config["enabled"]:
        messages.error(request, "Le module newsletter est actuellement désactivé.")
        return redirect("bo_dashboard")

    preview_stats = {"valid_count": 0, "invalid_count": 0, "sample_invalids": [], "batch_size": config["batch_size"], "max_recipients": config["max_recipients"]}

    if request.method == "POST":
        form = NewsletterBroadcastForm(request.POST, request.FILES)
        if form.is_valid():
            subject = form.cleaned_data["sujet"].strip()
            message = form.cleaned_data["message"]
            test_only = form.cleaned_data["test_only"]
            recipients = form.get_valid_emails()
            invalids = form.get_invalid_emails()
            preview_stats["valid_count"] = len(recipients)
            preview_stats["invalid_count"] = len(invalids)
            preview_stats["sample_invalids"] = invalids[:10]

            if test_only:
                recipients = [request.user.email] if request.user.email else []
                if not recipients:
                    messages.error(request, "Votre compte administrateur n’a pas d’adresse email.")
                    return render(request, "circuitMoto/admin/newsletter_broadcast.html", {"form": form, "preview_stats": preview_stats, "config": config})

            lock_key = f"newsletter_send_lock_user_{request.user.pk}"
            if cache.get(lock_key):
                messages.warning(request, "Un envoi est déjà en cours ou vient d’être lancé.")
                return render(request, "circuitMoto/admin/newsletter_broadcast.html", {"form": form, "preview_stats": preview_stats, "config": config})

            cache.set(lock_key, True, timeout=60)
            try:
                uploaded_files = request.FILES.getlist("pieces_jointes")
                attachments = [(f.name, f.read(), f.content_type or "application/octet-stream") for f in uploaded_files]
                sent = send_newsletter_in_batches(
                    subject=subject,
                    message=message,
                    recipients=recipients,
                    attachments=attachments,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    batch_size=config["batch_size"],
                    sleep_seconds=config["sleep_seconds"],
                )
                msg = f"Newsletter envoyée à {sent} destinataire(s). Lots de {config['batch_size']}."
                if invalids and not test_only:
                    msg += f" {len(invalids)} adresse(s) invalide(s) ignorée(s)."
                messages.success(request, msg)
                return redirect("bo_newsletter_broadcast")
            finally:
                cache.delete(lock_key)
        else:
            raw = request.POST.get("emails_blob", "")
            from .forms import parse_emails_blob
            valid_emails, invalid_emails = parse_emails_blob(raw)
            preview_stats["valid_count"] = len(valid_emails)
            preview_stats["invalid_count"] = len(invalid_emails)
            preview_stats["sample_invalids"] = invalid_emails[:10]
    else:
        form = NewsletterBroadcastForm()

    return render(request, "circuitMoto/admin/newsletter_broadcast.html", {"form": form, "preview_stats": preview_stats, "config": config, "hide_old_emailing": config["hide_old_emailing"]})
