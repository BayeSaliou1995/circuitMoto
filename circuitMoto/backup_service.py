# circuitMoto/backup_service.py
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple

from django.conf import settings
from django.utils import timezone


class BackupError(Exception):
    pass


def _safe_name(value: str) -> str:
    return "".join(c for c in value if c.isalnum() or c in ("-", "_")).strip() or "backup"


def create_full_backup_zip() -> Tuple[Path, str]:
    """
    Crée une sauvegarde complète:
    - dump PostgreSQL (.sql)
    - copie du dossier media/
    - fichier README de restauration
    - archive ZIP finale

    Retourne:
        (archive_path, archive_filename)
    """
    timestamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    project_name = _safe_name(getattr(settings, "ROOT_URLCONF", "circuitMoto").split(".")[0])
    backup_name = f"{project_name}-backup-{timestamp}"

    temp_root = Path(tempfile.mkdtemp(prefix="circuit_backup_"))
    backup_dir = temp_root / backup_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    db = settings.DATABASES["default"]
    engine = db.get("ENGINE", "")

    try:
        # ----------------------------
        # 1) Base de données
        # ----------------------------
        if "postgresql" in engine:
            sql_path = backup_dir / "database.sql"

            env = os.environ.copy()
            password = db.get("PASSWORD")
            if password:
                env["PGPASSWORD"] = password

            host = db.get("HOST") or "localhost"
            port = str(db.get("PORT") or "5432")
            user = db.get("USER") or ""
            name = db.get("NAME") or ""

            cmd = [
                "pg_dump",
                "-h", host,
                "-p", port,
                "-U", user,
                "-d", name,
                "-F", "p",
                "-f", str(sql_path),
            ]

            try:
                subprocess.run(
                    cmd,
                    check=True,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise BackupError(
                    "pg_dump est introuvable sur le serveur. Installe le client PostgreSQL."
                ) from exc
            except subprocess.CalledProcessError as exc:
                raise BackupError(
                    f"Échec du dump PostgreSQL: {exc.stderr.strip() or exc.stdout.strip() or 'erreur inconnue'}"
                ) from exc

        elif "sqlite3" in engine:
            db_file = Path(db["NAME"])
            if not db_file.exists():
                raise BackupError("Le fichier SQLite est introuvable.")
            shutil.copy2(db_file, backup_dir / db_file.name)

        else:
            raise BackupError("Moteur de base non pris en charge automatiquement.")

        # ----------------------------
        # 2) Dossier media
        # ----------------------------
        media_root = Path(getattr(settings, "MEDIA_ROOT", ""))
        if media_root and media_root.exists():
            shutil.copytree(media_root, backup_dir / "media", dirs_exist_ok=True)

        # ----------------------------
        # 3) README de restauration
        # ----------------------------
        restore_txt = backup_dir / "README_RESTAURATION.txt"
        restore_txt.write_text(
            (
                "SAUVEGARDE COMPLETE DU PROJET\n"
                f"Date: {timestamp}\n\n"
                "Contenu:\n"
                "- database.sql (ou fichier sqlite)\n"
                "- dossier media/\n\n"
                "Restauration:\n"
                "1. Déployer le projet dans un nouvel environnement.\n"
                "2. Restaurer la base PostgreSQL avec psql ou remettre le fichier SQLite.\n"
                "3. Remettre le dossier media/ au bon emplacement.\n"
                "4. Vérifier les variables d'environnement et les permissions.\n"
            ),
            encoding="utf-8",
        )

        # ----------------------------
        # 4) ZIP final
        # ----------------------------
        archive_base = temp_root / backup_name
        archive_path_str = shutil.make_archive(str(archive_base), "zip", root_dir=backup_dir)
        archive_path = Path(archive_path_str)

        return archive_path, archive_path.name

    except Exception:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        raise