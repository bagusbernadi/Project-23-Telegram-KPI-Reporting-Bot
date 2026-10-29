"""Pengirim pesan. DryRunSender tidak mengirim apa pun (menyimpan pesan + mencatat delivery_log). TelegramSender memanggil Bot API
lewat HTTP biasa; kode ini DIUJI hanya dengan transport palsu (tanpa token dan jaringan), belum pernah mengirim ke Telegram sungguhan."""
import os
import time


class SendError(Exception):
    pass


class DryRunSender:
    """Tidak mengirim. Menyimpan setiap pesan di self.messages dan catatan di self.log (daftar dict delivery_log)."""

    def __init__(self, latency_fn=None):
        self.messages, self.log = [], []
        self.latency_fn = latency_fn or (lambda: 3)

    def send(self, text, kind, sent_at, report_date, photo=None):
        self.messages.append(dict(kind=kind, text=text, photo=str(photo) if photo else None, sent_at=sent_at, report_date=report_date))
        self.log.append(dict(sent_at=sent_at, message_type=kind, status="sent", latency_s=int(self.latency_fn()), error="", report_date=report_date))
        return True


class TelegramSender:
    """Kirim lewat https://api.telegram.org/bot<TOKEN>/sendMessage atau sendPhoto. Token dan chat id hanya dari environment.
    post(url, data, files) bisa diganti saat tes. Gagal -> coba ulang sesuai wait_seconds, lalu catat gagal."""

    def __init__(self, post=None, retries=3, wait_seconds=(2, 5, 10), sleep=time.sleep):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.post = post or self._http_post
        self.retries, self.wait, self.sleep = retries, wait_seconds, sleep
        self.log = []

    @staticmethod
    def _http_post(url, data, files=None):  # pragma: no cover - butuh jaringan dan token
        import requests
        r = requests.post(url, data=data, files=files, timeout=20)
        if r.status_code != 200:
            raise SendError(f"HTTP {r.status_code}: {r.text[:120]}")
        return r.json()

    def send(self, text, kind, sent_at, report_date, photo=None):
        if not self.token or not self.chat_id:
            raise SendError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diisi")
        base = f"https://api.telegram.org/bot{self.token}"
        err = ""
        for i in range(self.retries):
            t0 = time.time()
            try:
                if photo:
                    with open(photo, "rb") as fh:
                        self.post(f"{base}/sendPhoto", {"chat_id": self.chat_id, "caption": text[:1000]}, {"photo": fh})
                else:
                    self.post(f"{base}/sendMessage", {"chat_id": self.chat_id, "text": text}, None)
                self.log.append(dict(sent_at=sent_at, message_type=kind, status="sent", latency_s=int(round(time.time() - t0)), error=err, report_date=report_date))
                return True
            except Exception as e:  # noqa: BLE001
                err = str(e).replace(self.token, "***")[:120]
                if i < self.retries - 1:
                    self.sleep(self.wait[min(i, len(self.wait) - 1)])
        self.log.append(dict(sent_at=sent_at, message_type=kind, status="failed", latency_s=0, error=err, report_date=report_date))
        return False
