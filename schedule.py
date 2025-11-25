# schedule.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from extensions import db
from models import Settings
from logger_conf import logger


@dataclass
class BackupSchedule:
    """
    Reprezentacja harmonogramu w pamięci.
    """
    enabled: bool = False
    hour: int = 3
    minute: int = 0
    last_run_date: Optional[str] = None


class ScheduleService:
    """
    Serwis do zarządzania harmonogramem w bazie danych (tabela Settings).
    """

    @staticmethod
    def _get_setting(key: str, default: str) -> str:
        """Pobiera surową wartość z tabeli Settings lub zwraca default."""
        # Używamy db.session.get (SQLAlchemy 2.0 style) lub query.get
        # W Twoim kodzie używasz db.session.get
        setting = db.session.get(Settings, key)
        return setting.value if setting else default

    @staticmethod
    def _set_setting(key: str, value: str) -> None:
        """Zapisuje wartość do tabeli Settings."""
        setting = db.session.get(Settings, key)
        if not setting:
            setting = Settings(key=key, value=str(value))
            db.session.add(setting)
        else:
            setting.value = str(value)
        # Commit powinien być wywoływany tutaj, aby zmiany były trwałe od razu
        db.session.commit()

    @classmethod
    def load_schedule(cls) -> BackupSchedule:
        """
        Ładuje konfigurację harmonogramu z bazy danych.
        """
        try:
            enabled_str = cls._get_setting('schedule_enabled', '0')
            hour_str = cls._get_setting('schedule_hour', '3')
            minute_str = cls._get_setting('schedule_minute', '0')
            last_run = cls._get_setting('schedule_last_run', None)

            # Konwersja typów
            enabled = (enabled_str == '1')
            hour = int(hour_str)
            minute = int(minute_str)

            return BackupSchedule(
                enabled=enabled,
                hour=hour,
                minute=minute,
                last_run_date=last_run
            )
        except Exception as e:
            logger.error(f"Błąd odczytu harmonogramu z DB: {e}. Używam domyślnych.")
            return BackupSchedule()

    @classmethod
    def save_schedule(cls, schedule: BackupSchedule) -> None:
        """
        Zapisuje obiekt harmonogramu do bazy danych.
        """
        try:
            cls._set_setting('schedule_enabled', '1' if schedule.enabled else '0')
            cls._set_setting('schedule_hour', str(schedule.hour))
            cls._set_setting('schedule_minute', str(schedule.minute))
            if schedule.last_run_date:
                cls._set_setting('schedule_last_run', schedule.last_run_date)

            logger.info("Zapisano harmonogram do bazy danych.")
        except Exception as e:
            logger.error(f"Błąd zapisu harmonogramu do DB: {e}")

    @classmethod
    def update_last_run_date(cls, date_str: str) -> None:
        """Aktualizuje tylko datę ostatniego uruchomienia."""
        try:
            cls._set_setting('schedule_last_run', date_str)
        except Exception as e:
            logger.error(f"Błąd aktualizacji daty ostatniego uruchomienia: {e}")


def should_run_now(schedule: BackupSchedule, now: datetime) -> bool:
    """
    Sprawdza, czy należy uruchomić backup (logika bez zmian).
    """
    if not schedule.enabled:
        return False

    today_str = now.date().isoformat()
    # Jeśli już dzisiaj leciał, to nie uruchamiaj
    if schedule.last_run_date == today_str:
        return False

    scheduled_today = now.replace(
        hour=schedule.hour,
        minute=schedule.minute,
        second=0,
        microsecond=0,
    )

    # Uruchom jeśli obecny czas >= czas zaplanowany
    if now >= scheduled_today:
        return True

    return False