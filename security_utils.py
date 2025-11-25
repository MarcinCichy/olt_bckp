# security_utils.py
import os
from pathlib import Path
from cryptography.fernet import Fernet
import config
from logger_conf import logger


def get_cipher():
    """
    Zwraca obiekt Fernet.
    Rzuca wyjątek, jeśli klucz jest pusty, None lub nieprawidłowy.
    """
    key = config.BACKUP_ENCRYPTION_KEY

    # 1. Sprawdzenie czy klucz w ogóle istnieje
    if not key or not key.strip():
        raise ValueError("Brak klucza BACKUP_ENCRYPTION_KEY w pliku .env!")

    # 2. Próba utworzenia obiektu Fernet (walidacja formatu klucza)
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise ValueError(f"Nieprawidłowy format klucza BACKUP_ENCRYPTION_KEY: {e}")


def encrypt_to_file(content: str, filepath: Path) -> bool:
    """
    Zapisuje treść (str) do pliku TYLKO w formie zaszyfrowanej.
    Jeśli szyfrowanie się nie uda (brak klucza/zły klucz) -> zwraca False i nic nie zapisuje.
    """
    try:
        # Pobranie szyfratora (rzuci błędem jeśli klucz jest zły/pusty)
        cipher = get_cipher()

        data_bytes = content.encode('utf-8')
        encrypted_data = cipher.encrypt(data_bytes)

        with filepath.open("wb") as f:
            f.write(encrypted_data)

        return True

    except Exception as e:
        logger.critical(f"BŁĄD BEZPIECZEŃSTWA: Nie można wykonać zaszyfrowanego backupu! Powód: {e}")

        # Na wszelki wypadek, gdyby plik został utworzony pusty (np. przy otwieraniu), usuwamy go
        try:
            if filepath.exists():
                filepath.unlink()
        except OSError:
            pass

        return False


def decrypt_from_file(filepath: Path) -> str:
    """
    Odczytuje i odszyfrowuje plik.
    Dla kompatybilności wstecznej: jeśli pliku nie da się odszyfrować,
    próbuje go odczytać jako tekst (dla starych backupów sprzed wdrożenia szyfrowania).
    """
    try:
        with filepath.open("rb") as f:
            data = f.read()

        # Próbujemy uzyskać cipher, ale tutaj nie chcemy "krzyczeć" błędem,
        # bo może chcemy odczytać stary plik plain-text nawet bez klucza.
        cipher = None
        try:
            cipher = get_cipher()
        except ValueError:
            pass  # Brak klucza lub zły klucz - spróbujemy odczytać raw

        if cipher:
            try:
                decrypted_data = cipher.decrypt(data)
                return decrypted_data.decode('utf-8')
            except Exception:
                # Klucz jest, ale nie pasuje do tego pliku.
                # Może plik jest stary i niezaszyfrowany?
                return data.decode('utf-8', errors='ignore')
        else:
            # Brak klucza w konfiguracji -> próbujemy odczytać jako plain text
            return data.decode('utf-8', errors='ignore')

    except Exception as e:
        logger.error(f"Błąd odczytu pliku {filepath}: {e}")
        return f"[BŁĄD ODCZYTU PLIKU: {e}]"