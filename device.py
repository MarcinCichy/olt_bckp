# device.py

import time
import paramiko
from text_processing import process_text
from logger_conf import logger


class Device:
    def __init__(self, ip, username, password, commands):
        # Inicjalizacja urządzenia z adresem IP, danymi logowania oraz listą komend
        self.ip = ip
        self.username = username
        self.password = password
        self.commands = commands           # Lista komend do wykonania (np. [command_1, command_2, ...])
        self.outputs = {}                  # Słownik przechowujący wyniki dla każdej komendy (klucze: 1, 2, ..., 5)
        self.client = None                 # Obiekt SSHClient z biblioteki paramiko (połączenie SSH)
        self.channel = None                # Kanał komunikacyjny SSH
        self.sysname = ""                  # Nazwa systemu pobrana z wyniku komendy 4

    def connect(self):
        # Nawiązywanie połączenia SSH z urządzeniem
        logger.info(f"Łączenie z urządzeniem: {self.ip} jako użytkownik {self.username}")
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Automatyczne zatwierdzanie nieznanych kluczy
        self.client.load_system_host_keys()
        # Próba połączenia z urządzeniem przy użyciu podanych danych logowania
        self.client.connect(
            self.ip,
            username=self.username,
            password=self.password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False
        )
        # Otwarcie interaktywnego kanału SSH
        self.channel = self.client.invoke_shell()
        time.sleep(1)  # Odczekanie, aż kanał będzie gotowy do komunikacji

    def execute_command(self, command):
        # Wykonuje pojedynczą komendę na urządzeniu przez kanał SSH
        logger.debug(f"Wykonuję komendę: {command}")
        self.channel.send(command + "\n")  # Wysłanie komendy wraz z zakończeniem linii
        time.sleep(1)                      # Krótkie opóźnienie przed kolejnym wysłaniem
        self.channel.send("\n")            # Wysłanie pustej linii (symulacja naciśnięcia ENTER)
        time.sleep(1)                      # Odczekanie na przetworzenie komendy
        output = ""
        # Odbieranie danych z kanału aż do momentu, gdy nie pojawią się kolejne dane
        while True:
            if self.channel.recv_ready():
                # Pobieranie danych w porcjach
                chunk = self.channel.recv(1024).decode()
                output += chunk
            else:
                time.sleep(3)  # Opóźnienie przed kolejną próbą odbioru danych
                if not self.channel.recv_ready():
                    break
        return output

    def run_commands(self):
        # Wykonanie wszystkich komend sekwencyjnie oraz przetwarzanie wyników
        for i, cmd in enumerate(self.commands, start=1):
            raw_output = self.execute_command(cmd)      # Wykonanie komendy i pobranie surowego outputu
            processed_output = process_text(raw_output)   # Przetwarzanie wyniku (oczyszczenie, formatowanie)
            self.outputs[i] = processed_output            # Zapis przetworzonego wyniku do słownika

        # Wyodrębnienie wartości sysname z wyniku komendy 4
        if 4 in self.outputs:
            for line in self.outputs[4].splitlines():
                if "sysname" in line:
                    # Zakładamy, że linia ma format "sysname: nazwa" lub "sysname nazwa"
                    parts = line.split("sysname", 1)[1].strip(" :")
                    if parts:
                        self.sysname = parts.split()[0]
                    break

    def save_output(self):
        # Ustalanie nazwy pliku wyjściowego na podstawie adresu IP oraz sysname (jeśli jest dostępny)
        if self.sysname:
            file_name = f"{self.ip}_{self.sysname}.log"
        else:
            file_name = f"{self.ip}.log"

        # Pobranie wyniku komendy 4 z przechowywanych outputów
        output = self.outputs.get(4, '')
        # Podzielenie tekstu na linie i usunięcie pierwszych trzech linii
        lines = output.splitlines()
        output_without_first_three = "\n".join(lines[3:]) if len(lines) >= 3 else ""

        # Zapis przetworzonego outputu do pliku
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(output_without_first_three)
        logger.info(f"Zapisano output komendy 4 do pliku: {file_name}")

    def log_outputs(self):
        # Logowanie wyników dla każdej z komend
        for i in range(1, 6):
            output = self.outputs.get(i, "")
            logger.info(f"Output for command {i}:\n{output}")

    def disconnect(self):
        # Rozłączenie SSH, jeśli klient został utworzony
        if self.client:
            self.client.close()
            logger.info(f"Połączenie z {self.ip} zakończone")

    def process_device(self):
        # Kompleksowy proces urządzenia:
        # 1. Łączenie się
        # 2. Wykonywanie komend i przetwarzanie wyników
        # 3. Zapis wyniku do pliku
        # 4. Rozłączanie się (nawet przy błędzie)
        try:
            self.connect()
            self.run_commands()
            self.save_output()
            # self.log_outputs()  # Opcjonalne logowanie wszystkich wyników komend
        except Exception as e:
            logger.error(f"Błąd przy łączeniu z {self.ip}: {e}")
        finally:
            self.disconnect()
