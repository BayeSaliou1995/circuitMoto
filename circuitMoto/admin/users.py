# -*- coding: utf-8 -*-
"""Gestion des utilisateurs staff et des mots de passe."""
from __future__ import annotations

import secrets
import string

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..models import AccountFlags, SitePrefs
from .forms import FirstPasswordChangeForm, SelfPasswordChangeForm, StaffUserCreateForm


def generate_strong_password(length: int = 12) -> str:
    u = string.ascii_uppercase
    l = string.ascii_lowercase
    d = string.digits
    s = "!@#$%^&*()-_=+[]{};:,.?/"
    base = [secrets.choice(u), secrets.choice(l), secrets.choice(d), secrets.choice(s)]
    pool = u + l + d + s
    base += [secrets.choice(pool) for _ in range(max(8, length) - 4)]
    secrets.SystemRandom().shuffle(base)
    return "".join(base)


@staff_member_required
def user_create(request):
    if not request.user.has_perm("auth.add_user"):
        messages.error(request, "Vous n'avez pas la permission de créer des utilisateurs.")
        return redirect("bo_dashboard")

    if request.method == "POST":
        form = StaffUserCreateForm(request.POST)
        if form.is_valid():
            User = get_user_model()
            tmp_pwd = generate_strong_password(12)
            user = User(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                is_active=True,
                is_staff=True,
                is_superuser=form.cleaned_data.get("is_superuser") or False,
            )
            user.set_password(tmp_pwd)
            user.save()
            AccountFlags.objects.update_or_create(user=user, defaults={"must_change_password": True, "initial_password_hash": user.password})
            messages.success(request, f"Utilisateur « {user.get_full_name() or user.username} » créé.")
            return render(request, "circuitMoto/admin/users_created_show_pwd.html", {"user_obj": user, "tmp_pwd": tmp_pwd})
    else:
        form = StaffUserCreateForm()
    return render(request, "circuitMoto/admin/users_create.html", {"form": form})


@login_required
def password_change_first(request):
    flags = getattr(request.user, "flags", None)
    if not flags or not flags.must_change_password:
        return redirect("bo_dashboard")
    if request.method == "POST":
        form = FirstPasswordChangeForm(request.POST)
        if form.is_valid():
            new_pwd = form.cleaned_data["password1"]
            request.user.set_password(new_pwd)
            request.user.save(update_fields=["password"])
            flags.must_change_password = False
            flags.initial_password_hash = ""
            flags.save(update_fields=["must_change_password", "initial_password_hash"])
            update_session_auth_hash(request, request.user)
            messages.success(request, "Mot de passe mis à jour. Bienvenue !")
            return redirect("bo_dashboard")
    else:
        form = FirstPasswordChangeForm()
    return render(request, "circuitMoto/auth/first_change_password.html", {"form": form})


@login_required
def password_change_self(request):
    if request.method == "POST":
        form = SelfPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            new_pwd = form.cleaned_data["new_password1"]
            request.user.set_password(new_pwd)
            request.user.save(update_fields=["password"])
            update_session_auth_hash(request, request.user)
            messages.success(request, "Votre mot de passe a bien été mis à jour.")
            return redirect("bo_dashboard" if request.user.is_staff else "home")
    else:
        form = SelfPasswordChangeForm(request.user)
    return render(request, "circuitMoto/auth/change_password.html", {"form": form})


@user_passes_test(lambda u: u.is_active and u.is_superuser)
@require_POST
def email_flags_set(request):
    key = (request.POST.get("key") or "").strip()
    raw = (request.POST.get("value") or "").strip().lower()
    value = raw in {"1", "true", "on", "yes"}
    mapping = {
        "all": "emails_pause_all",
        "pilote": "emails_pause_pilote",
        "passager": "emails_pause_passager",
    }
    if key not in mapping:
        from django.http import JsonResponse
        return JsonResponse({"ok": False, "message": "Clé invalide."}, status=400)
    prefs = SitePrefs.get()
    setattr(prefs, mapping[key], value)
    prefs.save(update_fields=[mapping[key], "modifie_le"])
    cache.delete("site_email_flags_v1")
    from django.http import JsonResponse
    return JsonResponse({"ok": True, "key": key, "paused": value, "flags": SitePrefs.as_flags(), "message": ("Pause activée" if value else "Pause désactivée")})
