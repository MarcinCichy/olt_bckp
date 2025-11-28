# device.py
import time
import socket
from typing import List, Tuple, Optional

import paramiko

from text_processing import process_text
from logger_conf import logger
import config


class Device:
    """
    Reprezentuje urządzenie (OLT).
    Odpowiada TYLKO za połączenie SSH i pobranie tekstu konfiguracji.
    Nie zapisuje plików na dysku.
    """

    def __init__(self, ip: str, username: str, password: str, commands: List[str]) -> None:
        self.ip = ip
        self.username = username
        self.password = password
        self.commands = commands

        self.client: Optional[paramiko.SSHClient] = None
        self.channel = None

        self.outputs = {}  # type: dict[int, str]
        self.sysname: str = ""

    def connect(self) -> None:
        logger.info(f"Łączenie z urządzeniem: {self.ip} jako użytkownik {self.username}")

        # USTAWIENIA PONAWIANIA
        max_retries = 3  # Ile razy próbować
        retry_delay = 10  # Ile sekund czekać między próbami

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.load_system_host_keys()

        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    logger.info(f"--> [RETRY] Ponawiam połączenie z {self.ip} (Próba {attempt}/{max_retries})...")

                self.client.connect(
                    self.ip,
                    username=self.username,
                    password=self.password,
                    timeout=config.SSH_TIMEOUT,
                    allow_agent=False,
                    look_for_keys=False
                )

                self.channel = self.client.invoke_shell()
                time.sleep(1)

                # Jeśli dotarliśmy tutaj, to sukces - wychodzimy z funkcji connect
                if attempt > 1:
                    logger.info(f"--> [SUKCES] Połączono za {attempt}. razem!")
                return

            except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
                last_exception = e
                logger.warning(f"Błąd przy próbie {attempt} dla {self.ip}: {e}")

                # Jeśli to nie była ostatnia próba, czekamy i pętla leci dalej
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    # To była ostatnia próba - poddajemy się
                    logger.error(f"Krytyczny błąd połączenia z {self.ip} po {max_retries} próbach.")
                    raise last_exception

    def execute_command(self, command: str) -> str:
        if not command:
            return ""

        logger.debug(f"{self.ip}: wykonuję komendę: {command}")
        self.channel.send(command + "\n")
        time.sleep(1)
        self.channel.send("\n")
        time.sleep(1)

        output = ""
        while True:
            if self.channel.recv_ready():
                try:
                    chunk = self.channel.recv(1024).decode(errors='ignore')
                    output += chunk
                except socket.timeout:
                    break
            else:
                time.sleep(3)
                if not self.channel.recv_ready():
                    break
        return output

    def run_commands(self) -> None:
        for i, cmd in enumerate(self.commands, start=1):
            if not cmd:
                continue
            raw_output = self.execute_command(cmd)
            processed_output = process_text(raw_output)
            self.outputs[i] = processed_output

        self._determine_sysname()

    def _determine_sysname(self):
        sysname_candidate = ""
        # Próba wyciągnięcia z wyniku komendy nr 4 (display current-configuration)
        if 4 in self.outputs:
            sysname_candidate = self._extract_sysname_from_text(self.outputs[4])

        # Fallback do innych komend
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
        for line in text.splitlines():
            if "sysname" in line:
                try:
                    parts = line.split("sysname", 1)[1].strip(" :")
                    if parts:
                        return parts.split()[0]
                except IndexError:
                    continue
        return ""

    def get_result(self) -> Tuple[Optional[str], str]:
        """
        Zwraca krotkę: (zawartość_konfiguracji, sysname).
        Zawartość jest oczyszczona (bez 3 pierwszych linii, jak w oryginale).
        """
        if 4 not in self.outputs:
            logger.warning(f"{self.ip}: Brak wyniku dla komendy nr 4.")
            return None, self.sysname

        output = self.outputs.get(4, "")
        lines = output.splitlines()

        # Logika z oryginału: usuń 3 pierwsze linie nagłówkowe
        final_content = "\n".join(lines[3:]) if len(lines) >= 3 else ""

        return final_content, self.sysname

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.close()
                logger.info(f"Połączenie z {self.ip} zakończone")
            except Exception:
                pass