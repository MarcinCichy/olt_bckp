# test_device.py

import unittest
import os
from device import Device
from text_processing import process_text

# Klasa DummyChannel symuluje zachowanie kanału SSH
class DummyChannel:
    def __init__(self, responses):
        # responses – lista napisów, które będą zwracane po kolei
        self.responses = responses
        self.index = 0

    def send(self, data):
        # Symulacja wysłania danych – nie wykonuje żadnej operacji
        pass

    def recv_ready(self):
        # Zwraca True, jeśli są jeszcze dane do odbioru
        return self.index < len(self.responses)

    def recv(self, buffer_size):
        # Zwraca kolejną porcję danych jako bajty
        if self.index < len(self.responses):
            response = self.responses[self.index]
            self.index += 1
            return response.encode()
        return "".encode()

# Klasa DummySSHClient symuluje klienta SSH z biblioteki paramiko
class DummySSHClient:
    def __init__(self, dummy_channel):
        self.dummy_channel = dummy_channel

    def set_missing_host_key_policy(self, policy):
        pass

    def load_system_host_keys(self):
        pass

    def connect(self, ip, username, password, timeout, allow_agent, look_for_keys):
        # Symulacja połączenia – nie wykonuje żadnych operacji
        pass

    def invoke_shell(self):
        # Zwraca atrę kanału
        return self.dummy_channel

    def close(self):
        pass

class TestDevice(unittest.TestCase):
    def setUp(self):
        # Przygotowanie atrapy kanału z przykładowymi odpowiedziami
        self.responses = [
            "Line1\n", "Line2\n", "Line3\n", "sysname: TestSys\n", "Line5\n"
        ]
        self.dummy_channel = DummyChannel(self.responses)
        # Utworzenie instancji Device z przykładowymi danymi
        self.device = Device("192.168.1.100", "user", "pass", ["dummy_command"])
        # Podmiana klienta SSH i kanału na atrapy
        self.device.client = DummySSHClient(self.dummy_channel)
        self.device.channel = self.dummy_channel

    def test_run_commands_and_sysname_extraction(self):
        # Ustawienie listy komend na 5 elementów
        self.device.commands = ["cmd1", "cmd2", "cmd3", "cmd4", "cmd5"]

        # Funkcja dummy zwraca inny output dla komendy 4 – zwracamy " Footer" z wiodącą spacją
        def dummy_execute_command(cmd):
            if cmd == "cmd4":
                return "Header\nLine1\nLine2\nsysname: TestSys\n Footer"
            else:
                return "Some other output\n"

        self.device.execute_command = dummy_execute_command
        self.device.run_commands()
        # Sprawdzamy, czy wynik komendy został zapisany i czy wyodrębniono sysname
        self.assertIn(4, self.device.outputs)
        self.assertEqual(self.device.sysname, "TestSys")

    def test_run_commands_and_sysname_extraction(self):
        # Ustawienie listy komend na 5 elementów
        self.device.commands = ["cmd1", "cmd2", "cmd3", "cmd4", "cmd5"]

        # Funkcja dummy zwraca inny output dla komendy 4 – zwracamy " Footer" z wiodącą spacją
        def dummy_execute_command(cmd):
            if cmd == "cmd4":
                return "Header\nLine1\nLine2\nsysname: TestSys\n Footer"
            else:
                return "Some other output\n"

        self.device.execute_command = dummy_execute_command
        self.device.run_commands()
        # Sprawdzamy, czy wynik komendy został zapisany i czy wyodrębniono sysname
        self.assertIn(4, self.device.outputs)
        self.assertEqual(self.device.sysname, "TestSys")

    def test_save_output(self):
        # Test metody save_output – sprawdzamy, czy zapisuje właściwie dane do pliku
        dummy_output = "Header\nLineA\nLineB\nLineC\nLineD"
        self.device.outputs[4] = dummy_output
        self.device.sysname = "TestSys"
        # Nazwa pliku powinna być "192.168.1.100_TestSys.log"
        expected_file = "192.168.1.100_TestSys.log"
        # Upewnij się, że plik nie istnieje przed testem
        if os.path.exists(expected_file):
            os.remove(expected_file)
        self.device.save_output()
        # Sprawdzenie, czy plik został utworzony
        self.assertTrue(os.path.exists(expected_file))
        # Odczyt zawartości pliku – pierwsze trzy linie powinny zostać usunięte
        with open(expected_file, "r", encoding="utf-8") as f:
            content = f.read()
        expected_content = "LineC\nLineD"
        self.assertEqual(content, expected_content)
        # Usuwanie pliku po teście
        os.remove(expected_file)

if __name__ == '__main__':
    unittest.main()
