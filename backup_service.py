# backup_service.py
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from logger_conf import logger
from device import Device
import config
from backup_storage import BackupStorage, BackupFileInfo
from backup_status import BackupStatusRepository


@dataclass
class BackupResult:
    ip: str
    backup_path: Optional[str]
    success: bool
    error: Optional[str] = None


@dataclass
class DeviceStatus:
    ip: str
    sysname: Optional[str]
    last_backup: Optional[datetime]
    has_backup: bool
    status: str
    last_error: Optional[str]


class BackupService:
    """
    Warstwa logiki biznesowej. Zarządza listą urządzeń, uruchamianiem backupu
    i sprawdzaniem statusów. Posiada blokadę (mutex) dla operacji współbieżnych.
    """

    def __init__(
            self,
            devices_file: Optional[str] = None,
            username: Optional[str] = None,
            password: Optional[str] = None,
            commands: Optional[List[str]] = None,
            backup_dir: Optional[str] = None,
    ) -> None:
        self.devices_file = devices_file or config.DEVICES_FILE
        self.username = username or config.SSH_USERNAME
        self.password = password or config.SSH_PASSWORD
        self.commands = commands or config.COMMANDS
        self.backup_dir = backup_dir or config.BACKUP_DIR

        self.storage = BackupStorage(self.backup_dir)
        self.status_repo = BackupStatusRepository(config.BACKUP_STATUS_FILE)

        # Blokada zapobiegająca równoległemu uruchomieniu backupów
        self._lock = threading.Lock()
        self._cancel_requested: bool = False

    def is_running(self) -> bool:
        """Sprawdza czy backup jest w toku."""
        return self._lock.locked()

    def request_cancel(self) -> None:
        """Zgłasza żądanie przerwania."""
        if self.is_running():
            self._cancel_requested = True
            logger.info("Otrzymano żądanie anulowania backupu.")

    def _load_devices(self) -> List[str]:
        path = Path(self.devices_file)
        if not path.is_file():
            logger.warning(f"Plik z urządzeniami nie istnieje: {path}")
            return []
        with path.open("r", encoding="utf-8") as f:
            # Filtrujemy puste linie i komentarze
            ips = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        return ips

    def list_devices(self) -> List[str]:
        return self._load_devices()

    def list_devices_status(self) -> List[DeviceStatus]:
        ips = self._load_devices()
        statuses: List[DeviceStatus] = []
        now = datetime.now()

        for ip in ips:
            backups = self.storage.list_backups(ip=ip)
            last_backup_at = backups[0].created_at if backups else None
            has_backup = bool(backups)
            sysname = backups[0].sysname if backups else None

            state = self.status_repo.get_record(ip)
            status = state.last_result
            last_error = state.last_error

            if status == "running" and state.last_run:
                try:
                    last_run_dt = datetime.fromisoformat(state.last_run)
                    if now - last_run_dt > timedelta(minutes=30):
                        status = "error"
                        if not last_error:
                            last_error = "Backup przerwany (timeout procesu)"
                except ValueError:
                    pass

            if status == "never" and has_backup:
                status = "success"

            statuses.append(
                DeviceStatus(
                    ip=ip,
                    sysname=sysname,
                    last_backup=last_backup_at,
                    has_backup=has_backup,
                    status=status,
                    last_error=last_error,
                )
            )
        return statuses

    def get_latest_backups_all_devices(self) -> List[BackupFileInfo]:
        ips = self._load_devices()
        latest: List[BackupFileInfo] = []
        for ip in ips:
            backups = self.storage.list_backups(ip=ip)
            if backups:
                latest.append(backups[0])
        latest.sort(key=lambda b: b.ip)
        return latest

    def backup_all_devices(self) -> List[BackupResult]:
        ips = self._load_devices()
        return self.backup_devices(ips)

    def backup_devices(self, ips: List[str]) -> List[BackupResult]:
        """
        Główna funkcja wykonująca backup. Jest zabezpieczona blokadą.
        """
        # Próba założenia blokady. Jeśli zajęte, zwracamy pustą listę/błąd.
        if not self._lock.acquire(blocking=False):
            logger.warning("Próba uruchomienia backupu, gdy inny jest w toku.")
            return []

        results: List[BackupResult] = []
        self._cancel_requested = False

        try:
            logger.info(f"Rozpoczynam sesję backupu dla {len(ips)} urządzeń.")

            for index, ip in enumerate(ips):
                if self._cancel_requested:
                    logger.info("Przerwano pętlę backupu (request_cancel).")
                    self._mark_cancelled(ips[index:])
                    break

                res = self._process_single_ip(ip)
                results.append(res)

        except Exception as e:
            logger.error(f"Nieoczekiwany błąd pętli backupu: {e}")
        finally:
            self._lock.release()
            self._cancel_requested = False
            logger.info("Zakończono sesję backupu.")

        return results

    def _process_single_ip(self, ip: str) -> BackupResult:
        start_time = datetime.now()
        self.status_repo.set_running(ip, start_time.isoformat(timespec="seconds"))

        device = Device(
            ip=ip,
            username=self.username,
            password=self.password,
            commands=self.commands,
            backup_dir=self.backup_dir,
        )

        # process_device obsługuje łączenie, komendy i zapis
        backup_path = device.process_device()
        end_time = datetime.now()

        if backup_path:
            self.status_repo.set_success(ip, end_time.isoformat(timespec="seconds"))
            return BackupResult(ip=ip, backup_path=backup_path, success=True)
        else:
            msg = "Nie utworzono pliku backupu (błąd SSH lub pusta konfiguracja)"
            self.status_repo.set_error(ip, end_time.isoformat(timespec="seconds"), msg)
            return BackupResult(ip=ip, backup_path=None, success=False, error=msg)

    def _mark_cancelled(self, ips: List[str]):
        now_str = datetime.now().isoformat(timespec="seconds")
        msg = "Backup anulowany przez użytkownika."
        for ip in ips:
            self.status_repo.set_error(ip, now_str, msg)