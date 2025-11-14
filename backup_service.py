# backup_service.py
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
    """
    Informacje o urządzeniu do wyświetlenia na głównej liście:
      - ip: adres urządzenia,
      - sysname: nazwa systemowa (jeśli ją znamy z plików backupu),
      - last_backup: data/godzina ostatniego backupu (na podstawie plików),
      - has_backup: czy istnieje przynajmniej jeden backup (True/False),
      - status: 'never', 'running', 'success', 'error'
      - last_error: ostatni błąd (jeśli był)
    """
    ip: str
    sysname: Optional[str]
    last_backup: Optional[datetime]
    has_backup: bool
    status: str
    last_error: Optional[str]


class BackupService:
    """
    Warstwa „logiki biznesowej” – wie:
      - skąd wziąć listę urządzeń,
      - jak uruchomić backup (jednego / wielu),
      - gdzie zapisane są pliki,
      - jak listować backupy (przez BackupStorage),
      - jaki jest ostatni status backupu (BackupStatusRepository).
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

    def _load_devices(self) -> List[str]:
        path = Path(self.devices_file)
        if not path.is_file():
            logger.warning(f"Plik z urządzeniami nie istnieje: {path}")
            return []
        with path.open("r", encoding="utf-8") as f:
            ips = [line.strip() for line in f if line.strip()]
        return ips

    def list_devices(self) -> List[str]:
        """
        Zwraca listę IP wczytanych z pliku z urządzeniami.
        (Używane tam, gdzie nie potrzebujemy statusu.)
        """
        return self._load_devices()

    def list_devices_status(self) -> List[DeviceStatus]:
        """
        Zwraca listę urządzeń z informacją o:
          - adresie IP,
          - sysname (jeśli znamy z backupów),
          - dacie/godzinie ostatniego backupu,
          - statusie,
          - ostatnim błędzie.
        """
        ips = self._load_devices()
        statuses: List[DeviceStatus] = []

        for ip in ips:
            backups = self.storage.list_backups(ip=ip)
            last_backup_at = backups[0].created_at if backups else None
            has_backup = bool(backups)
            sysname = backups[0].sysname if backups else None

            state = self.status_repo.get_record(ip)
            status = state.last_result
            last_error = state.last_error

            # --- AUTO-TIMEOUT dla "running" ---
            # Jeśli status "running" utrzymuje się dłużej niż 10 minut,
            # wyświetlamy go jako błąd (na poziomie widoku).
            if status == "running" and state.last_run:
                try:
                    last_run_dt = datetime.fromisoformat(state.last_run)
                    if datetime.now() - last_run_dt > timedelta(minutes=10):
                        status = "error"
                        if not last_error:
                            last_error = "Timeout backupu (running > 10 min)"
                except ValueError:
                    # Jeśli data ma zły format – ignorujemy i zostawiamy oryginalny status
                    pass

            # Jeśli nie mamy statusu, ale istnieje backup, to traktujemy jak sukces
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
        """
        Zwraca listę ostatnich backupów dla wszystkich urządzeń,
        po jednym backupie (najświeższym) na każde IP z listy urządzeń.
        """
        ips = self._load_devices()
        latest: List[BackupFileInfo] = []

        for ip in ips:
            backups = self.storage.list_backups(ip=ip)
            if backups:
                latest.append(backups[0])

        # Posortuj np. po IP
        latest.sort(key=lambda b: b.ip)
        return latest

    def backup_all_devices(self) -> List[BackupResult]:
        """
        Backup wszystkich urządzeń z pliku.
        """
        ips = self._load_devices()
        return self.backup_devices(ips)

    def backup_devices(self, ips: List[str]) -> List[BackupResult]:
        """
        Backup tylko wybranych urządzeń (lista IP).
        """
        results: List[BackupResult] = []

        for ip in ips:
            logger.info(f"Rozpoczynam backup urządzenia {ip}")
            device = Device(
                ip=ip,
                username=self.username,
                password=self.password,
                commands=self.commands,
                backup_dir=self.backup_dir,
            )

            start_time = datetime.now()
            self.status_repo.set_running(ip, start_time.isoformat(timespec="seconds"))

            try:
                backup_path = device.process_device()
                end_time = datetime.now()

                if backup_path:
                    self.status_repo.set_success(ip, end_time.isoformat(timespec="seconds"))
                    results.append(
                        BackupResult(
                            ip=ip,
                            backup_path=backup_path,
                            success=True,
                        )
                    )
                else:
                    msg = "Backup nie został utworzony (brak ścieżki do pliku)."
                    self.status_repo.set_error(ip, end_time.isoformat(timespec="seconds"), msg)
                    results.append(
                        BackupResult(
                            ip=ip,
                            backup_path=None,
                            success=False,
                            error=msg,
                        )
                    )
            except Exception as e:
                end_time = datetime.now()
                err_msg = str(e)
                self.status_repo.set_error(ip, end_time.isoformat(timespec="seconds"), err_msg)
                logger.error(f"Błąd podczas backupu urządzenia {ip}: {e}")
                results.append(
                    BackupResult(
                        ip=ip,
                        backup_path=None,
                        success=False,
                        error=err_msg,
                    )
                )

        return results
