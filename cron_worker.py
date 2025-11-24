# cron_worker.py
from datetime import datetime

from logger_conf import logger
from backup_service import BackupService
from schedule import ScheduleRepository, should_run_now
import config
# Musimy zaimportować obiekt 'app', aby mieć dostęp do bazy danych
from webapp import app


def main() -> None:
    repo = ScheduleRepository(config.SCHEDULE_FILE)
    schedule = repo.load()
    now = datetime.now()

    if not should_run_now(schedule, now):
        logger.info("Auto-backup: brak potrzeby uruchamiania (harmonogram).")
        return

    logger.info("Auto-backup: start backupu wszystkich urządzeń.")

    # Tworzymy kontekst aplikacji, aby BackupService widział bazę danych
    with app.app_context():
        # Inicjalizujemy serwis przekazując app
        service = BackupService(app)
        # Wywołujemy z flagą 'cron' - to uruchomi rotację dla tych plików
        service.backup_devices_logic(trigger_type='cron')

    logger.info("Auto-backup: zakończono operację.")

    # Aktualizujemy datę ostatniego uruchomienia
    schedule.last_run_date = now.date().isoformat()
    repo.save(schedule)


if __name__ == "__main__":
    main()