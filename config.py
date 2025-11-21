# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

# Ładowanie zmiennych środowiskowych z pliku .env (jeśli istnieje lokalnie)
load_dotenv()

# === USTAWIENIA BAZY DANYCH ===
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

if DB_TYPE == "postgres":
    user = os.getenv("POSTGRES_USER", "postgres")
    pw = os.getenv("POSTGRES_PASSWORD", "password")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "oltbackup")
    SQLALCHEMY_DATABASE_URI = f"postgresql://{user}:{pw}@{host}:{port}/{db_name}"
else:
    data_dir = os.getenv("DATA_DIR", ".")
    db_path = os.path.join(data_dir, "app.db")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

SQLALCHEMY_TRACK_MODIFICATIONS = False

# === BEZPIECZEŃSTWO ===

# POPRAWKA: Bierzemy klucz z .env. Jeśli go nie ma (błąd konfigu), dopiero wtedy losujemy.
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24))

# Konfiguracja wygasania sesji
SESSION_PERMANENT = False
PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

# Klucz do szyfrowania plików backupu
BACKUP_ENCRYPTION_KEY = os.getenv("BACKUP_ENCRYPTION_KEY")

# === SSH ===
SSH_USERNAME = os.getenv("SSH_USERNAME", "").strip()
SSH_PASSWORD = os.getenv("SSH_PASSWORD", "")
SSH_TIMEOUT = int(os.getenv("SSH_TIMEOUT", 20))

# === PLIKI I KATALOGI ===
DEVICES_FILE = os.getenv("DEVICES_FILE", "devices.txt")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
SCHEDULE_FILE = os.getenv("SCHEDULE_FILE", "backup_schedule.json")
BACKUP_STATUS_FILE = os.getenv("BACKUP_STATUS_FILE", "backup_status.json")

# === KOMENDY OLT ===
COMMAND_1 = os.getenv("COMMAND_1")
COMMAND_2 = os.getenv("COMMAND_2")
COMMAND_3 = os.getenv("COMMAND_3")
COMMAND_4 = os.getenv("COMMAND_4")
COMMAND_5 = os.getenv("COMMAND_5")
COMMANDS = [COMMAND_1, COMMAND_2, COMMAND_3, COMMAND_4, COMMAND_5]