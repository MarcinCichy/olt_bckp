# backup_storage.py
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from logger_conf import logger


@dataclass
class BackupFileInfo:
    filename: str
    ip: str
    sysname: Optional[str]
    created_at: datetime
    size_bytes: int


class BackupStorage:
    """
    Odpowiada za operacje na plikach backupów (lista, podgląd, kasowanie, ścieżki).
    """

    def __init__(self, backup_dir: str) -> None:
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _parse_filename(self, name: str) -> Optional[BackupFileInfo]:
        """
        Oczekiwany format nazwy pliku:
          IP_SYSNAME_DDMMYY_HHMM
        lub (bez sysname):
          IP_DDMMYY_HHMM
        """
        path = self.backup_dir / name
        if not path.is_file():
            return None

        parts = name.rsplit("_", 2)
        if len(parts) != 3:
            # Nieznany format – pomijamy
            return None

        ip_sys, date_str, time_str = parts
        try:
            dt = datetime.strptime(f"{date_str}_{time_str}", "%d%m%y_%H%M")
        except ValueError:
            return None

        if "_" in ip_sys:
            ip, sysname = ip_sys.split("_", 1)
        else:
            ip, sysname = ip_sys, None

        size = path.stat().st_size

        return BackupFileInfo(
            filename=name,
            ip=ip,
            sysname=sysname,
            created_at=dt,
            size_bytes=size,
        )

    def list_backups(self, ip: Optional[str] = None) -> List[BackupFileInfo]:
        """
        Zwraca listę backupów (opcjonalnie tylko dla jednego IP),
        posortowaną od najnowszego do najstarszego.
        """
        backups: List[BackupFileInfo] = []

        for entry in self.backup_dir.iterdir():
            if not entry.is_file():
                continue
            info = self._parse_filename(entry.name)
            if not info:
                continue
            if ip and info.ip != ip:
                continue
            backups.append(info)

        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def read_backup(self, filename: str) -> str:
        """
        Zwraca zawartość pliku backupu jako tekst.
        """
        path = self.backup_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Plik backupu nie istnieje: {path}")
        return path.read_text(encoding="utf-8")

    def delete_backup(self, filename: str) -> bool:
        """
        Kasuje wybrany plik backupu. Zwraca True, jeśli się udało.
        """
        path = self.backup_dir / filename
        if not path.is_file():
            logger.warning(f"Próba usunięcia nieistniejącego pliku backupu: {path}")
            return False
        path.unlink()
        logger.info(f"Usunięto backup: {path}")
        return True

    def get_backup_path(self, filename: str) -> Path:
        """
        Zwraca pełną ścieżkę do pliku backupu.
        """
        return self.backup_dir / filename
