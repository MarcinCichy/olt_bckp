# notification_service.py
import requests
import json
from datetime import datetime
import config
from logger_conf import logger


class NotificationService:
    @staticmethod
    def send_backup_summary(total, success, failed, failed_ips, duration_seconds):
        """
        Wysyła podsumowanie backupu na Mattermost.
        Wersja kompaktowa (max 3 linie tekstu dla sukcesu).
        """
        webhook_url = config.MATTERMOST_WEBHOOK_URL

        if not webhook_url:
            logger.info("Brak konfiguracji MATTERMOST_WEBHOOK_URL - pomijam powiadomienie.")
            return

        # Kolory paska bocznego
        if failed == 0:
            color = "#00c951"  # Green
            status_text = "SUKCES"
        elif success == 0:
            color = "#d10c27"  # Red
            status_text = "AWARIA"
        else:
            color = "#ffbc42"  # Orange
            status_text = "PROBLEMY"

        # Budowanie treści wiadomości (Markdown)

        # Linia 1: Nagłówek
        line_1 = f"**Backup Automatyczny: {status_text}**"

        # Linia 2: Data
        line_2 = f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Linia 3: Statystyki
        line_3 = f"Razem: **{total}** ✅ OK: **{success}** ❌ Błąd: **{failed}**"

        text_lines = [line_1, line_2, line_3]

        # Dodatkowa lista błędów tylko jeśli wystąpiły
        if failed_ips:
            # FIX: Dodajemy pusty string przed separatorem,
            # aby uniknąć zamiany poprzedniej linii w nagłówek H2.
            text_lines.append("")
            text_lines.append("---")
            text_lines.append("**Błędy IP:** " + ", ".join(failed_ips))

        payload = {
            "username": "OLT Backup Bot",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/2950/2950063.png",
            "attachments": [
                {
                    "color": color,
                    "text": "\n".join(text_lines)
                }
            ]
        }

        try:
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            if response.status_code != 200:
                logger.error(f"Błąd Mattermost: {response.status_code} - {response.text}")
            else:
                logger.info("Wysłano raport na Mattermost.")
        except Exception as e:
            logger.error(f"Wyjątek przy wysyłaniu powiadomienia: {e}")