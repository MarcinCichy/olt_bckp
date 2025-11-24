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
        """Funkcja uruchamiana w wątku (z GUI)."""
        with self.app.app_context():
            # Wywołanie ręczne z GUI = 'manual'
            self.backup_devices_logic(trigger_type='manual')

    def backup_devices_logic(self, selected_ips=None, trigger_type='manual'):
        """
        Główna pętla backupu.
        :param selected_ips: Lista IP (opcjonalnie)
        :param trigger_type: 'manual' lub 'cron'
        """
        if not self._lock.acquire(blocking=False):
            return

        self._cancel_requested = False
        try:
            devices = DBDevice.query.filter_by(enabled=True).all()
            if selected_ips:
                devices = [d for d in devices if d.ip in selected_ips]

            logger.info(f"Start backupu {len(devices)} urządzeń. Typ: {trigger_type}")

            for dev in devices:
                if self._cancel_requested:
                    logger.info("Przerwano backup.")
                    break

                self._process_single_device(dev, trigger_type)

        except Exception as e:
            logger.error(f"Błąd w pętli backupu: {e}")
        finally:
            self._lock.release()
            self._cancel_requested = False

    def _process_single_device(self, db_dev, trigger_type):
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
            # 1. Pobranie backupu
            plain_path_str = ssh_dev.process_device()

            # Aktualizacja sysname
            if ssh_dev.sysname:
                db_dev.sysname = ssh_dev.sysname

            if plain_path_str:
                plain_path = Path(plain_path_str)

                # 2. Odczyt (plain text)
                try:
                    with plain_path.open("r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with plain_path.open("r", encoding="latin-1") as f:
                        content = f.read()

                # 3. Szyfrowanie i nadpisanie pliku
                if security_utils.encrypt_to_file(content, plain_path):
                    # Sukces
                    db_dev.last_status = 'success'
                    db_dev.last_backup_time = datetime.now()

                    # Zapis do logów z uwzględnieniem TYPU
                    log = BackupLog(
                        device_ip=ip,
                        filename=plain_path.name,
                        status='success',
                        size_bytes=plain_path.stat().st_size,
                        encrypted=True,
                        trigger_type=trigger_type  # <-- ZAPISUJEMY CZY MANUAL/CRON
                    )
                    db.session.add(log)

                    # === ROTACJA BACKUPÓW ===
                    # Czyścimy stare tylko, jeśli uruchomiono z CRONA.
                    if trigger_type == 'cron':
                        self._cleanup_old_backups(ip)

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

        # Zapisujemy zmiany w bazie
        db.session.commit()

    def _cleanup_old_backups(self, ip: str):
        """
        Usuwa najstarsze backupy TYPU CRON dla danego IP, jeśli ich liczba przekracza limit.
        Backupy 'manual' są ignorowane (zostają na zawsze).
        """
        try:
            # Pobieramy tylko udane backupy automatyczne, posortowane od najnowszego
            logs = BackupLog.query.filter_by(device_ip=ip, status='success', trigger_type='cron') \
                .order_by(BackupLog.created_at.desc()) \
                .all()

            limit = config.MAX_BACKUPS_PER_DEVICE

            if len(logs) > limit:
                # Lista logów do usunięcia (wszystkie powyżej limitu)
                logs_to_delete = logs[limit:]

                count = 0
                for log_entry in logs_to_delete:
                    # 1. Usuń plik z dysku
                    file_path = self.backup_dir / log_entry.filename
                    try:
                        if file_path.exists():
                            file_path.unlink()
                    except OSError as e:
                        pass  # Ignorujemy błędy przy usuwaniu

                    # 2. Usuń wpis z bazy
                    db.session.delete(log_entry)
                    count += 1

                # Nie robimy commit() tutaj, bo zrobi to funkcja nadrzędna
                logger.info(f"Rotacja (Cron) dla {ip}: usunięto {count} starych plików.")

        except Exception as e:
            logger.error(f"Błąd podczas rotacji backupów dla {ip}: {e}")