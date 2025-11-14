# log_viewer.py
from pathlib import Path
from typing import List

# Ścieżka do głównego pliku logów aplikacji
LOG_FILE_PATH = Path("logs") / "app.log"


def get_logs_for_ip(ip: str, max_lines: int = 200) -> List[str]:
    """
    Zwraca ostatnie max_lines linii z loga głównego,
    które zawierają podany adres IP.
    """
    if not LOG_FILE_PATH.is_file():
        return []

    lines = LOG_FILE_PATH.read_text(encoding="utf-8").splitlines()
    filtered = [line for line in lines if ip in line]
    return filtered[-max_lines:]
