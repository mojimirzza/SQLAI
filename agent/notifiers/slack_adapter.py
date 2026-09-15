"""
Slack Notifier Adapter
Minimal webhook-based Slack notifications.
"""
import json
import urllib.request


class SlackAdapter:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, channel: str, message: str) -> bool:
        """Send message to Slack via webhook."""
        payload = {
            "text": message,
            "channel": channel,
        }

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False

    def send_console(self, channel: str, message: str) -> bool:
        """Fallback: print to console instead of Slack."""
        print(f"\n[{channel}]\n{message}\n{'='*50}")
        return True
