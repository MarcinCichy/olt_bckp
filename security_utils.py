# security_utils.py
import os
from pathlib import Path
from cryptography.fernet import Fernet
import config
from logger_conf import logger


def get_cipher():
    key = config.BACKUP_ENCRYPTION_KEY
    if not key:
        logger.warning(
            "Brak klucza szyfrowania (BACKUP_ENCRYPTION_KEY)! Pliki będą zapisywane jawnym tekstem (NIEZALECANE).")
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        logger.error(f"Błąd inicjalizacji szyfrowania: {e}")
        return None


def encrypt_to_file(content: str, filepath: Path) -> bool:
    """Zapisuje treść (str) do pliku, szyfrując ją."""
    cipher = get_cipher()
    try:
        data_bytes = content.encode('utf-8')
        if cipher:
            encrypted_data = cipher.encrypt(data_bytes)
            with filepath.open("wb") as f:
                f.write(encrypted_data)
        else:
            # Fallback do plain text (tylko jeśli brak klucza)
            with filepath.open("w", encoding="utf-8") as f:
                f.write(content)
        return True
    except Exception as e:
        logger.error(f"Błąd podczas szyfrowania/zapisu pliku {filepath}: {e}")
        return False


def decrypt_from_file(filepath: Path) -> str:
    """Odczytuje i odszyfrowuje plik."""
    cipher = get_cipher()
    try:
        with filepath.open("rb") as f:
            data = f.read()

        if cipher:
            try:
                decrypted_data = cipher.decrypt(data)
                return decrypted_data.decode('utf-8')
            except Exception:
                # Jeśli nie udało się odszyfrować, może plik jest plain-text (stary backup)?
                # Próbujemy odczytać jako tekst
                return data.decode('utf-8', errors='ignore')
        else:
            return data.decode('utf-8', errors='ignore')

    except Exception as e:
        logger.error(f"Błąd odczytu/deszyfrowania pliku {filepath}: {e}")
        return "[BŁĄD ODCZYTU - PLIK USZKODZONY LUB ZŁY KLUCZ]"