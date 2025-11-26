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
            # Jeśli nie możemy zapisać statusu "running", to prawdopodobnie z bazą jest coś nie tak.
            # Ale próbujemy robić backup dalej? Raczej nie, bo nie zapiszemy wyniku.
            logger.error(f"Błąd bazy danych przy starcie backupu dla {ip} - pomijam.")
            return

        ssh_dev = SSHDevice(
            ip=ip,
            username=config.SSH_USERNAME,
            password=config.SSH_PASSWORD,
            commands=config.COMMANDS
        )

        try:
            # 2. Logika SSH (może rzucić wyjątkiem)
            ssh_dev.connect()
            ssh_dev.run_commands()
            content, sysname = ssh_dev.get_result()

            if sysname:
                db_dev.sysname = sysname

            if content:
                safe_sysname = "".join(c for c in sysname if c.isalnum() or c in ('-', '_')) if sysname else ""
                base_name = f"{ip}_{safe_sysname}" if safe_sysname else ip
                timestamp = datetime.now().strftime("%d%m%y_%H%M")

                filename = f"{base_name}_{timestamp}.txt"
                file_path = self.backup_dir / filename

                # 3. Zapis i Szyfrowanie
                # security_utils.encrypt_to_file rzuca False lub Exception przy problemach
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
                    # encrypt_to_file zwróciło False tylko jeśli złapano błąd wewnątrz
                    # (ale teraz w security_utils mamy fail-fast, więc to raczej rzadkie)
                    db_dev.last_status = 'error'
                    db_dev.last_error = "Błąd zapisu pliku (sprawdź logi / klucz szyfrowania)"
            else:
                db_dev.last_status = 'error'
                db_dev.last_error = "Pusta konfiguracja lub błąd komendy SSH"

            db.session.commit()

        except Exception as e:
            # KLUCZOWY ROLLBACK
            db.session.rollback()
            logger.error(f"Exception device {ip}: {e}")

            # Próba zapisania błędu do bazy w nowej transakcji
            try:
                # Odświeżamy obiekt (bo po rollbacku może być odłączony)
                # W prostym scenariuszu db_dev jest wciąż w sesji, ale bezpieczniej pobrać ponownie lub uważać.
                # Tutaj, ponieważ rollback cofnął status 'running', ustawiamy 'error'.
                db_dev.last_status = 'error'
                db_dev.last_error = str(e)[:250]
                db.session.commit()
            except Exception as e2:
                logger.error(f"Nie udało się zapisać statusu błędu do DB dla {ip}: {e2}")
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
                # Commit nie jest tu potrzebny explicite, bo funkcja nadrzędna robi commit,
                # ale dla bezpieczeństwa przy rotacji można:
                # db.session.commit()
                # Jednak zostawiamy to nadrzędnej metodzie (jest w bloku try głównej pętli lub metody).
                # W obecnej strukturze _cleanup jest wywoływany przed commitem w _process_single_device, więc OK.
        except Exception as e:
            logger.error(f"Błąd rotacji dla {ip}: {e}")