# circuitMoto/translation_utils.py
import os
from typing import Iterable, Optional

# Détection de langue (optionnel mais recommandé)
try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
except Exception:
    detect = None

# DeepL (si DEEPL_API_KEY défini)
try:
    import deepl  # pip install deepl
except Exception:
    deepl = None

# Google Translate non-officiel (secours)
try:
    from googletrans import Translator as GoogleTranslator  # pip install googletrans==4.0.0rc1
except Exception:
    GoogleTranslator = None

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
_google = None

def _detect_lang(text: str) -> Optional[str]:
    if not text:
        return None
    if detect:
        try:
            return detect(text)  # "fr", "en", ...
        except Exception:
            return None
    # Heuristique minimale si lib absente
    lowered = text.lower()
    any_fr = any(tok in lowered for tok in (" le ", " la ", " les ", " des ", " un ", " une ", "à ", " de "))
    any_en = any(tok in lowered for tok in (" the ", " an ", " a ", " to ", " of ", " and "))
    if any_fr and not any_en:
        return "fr"
    if any_en and not any_fr:
        return "en"
    return None

def translate_text(text: str, src: str = "fr", dest: str = "en") -> str:
    if not text:
        return text

    # 1) DeepL
    if DEEPL_API_KEY and deepl:
        try:
            tr = deepl.Translator(DEEPL_API_KEY)
            res = tr.translate_text(text, source_lang=src.upper(), target_lang=dest.upper())
            return res.text
        except Exception:
            pass

    # 2) Google (secours, sans garantie)
    if GoogleTranslator:
        try:
            global _google
            if _google is None:
                _google = GoogleTranslator()
            res = _google.translate(text, src=src, dest=dest)
            return res.text
        except Exception:
            pass

    # 3) Fallback : retourner le texte d’origine (copie FR→EN)
    return text

def auto_translate_instance(instance, fields: Iterable[str]) -> bool:
    """
    Pour chaque champ 'f' dans fields, si f_en est vide ou semble FR,
    on traduit depuis f_fr (ou f si proxy) vers EN et on remplit f_en.
    Retourne True si instance modifiée.
    """
    changed = False
    for f in fields:
        fr = getattr(instance, f"{f}_fr", "") or getattr(instance, f, "")
        en = getattr(instance, f"{f}_en", "")
        if not fr:
            continue

        # Si EN est vide, ou détecté FR → traduire
        need = (not en)
        if not need:
            lang_en = _detect_lang(en)
            if lang_en in ("fr", "fr-FR", "fr-CA"):
                need = True

        if need:
            translated = translate_text(fr, src="fr", dest="en") or ""
            if translated and translated != en:
                setattr(instance, f"{f}_en", translated)
                changed = True
    return changed
