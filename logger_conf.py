# logger_conf.py

import logging
from pathlib import Path

import colorlog

# ===== USTAWIENIA FORMATÓW =====

# Format logów na konsoli (z kolorami)
CONSOLE_LOG_FORMAT = "%(log_color)s%(levelname)-8s%(reset)s %(message)s"

# Format logów w pliku
FILE_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"


# ===== KONFIGURACJA LOGGERA GŁÓWNEGO =====

# Używamy głównego loggera (root), żeby wszystkie moduły korzystały z jednej konfiguracji
logger = logging.getLogger()

# Żeby Flask / reloader nie dodawał wielu handlerów przy każdym starcie,
# konfigurujemy logger tylko raz – jeśli nie ma jeszcze handlerów.
if not logger.handlers:
    # Globalny poziom na DEBUG – żeby do pliku można było pisać wszystko,
    # a poziom dla poszczególnych handlerów ustawimy osobno.
    logger.setLevel(logging.DEBUG)

    # ===== HANDLER NA KONSOLĘ (PyCharm / terminal) =====
    console_handler = colorlog.StreamHandler()
    # Na konsoli chcemy widzieć tylko INFO, WARNING, ERROR, CRITICAL
    console_handler.setLevel(logging.INFO)

    console_formatter = colorlog.ColoredFormatter(CONSOLE_LOG_FORMAT)
    console_handler.setFormatter(console_formatter)

    # ===== HANDLER DO PLIKU =====
    # Logi zapisujemy do katalogu "logs/app.log"
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    file_path = log_dir / "app.log"
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    # Do pliku zapisujemy pełne DEBUG (wszystko)
    file_handler.setLevel(logging.DEBUG)

    file_formatter = logging.Formatter(FILE_LOG_FORMAT)
    file_handler.setFormatter(file_formatter)

    # ===== DODANIE HANDLERÓW =====
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
