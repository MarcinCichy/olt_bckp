# backup_status.py
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from logger_conf import logger


@dataclass
class DeviceBackupRecord:
    """
    Ostatni znany stan backupu dla danego IP.
      - last_result: 'never', 'running', 'success', 'error'
      - last_error: treść ostatniego błędu (jeśli była)
      - last_run: znacznik czasu ISO (str) lub None
    """
    last_result: str = "never"
    last_error: Optional[str] = None
    last_run: Optional[str] = None


class BackupStatusRepository:
    """
    Prosty repozytorium, które zapisuje/odczytuje status backupu do pliku JSON.
    Kluczem jest adres IP urządzenia.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def _load_raw(self) -> Dict[str, dict]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            return data
        except Exception as e:
            logger.error(f"Nie udało się odczytać pliku statusu backupu {self.path}: {e}")
            return {}

    def _save_raw(self, data: Dict[str, dict]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_record(self, ip: str) -> DeviceBackupRecord:
        raw = self._load_raw()
        rec = raw.get(ip)
        if not rec:
            return DeviceBackupRecord()
        return DeviceBackupRecord(
            last_result=rec.get("last_result", "never"),
            last_error=rec.get("last_error"),
            last_run=rec.get("last_run"),
        )

    def set_running(self, ip: str, when: str) -> None:
        raw = self._load_raw()
        raw[ip] = {
            "last_result": "running",
            "last_error": None,
            "last_run": when,
        }
        self._save_raw(raw)

    def set_success(self, ip: str, when: str) -> None:
        raw = self._load_raw()
        raw[ip] = {
            "last_result": "success",
            "last_error": None,
            "last_run": when,
        }
        self._save_raw(raw)

    def set_error(self, ip: str, when: str, error: str) -> None:
        raw = self._load_raw()
        raw[ip] = {
            "last_result": "error",
            "last_error": error,
            "last_run": when,
        }
        self._save_raw(raw)
