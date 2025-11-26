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
        """
        webhook_url = config.MATTERMOST_WEBHOOK_URL

        if not webhook_url:
            logger.info("Brak konfiguracji MATTERMOST_WEBHOOK_URL - pomijam powiadomienie.")
            return

        # Ustalanie koloru paska (Zielony=OK, Czerwony=Awaria, Żółty=Częściowe błędy)
        if failed == 0:
            color = "#00c951"  # Green
            title = "✅ Backup Automatyczny OLTów: Sukces"
        elif success == 0:
            color = "#d10c27"  # Red
            title = "❌ Backup Automatyczny OLTów: Awaria"
        else:
            color = "#ffbc42"  # Orange
            title = "⚠️ Backup Automatyczny OLTów: Problemy"

        # Treść wiadomości
        text_lines = [
            f"### {title}",
            f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Czas trwania:** {duration_seconds:.1f}s",
            "",
            "---",
            f"📊 **Statystyki:**",
            f"- Razem: **{total}**",
            f"- ✅ OK: **{success}**",
            f"- ❌ Błąd: **{failed}**"
        ]

        if failed_ips:
            text_lines.append("\n**Problematyczne urządzenia:**")
            for ip in failed_ips:
                text_lines.append(f"- `{ip}`")

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