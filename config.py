# config.py
import os
from dotenv import load_dotenv

# Ładowanie zmiennych środowiskowych z pliku .env (jeśli istnieje)
load_dotenv()

# Dane logowania SSH
SSH_USERNAME = os.getenv("SSH_USERNAME", "").strip()
SSH_PASSWORD = os.getenv("PASSWORD", "")

# Komendy wykonywane na OLT.
# Pobierane z .env:
#   COMMAND_1, COMMAND_2, COMMAND_3, COMMAND_4, COMMAND_5
COMMANDS = [
    os.getenv("COMMAND_1"),
    os.getenv("COMMAND_2"),
    os.getenv("COMMAND_3"),
    os.getenv("COMMAND_4"),
    os.getenv("COMMAND_5"),
]

# Plik z listą urządzeń (jeden adres IP w linii).
# Domyślnie używamy "devices.txt", ale można to nadpisać w .env:
#   DEVICES_FILE=devices.txt
DEVICES_FILE = os.getenv("DEVICES_FILE", "devices.txt")

# Katalog, w którym będą trzymane backupy
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")

# Plik z konfiguracją harmonogramu (dla CRON + auto-backup)
SCHEDULE_FILE = os.getenv("SCHEDULE_FILE", "backup_schedule.json")

# Plik z informacją o statusie backupów (sukces/błąd/w trakcie)
BACKUP_STATUS_FILE = os.getenv("BACKUP_STATUS_FILE", "backup_status.json")
