# circuitMoto/validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.contrib.auth.hashers import check_password
from django.conf import settings

from .models import PasswordHistory

class PreventPasswordReuseValidator:
    """
    Interdit de réutiliser:
      - le mot de passe actuel
      - un des N derniers (N = PASSWORD_HISTORY_SIZE, défaut 5)
    """
    def __init__(self, history_size=None):
        self.history_size = history_size or getattr(settings, "PASSWORD_HISTORY_SIZE", 5)

    def validate(self, password, user=None):
        if user is None:
            return
        # 1) pas le même que l'actuel
        if user.password and check_password(password, user.password):
            raise ValidationError(
                _("Ce mot de passe a déjà été utilisé. Veuillez en choisir un autre."),
                code="password_used",
            )
        # 2) pas l’un des N derniers
        if user.pk:
            hist = PasswordHistory.objects.filter(user=user).order_by("-created_at")[: self.history_size]
            for h in hist:
                if check_password(password, h.encoded):
                    raise ValidationError(
                        _("Vous avez déjà utilisé ce mot de passe récemment. Choisissez-en un différent."),
                        code="password_used_recently",
                    )

    def get_help_text(self):
        return _("Vous ne pouvez pas réutiliser vos anciens mots de passe.")