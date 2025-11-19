# device.py
import time
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import paramiko

from text_processing import process_text
from logger_conf import logger
import config


class Device:
    """
    Reprezentuje pojedyncze urządzenie (np. OLT), z którym łączymy się po SSH.
    Wersja przywrócona do oryginalnej logiki (hard-coded sleeps),
    która działała w Twoim środowisku.
    """

    def __init__(self, ip: str, username: str, password: str, commands: List[str], backup_dir: str) -> None:
        self.ip = ip
        self.username = username
        self.password = password
        self.commands = commands
        self.backup_dir = Path(backup_dir)

        self.outputs = {}  # type: dict[int, str]
        self.client: Optional[paramiko.SSHClient] = None
        self.channel = None
        self.sysname: str = ""

    def connect(self) -> None:
        logger.info(f"Łączenie z urządzeniem: {self.ip} jako użytkownik {self.username}")
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.load_system_host_keys()

            self.client.connect(
                self.ip,
                username=self.username,
                password=self.password,
                timeout=config.SSH_TIMEOUT,
                allow_agent=False,
                look_for_keys=False
            )

            self.channel = self.client.invoke_shell()
            # W oryginale był sleep(1) po połączeniu
            time.sleep(1)

        except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
            logger.error(f"Błąd połączenia z {self.ip}: {e}")
            raise

    def execute_command(self, command: str) -> str:
        """
        Wykonuje pojedynczą komendę dokładnie tak, jak w oryginalnym kodzie:
        1. Wyślij komendę + \n
        2. Czekaj 1s
        3. Wyślij \n (pusty enter) - to często "opycha" prompt na OLT
        4. Czekaj 1s
        5. Czytaj w pętli z 3-sekundowym timeoutem na brak danych
        """
        if not command:
            logger.warning(f"{self.ip}: pusta komenda – pomijam.")
            return ""

        logger.debug(f"{self.ip}: wykonuję komendę: {command}")

        # Oryginalna sekwencja
        self.channel.send(command + "\n")
        time.sleep(1)
        self.channel.send("\n")
        time.sleep(1)

        output = ""
        while True:
            if self.channel.recv_ready():
                # Czytamy kawałkami
                try:
                    chunk = self.channel.recv(1024).decode(errors='ignore')
                    output += chunk
                except socket.timeout:
                    break
            else:
                # To jest kluczowe dla Twojego urządzenia - czekamy 3 sekundy
                # jeśli nic nie przyjdzie, uznajemy że koniec.
                time.sleep(3)
                if not self.channel.recv_ready():
                    break
        return output

    def run_commands(self) -> None:
        """
        Wykonuje komendy bez żadnych dodatkowych ingerencji (brak screen-length itp).
        """
        for i, cmd in enumerate(self.commands, start=1):
            if not cmd:
                continue

            raw_output = self.execute_command(cmd)
            processed_output = process_text(raw_output)
            self.outputs[i] = processed_output

        # Wyodrębnienie sysname (logika oryginalna)
        self._determine_sysname()

    def _determine_sysname(self):
        sysname_candidate = ""

        if 4 in self.outputs:
            sysname_candidate = self._extract_sysname_from_text(self.outputs[4])

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
        """
        for line in text.splitlines():
            if "sysname" in line:
                # Oryginalne proste parsowanie
                try:
                    parts = line.split("sysname", 1)[1].strip(" :")
                    if parts:
                        return parts.split()[0]
                except IndexError:
                    continue
        return ""

    def save_output(self) -> Optional[str]:
        """
        Zapisuje wynik komendy nr 4.
        """
        if 4 not in self.outputs:
            logger.warning(f"{self.ip}: Brak wyniku dla komendy nr 4 - nie zapisuję pliku.")
            return None

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        if self.sysname:
            # Prosta sanityzacja na wypadek dziwnych znaków
            safe_sysname = "".join(c for c in self.sysname if c.isalnum() or c in ('-', '_'))
            base_name = f"{self.ip}_{safe_sysname}"
        else:
            base_name = self.ip

        timestamp = datetime.now().strftime("%d%m%y_%H%M")
        file_name = f"{base_name}_{timestamp}"
        file_path = self.backup_dir / file_name

        output = self.outputs.get(4, "")
        lines = output.splitlines()

        # W oryginale usuwałeś 3 pierwsze linie
        output_without_first_three = "\n".join(lines[3:]) if len(lines) >= 3 else ""

        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(output_without_first_three)
            logger.info(f"Zapisano backup do pliku: {file_path}")
            return str(file_path)
        except IOError as e:
            logger.error(f"Błąd zapisu pliku {file_path}: {e}")
            return None

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.close()
                logger.info(f"Połączenie z {self.ip} zakończone")
            except Exception:
                pass

    def process_device(self) -> Optional[str]:
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