# schedule.py
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from logger_conf import logger


@dataclass
class BackupSchedule:
    """
    Prosta reprezentacja harmonogramu:
      - enabled: czy auto-backup jest włączony,
      - hour, minute: o której godzinie ma się uruchomić,
      - last_run_date: data ostatniego uruchomienia (YYYY-MM-DD jako string),
        żeby nie robić backupu kilka razy tego samego dnia.
    """
    enabled: bool = True
    hour: int = 3
    minute: int = 0
    last_run_date: Optional[str] = None


class ScheduleRepository:
    """
    Odpowiada za zapis/odczyt harmonogramu do pliku JSON.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def load(self) -> BackupSchedule:
        if not self.path.is_file():
            logger.info(f"Plik harmonogramu nie istnieje, używam domyślnych wartości: {self.path}")
            return BackupSchedule()
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return BackupSchedule(
                enabled=bool(data.get("enabled", True)),
                hour=int(data.get("hour", 3)),
                minute=int(data.get("minute", 0)),
                last_run_date=data.get("last_run_date"),
            )
        except Exception as e:
            logger.error(f"Nie udało się odczytać pliku harmonogramu {self.path}: {e}")
            return BackupSchedule()

    def save(self, schedule: BackupSchedule) -> None:
        data = {
            "enabled": schedule.enabled,
            "hour": schedule.hour,
            "minute": schedule.minute,
            "last_run_date": schedule.last_run_date,
        }
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Zapisano harmonogram do pliku: {self.path}")


def should_run_now(schedule: BackupSchedule, now: datetime) -> bool:
    """
    Zwraca True, jeśli wg harmonogramu powinniśmy wykonać backup.
    Zakładamy:
      - backup raz dziennie,
      - wykonujemy go o godzinie (hour:minute),
      - jeśli last_run_date == dzisiejsza data, drugi raz już nie uruchamiamy.
    """
    if not schedule.enabled:
        return False

    today_str = now.date().isoformat()
    if schedule.last_run_date == today_str:
        return False

    scheduled_today = now.replace(
        hour=schedule.hour,
        minute=schedule.minute,
        second=0,
        microsecond=0,
    )
    if now >= scheduled_today:
        return True

    return False
