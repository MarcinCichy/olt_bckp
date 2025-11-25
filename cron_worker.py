# cron_worker.py
from datetime import datetime
import time

from logger_conf import logger
from backup_service import BackupService
from schedule import ScheduleService, should_run_now
# Import app, aby mieć kontekst bazy danych
from webapp import app


def main() -> None:
    # Worker potrzebuje kontekstu aplikacji (Flask), aby połączyć się z bazą danych
    with app.app_context():
        try:
            # 1. Pobierz harmonogram z BAZY
            schedule = ScheduleService.load_schedule()
            now = datetime.now()

            # 2. Sprawdź czy uruchamiać
            if not should_run_now(schedule, now):
                # Opcjonalnie: logger.debug, żeby nie śmiecić w logach co minutę
                # logger.debug("Auto-backup: brak potrzeby uruchamiania.")
                return

            logger.info("Auto-backup: HARMONOGRAM ZADZIAŁAŁ. Start backupu.")

            # 3. Uruchom usługę backupu
            service = BackupService(app)
            service.backup_devices_logic(trigger_type='cron')

            # 4. Zapisz datę wykonania, żeby nie uruchomić ponownie dzisiaj
            today_str = now.date().isoformat()
            ScheduleService.update_last_run_date(today_str)
            logger.info(f"Auto-backup: Zakończono. Ustawiono last_run_date na {today_str}")

        except Exception as e:
            logger.error(f"Krytyczny błąd w cron_worker: {e}")

if __name__ == "__main__":
    # Jeśli uruchamiasz to w pętli w systemie (np. co minutę), to wystarczy raz.
    # Jeśli to ma być demon (działający w tle ciągle), trzeba by dodać pętlę while True.
    # Zakładam, że uruchamiasz to z systemowego crona co minutę lub jako oddzielny proces.
    main()