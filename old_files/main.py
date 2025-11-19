import os
from dotenv import load_dotenv
from device_manager import DeviceManager

# Ładowanie zmiennych środowiskowych z pliku .env
load_dotenv()

# Pobieranie danych z pliku .env (wszystkie dane poza adresem IP, który pobieramy z pliku)
username = os.getenv("SSH_USERNAME", "").strip()  # Nazwa użytkownika SSH (usuwamy zbędne spacje)
password = os.getenv("PASSWORD")                   # Hasło SSH
command_1 = os.getenv("COMMAND_1")                 # Pierwsza komenda do wykonania
command_2 = os.getenv("COMMAND_2")                 # Druga komenda do wykonania
command_3 = os.getenv("COMMAND_3")                 # Trzecia komenda do wykonania
command_4 = os.getenv("COMMAND_4")                 # Czwarta komenda do wykonania
command_5 = os.getenv("COMMAND_5")                 # Piąta komenda do wykonania

# Lista komend do wykonania na urządzeniach
commands = [command_1, command_2, command_3, command_4, command_5]

# Ścieżka do pliku zawierającego listę urządzeń (każdy adres IP w nowej linii)
devices_file = "../device_one.txt"

# Utworzenie instancji managera urządzeń z podanymi parametrami
manager = DeviceManager(devices_file, username, password, commands)

# Wczytanie listy urządzeń z pliku
manager.load_devices()

# Przetworzenie wszystkich urządzeń (łączy się, wykonuje komendy, zapisuje wyniki)
manager.process_all_devices()
