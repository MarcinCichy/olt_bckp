# device.py
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import paramiko

from text_processing import process_text
from logger_conf import logger


class Device:
    """
    Reprezentuje pojedyncze urządzenie (np. OLT), z którym łączymy się po SSH
    i wykonujemy zestaw komend backupowych.
    """

    def __init__(self, ip: str, username: str, password: str, commands, backup_dir: str) -> None:
        self.ip = ip
        self.username = username
        self.password = password
        self.commands = commands
        self.backup_dir = Path(backup_dir)

        self.outputs = {}          # type: dict[int, str]
        self.client: Optional[paramiko.SSHClient] = None
        self.channel = None
        self.sysname: str = ""

    def connect(self) -> None:
        logger.info(f"Łączenie z urządzeniem: {self.ip} jako użytkownik {self.username}")
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.load_system_host_keys()
        self.client.connect(
            self.ip,
            username=self.username,
            password=self.password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        self.channel = self.client.invoke_shell()
        time.sleep(1)

    def execute_command(self, command: str) -> str:
        """
        Wykonuje pojedynczą komendę na urządzeniu przez kanał SSH
        i zwraca surowy tekst wyjściowy (bez przetwarzania).
        """
        if not command:
            logger.warning(f"{self.ip}: pusta komenda – pomijam.")
            return ""

        logger.debug(f"{self.ip}: wykonuję komendę: {command}")
        self.channel.send(command + "\n")
        time.sleep(1)
        self.channel.send("\n")
        time.sleep(1)

        output = ""
        while True:
            if self.channel.recv_ready():
                chunk = self.channel.recv(1024).decode()
                output += chunk
            else:
                time.sleep(3)
                if not self.channel.recv_ready():
                    break
        return output

    def run_commands(self) -> None:
        """
        Wykonuje wszystkie komendy z listy self.commands i zapisuje
        przetworzone wyniki w self.outputs.
        """
        for i, cmd in enumerate(self.commands, start=1):
            raw_output = self.execute_command(cmd)
            processed_output = process_text(raw_output)
            self.outputs[i] = processed_output

        # Wyodrębnienie sysname – najpierw próbujemy z wyniku komendy 4
        sysname_candidate = ""

        if 4 in self.outputs:
            sysname_candidate = self._extract_sysname_from_text(self.outputs[4])

        # Jeśli się nie udało, szukamy w pozostałych outputach
        if not sysname_candidate:
            for idx, text in self.outputs.items():
                if idx == 4:
                    continue
                sysname_candidate = self._extract_sysname_from_text(text)
                if sysname_candidate:
                    break

        self.sysname = sysname_candidate or ""

    @staticmethod
    def _extract_sysname_from_text(text: str) -> str:
        """
        Pomocnicza metoda do wyszukiwania 'sysname' w tekście.
        Zakładamy linie w stylu:
          'sysname: OLT-COS-TAM' lub 'sysname OLT-COS-TAM'
        """
        for line in text.splitlines():
            if "sysname" in line:
                parts = line.split("sysname", 1)[1].strip(" :")
                if parts:
                    return parts.split()[0]
        return ""

    def save_output(self) -> str:
        """
        Zapisuje wynik komendy nr 4 (po przetworzeniu) do pliku w katalogu backupów.
        Nazwa pliku:
          IP_SYSNAME_DDMMYY_HHMM

        Zwraca pełną ścieżkę do utworzonego pliku.
        """
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        if self.sysname:
            base_name = f"{self.ip}_{self.sysname}"
        else:
            base_name = self.ip

        timestamp = datetime.now().strftime("%d%m%y_%H%M")
        file_name = f"{base_name}_{timestamp}"
        file_path = self.backup_dir / file_name

        output = self.outputs.get(4, "")
        lines = output.splitlines()
        output_without_first_three = "\n".join(lines[3:]) if len(lines) >= 3 else ""

        with file_path.open("w", encoding="utf-8") as f:
            f.write(output_without_first_three)

        logger.info(f"Zapisano backup do pliku: {file_path}")
        return str(file_path)

    def disconnect(self) -> None:
        if self.client:
            self.client.close()
            logger.info(f"Połączenie z {self.ip} zakończone")

    def process_device(self) -> Optional[str]:
        """
        Pełny proces:
          1. Połączenie
          2. Wykonanie komend i przetworzenie wyników
          3. Zapis backupu do pliku
          4. Rozłączenie

        Zwraca ścieżkę do pliku backupu lub None w razie błędu.
        """
        backup_path: Optional[str] = None
        try:
            self.connect()
            self.run_commands()
            backup_path = self.save_output()
        except Exception as e:
            logger.error(f"Błąd przy przetwarzaniu urządzenia {self.ip}: {e}")
        finally:
            self.disconnect()
        return backup_path
