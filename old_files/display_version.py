import os
import time
import paramiko
from dotenv import load_dotenv


def get_version_output(channel):
    """
    Wysyła komendę "display version" oraz symuluje naciśnięcie klawisza ENTER,
    aby urządzenie zwróciło pełny wynik.
    """
    # Wysyłamy komendę bezpośrednio z końcowym \n
    channel.send("display version\n")
    time.sleep(1)  # Krótkie oczekiwanie, aby urządzenie zareagowało

    # Dodatkowe naciśnięcie ENTER, jeżeli urządzenie tego oczekuje
    channel.send("\n")
    time.sleep(1)  # Czas na przetworzenie komendy i naciśnięcie ENTER

    output = ""
    while True:
        if channel.recv_ready():
            output += channel.recv(1024).decode()
        else:
            time.sleep(0.5)
            if not channel.recv_ready():
                break
    return output


def extract_version(output):
    """
    Przeszukuje output w poszukiwaniu linii zawierającej dokładnie ciąg "VERSION : "
    i zwraca wartość znajdującą się po tym ciągu.
    """
    for line in output.splitlines():
        line = line.strip()
        #print(f"DEBUG: linia: '{line}'")
        if line.startswith("VERSION : "):
            version = line[len("VERSION : "):].strip()
            #print(f"DEBUG: znaleziono wersję: '{version}'")
            return version
    #print("DEBUG: Nie znaleziono linii z 'VERSION : '")
    return ""



def main():
    load_dotenv()

    username = os.getenv("SSH_USERNAME", "").strip()
    password = os.getenv("PASSWORD")

    devices_file = "../devices.txt"
    with open(devices_file, "r", encoding="utf-8") as f:
        device_ips = [line.strip() for line in f if line.strip()]

    results = []

    for ip in device_ips:
        print(f"Connecting to {ip}...")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.load_system_host_keys()
        try:
            client.connect(ip, username=username, password=password,
                           timeout=10, allow_agent=False, look_for_keys=False)
            channel = client.invoke_shell()
            time.sleep(1)  # Poczekaj aż kanał będzie gotowy
            output = get_version_output(channel)
            version_value = extract_version(output)
            results.append(f"{ip} - {version_value}")
        except Exception as e:
            results.append(f"{ip} - ERROR: {e}")
        finally:
            client.close()

    with open("../versions.log", "w", encoding="utf-8") as f:
        for line in results:
            f.write(line + "\n")

    print("Wyniki zapisano w pliku versions.log")


if __name__ == "__main__":
    main()
