# device_manager.py

from device import Device
from logger_conf import logger


class DeviceManager:
    def __init__(self, devices_file, username, password, commands):
        # Inicjalizacja managera urządzeń z podanym plikiem, danymi logowania i listą komend
        self.devices_file = devices_file
        self.username = username
        self.password = password
        self.commands = commands
        self.device_list = []  # Lista adresów IP urządzeń

    def load_devices(self):
        # Wczytuje listę urządzeń z pliku, ignorując puste linie
        with open(self.devices_file, "r", encoding="utf-8") as f:
            self.device_list = [line.strip() for line in f if line.strip()]
        logger.info(f"Wczytano {len(self.device_list)} urządzeń z pliku {self.devices_file}")

    def process_all_devices(self):
        # Dla każdego adresu IP utworzenie obiektu Device i wykonanie pełnego procesu
        for ip in self.device_list:
            device = Device(ip, self.username, self.password, self.commands)
            device.process_device()
