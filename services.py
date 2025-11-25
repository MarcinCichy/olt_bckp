# services.py
from backup_service import BackupService

# Tworzymy globalną instancję serwisu.
# Aplikacja (app) zostanie przypisana do niej później w webapp.py
backup_service = BackupService(app=None)