# test_device_manager.py

import unittest
import os
from device_manager import DeviceManager

class TestDeviceManager(unittest.TestCase):
    def setUp(self):
        # Utworzenie tymczasowego pliku z listą urządzeń
        self.test_file = "test_devices.txt"
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("192.168.1.1\n")
            f.write("192.168.1.2\n")
            f.write("\n")  # Pusta linia – powinna być zignorowana
            f.write("192.168.1.3\n")
        self.username = "test_user"
        self.password = "test_pass"
        self.commands = ["cmd1", "cmd2", "cmd3", "cmd4", "cmd5"]

    def tearDown(self):
        # Usunięcie tymczasowego pliku po teście
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_load_devices(self):
        manager = DeviceManager(self.test_file, self.username, self.password, self.commands)
        manager.load_devices()
        # Powinno zostać załadowane 3 urządzenia
        self.assertEqual(len(manager.device_list), 3)
        self.assertListEqual(manager.device_list, ["192.168.1.1", "192.168.1.2", "192.168.1.3"])

if __name__ == '__main__':
    unittest.main()
