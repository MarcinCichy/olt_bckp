# backup_service.py
import threading
from pathlib import Path
from datetime import datetime

from logger_conf import logger
from device import Device as SSHDevice
import config
from extensions import db
from models import Device as DBDevice, BackupLog
import security_utils


class BackupService:
    def __init__(self, app=None):
        self.app = app
        self.backup_dir = Path(config.BACKUP_DIR)
        self.backup_dir.resolve().mkdir(parents=True, exist_ok=True)
        logger.info(f"--> KATALOG BACKUPÓW: {self.backup_dir.resolve()}")

        self._lock = threading.Lock()
        self._cancel_requested = False

    def init_app(self, app):
        """Pozwala przypisać aplikację Flask po utworzeniu instancji."""
        self.app = app

    def is_running(self) -> bool:
        return self._lock.locked()

    def request_cancel(self) -> None:
        if self.is_running():
            self._cancel_requested = True
            logger.info("Otrzymano żądanie anulowania backupu.")

    def backup_all_devices_thread(self):
        """Funkcja uruchamiana w wątku (z GUI)."""
        if not self.app:
            logger.error("Błąd: BackupService nie ma przypisanej aplikacji (self.app is None)")
            return

        with self.app.app_context():
            self.backup_devices_logic(trigger_type='manual')

    def backup_devices_logic(self, selected_ips=None, trigger_type='manual'):
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

        # 1. Start - ustawiamy status running
        try:
            db_dev.last_status = 'running'
            db_dev.last_error = None
            db.session.commit()
        except Exception:
            db.session.rollback()
            return  # Jeśli nie możemy zapisać statusu start, to i tak nic nie zrobimy

        ssh_dev = SSHDevice(
            ip=ip,
            username=config.SSH_USERNAME,
            password=config.SSH_PASSWORD,
            commands=config.COMMANDS
        )

        try:
            # 2. Logika SSH
            ssh_dev.connect()
            ssh_dev.run_commands()
            content, sysname = ssh_dev.get_result()
            # Usuwamy ssh_dev.disconnect() stąd - wykona się w finally

            if sysname:
                db_dev.sysname = sysname

            if content:
                safe_sysname = "".join(c for c in sysname if c.isalnum() or c in ('-', '_')) if sysname else ""
                base_name = f"{ip}_{safe_sysname}" if safe_sysname else ip
                timestamp = datetime.now().strftime("%d%m%y_%H%M")

                filename = f"{base_name}_{timestamp}.txt"
                file_path = self.backup_dir / filename

                # 3. Zapis (zwróci False jeśli szyfrowanie zawiedzie przy obecnym kluczu)
                if security_utils.encrypt_to_file(content, file_path):
                    db_dev.last_status = 'success'
                    db_dev.last_backup_time = datetime.now()

                    log = BackupLog(
                        device_ip=ip,
                        filename=filename,
                        status='success',
                        size_bytes=file_path.stat().st_size,
                        encrypted=True,
                        trigger_type=trigger_type
                    )
                    db.session.add(log)

                    if trigger_type == 'cron':
                        self._cleanup_old_backups(ip)
                else:
                    db_dev.last_status = 'error'
                    db_dev.last_error = "Błąd szyfrowania: Sprawdź klucz w .env!"
            else:
                db_dev.last_status = 'error'
                db_dev.last_error = "Pusta konfiguracja lub błąd komendy"

            db.session.commit()

        except Exception as e:
            # KLUCZOWA ZMIANA: Rollback w przypadku błędu
            db.session.rollback()
            logger.error(f"Exception device {ip}: {e}")

            # Próba zapisania błędu do bazy (w nowej transakcji po rollbacku)
            try:
                db_dev.last_status = 'error'
                db_dev.last_error = str(e)[:250]  # Przycinamy na wszelki wypadek
                db.session.commit()
            except Exception:
                db.session.rollback()

        finally:
            ssh_dev.disconnect()

    def _cleanup_old_backups(self, ip: str):
        try:
            logs = BackupLog.query.filter_by(device_ip=ip, status='success', trigger_type='cron') \
                .order_by(BackupLog.created_at.desc()) \
                .all()

            limit = config.MAX_BACKUPS_PER_DEVICE

            if len(logs) > limit:
                logs_to_delete = logs[limit:]
                count = 0
                for log_entry in logs_to_delete:
                    file_path = self.backup_dir / log_entry.filename
                    try:
                        if file_path.exists():
                            file_path.unlink()
                    except OSError:
                        pass

                    db.session.delete(log_entry)
                    count += 1

                logger.info(f"Rotacja (Cron) dla {ip}: usunięto {count} starych plików.")
        except Exception as e:
            logger.error(f"Błąd rotacji dla {ip}: {e}")