# cron_worker.py
from datetime import datetime

from logger_conf import logger
from backup_service import BackupService
from schedule import ScheduleRepository, should_run_now
import config


def main() -> None:
    repo = ScheduleRepository(config.SCHEDULE_FILE)
    schedule = repo.load()
    now = datetime.now()

    if not should_run_now(schedule, now):
        logger.info("Auto-backup: brak potrzeby uruchamiania (harmonogram).")
        return

    logger.info("Auto-backup: start backupu wszystkich urządzeń.")
    service = BackupService()
    results = service.backup_all_devices()
    ok = sum(1 for r in results if r.success)
    fail = len(results) - ok
    logger.info(f"Auto-backup: zakończono. Sukces: {ok}, błędy: {fail}.")

    schedule.last_run_date = now.date().isoformat()
    repo.save(schedule)


if __name__ == "__main__":
    main()
