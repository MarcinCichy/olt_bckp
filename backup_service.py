# backup_service.py
import threading
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from logger_conf import logger
from device import Device as SSHDevice
import config
from extensions import db
from models import Device as DBDevice, BackupLog, Settings
import security_utils


class BackupService:
    def __init__(self, app=None):
        self.app = app
        self.backup_dir = Path(config.BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cancel_requested = False

    def is_running(self) -> bool:
        return self._lock.locked()

    def request_cancel(self) -> None:
        if self.is_running():
            self._cancel_requested = True
            logger.info("Otrzymano żądanie anulowania backupu.")

    def get_devices_list(self):
        """Pobiera aktywne urządzenia z BAZY DANYCH."""
        return DBDevice.query.filter_by(enabled=True).all()

    def backup_all_devices_thread(self):
        """Funkcja uruchamiana w wątku."""
        with self.app.app_context():
            self.backup_devices_logic()

    def backup_devices_logic(self, selected_ips=None):
        if not self._lock.acquire(blocking=False):
            return

        self._cancel_requested = False
        try:
            devices = DBDevice.query.filter_by(enabled=True).all()
            if selected_ips:
                devices = [d for d in devices if d.ip in selected_ips]

            logger.info(f"Start backupu {len(devices)} urządzeń.")

            for dev in devices:
                if self._cancel_requested:
                    logger.info("Przerwano backup.")
                    break

                self._process_single_device(dev)

        except Exception as e:
            logger.error(f"Błąd w pętli backupu: {e}")
        finally:
            self._lock.release()
            self._cancel_requested = False

    def _process_single_device(self, db_dev):
        ip = db_dev.ip

        # Ustawiamy status na running
        db_dev.last_status = 'running'
        db_dev.last_error = None
        db.session.commit()

        ssh_dev = SSHDevice(
            ip=ip,
            username=config.SSH_USERNAME,
            password=config.SSH_PASSWORD,
            commands=config.COMMANDS,
            backup_dir=str(self.backup_dir)
        )

        try:
            # 1. Pobranie backupu (Device.process_device łączy się i pobiera config)
            plain_path_str = ssh_dev.process_device()

            # === POPRAWKA: Aktualizacja sysname w bazie ===
            # Jeśli SSHDevice wykrył nazwę urządzenia, zapisujemy ją w bazie danych
            if ssh_dev.sysname:
                db_dev.sysname = ssh_dev.sysname

            if plain_path_str:
                plain_path = Path(plain_path_str)

                # 2. Odczyt (plain text)
                try:
                    with plain_path.open("r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # Fallback dla dziwnych kodowań
                    with plain_path.open("r", encoding="latin-1") as f:
                        content = f.read()

                # 3. Szyfrowanie i nadpisanie pliku
                if security_utils.encrypt_to_file(content, plain_path):
                    # Sukces
                    db_dev.last_status = 'success'
                    db_dev.last_backup_time = datetime.now()

                    # Dodajemy wpis do historii logów
                    log = BackupLog(
                        device_ip=ip,
                        filename=plain_path.name,
                        status='success',
                        size_bytes=plain_path.stat().st_size,
                        encrypted=True
                    )
                    db.session.add(log)
                else:
                    db_dev.last_status = 'error'
                    db_dev.last_error = "Błąd szyfrowania pliku"
            else:
                db_dev.last_status = 'error'
                db_dev.last_error = "Błąd SSH lub pusta konfiguracja"

        except Exception as e:
            db_dev.last_status = 'error'
            db_dev.last_error = str(e)
            logger.error(f"Exception device {ip}: {e}")

        # Zapisujemy zmiany w bazie (status, sysname, logi)
        db.session.commit()