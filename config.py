# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

# Ładowanie zmiennych środowiskowych z pliku .env (jeśli istnieje)
load_dotenv()

# === USTAWIENIA BAZY DANYCH ===
# Wybór silnika: 'sqlite' lub 'postgres'
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

if DB_TYPE == "postgres":
    # Format: postgresql://user:password@host:port/dbname
    user = os.getenv("POSTGRES_USER", "postgres")
    pw = os.getenv("POSTGRES_PASSWORD", "password")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "oltbackup")
    SQLALCHEMY_DATABASE_URI = f"postgresql://{user}:{pw}@{host}:{port}/{db_name}"
else:
    # Domyślnie SQLite w katalogu /data (dla Dockera) lub lokalnie
    data_dir = os.getenv("DATA_DIR", ".")
    db_path = os.path.join(data_dir, "app.db")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

SQLALCHEMY_TRACK_MODIFICATIONS = False

# === BEZPIECZEŃSTWO ===

# ZMIANA: Generujemy losowy klucz przy każdym uruchomieniu aplikacji.
# Skutek: Restart serwera/kontenera natychmiast wylogowuje wszystkich użytkowników.
SECRET_KEY = os.urandom(24)

# Konfiguracja wygasania sesji
# False oznacza, że sesja wygasa po zamknięciu przeglądarki
SESSION_PERMANENT = False
# Dodatkowo wyloguj po 30 minutach bezczynności
PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

# Klucz do szyfrowania plików backupu (musi być base64 url-safe, 32 bytes)
# Ten klucz MUSI być stały (z .env), żeby móc odszyfrować stare pliki.
BACKUP_ENCRYPTION_KEY = os.getenv("BACKUP_ENCRYPTION_KEY")

# === SSH ===
SSH_USERNAME = os.getenv("SSH_USERNAME", "").strip()
SSH_PASSWORD = os.getenv("SSH_PASSWORD", "")
SSH_TIMEOUT = int(os.getenv("SSH_TIMEOUT", 20))

# === PLIKI I KATALOGI (Dla kompatybilności i importu) ===
# Plik z listą urządzeń (jeden adres IP w linii).
DEVICES_FILE = os.getenv("DEVICES_FILE", "devices.txt")

# Katalog, w którym będą trzymane backupy
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")

# Plik z konfiguracją harmonogramu (zostawiamy dla kompatybilności)
SCHEDULE_FILE = os.getenv("SCHEDULE_FILE", "backup_schedule.json")

# Plik statusów (zostawiamy dla kompatybilności)
BACKUP_STATUS_FILE = os.getenv("BACKUP_STATUS_FILE", "backup_status.json")

# === KOMENDY OLT ===
COMMANDS = [
    os.getenv("COMMAND_1"),
    os.getenv("COMMAND_2"),
    os.getenv("COMMAND_3"),
    os.getenv("COMMAND_4"),
    os.getenv("COMMAND_5"),
]