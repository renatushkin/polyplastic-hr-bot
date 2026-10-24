import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_settings():
    env_file = ROOT / ".env"

    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    token = os.getenv("MAX_BOT_TOKEN", "").strip()

    base_url = os.getenv(
        "MAX_API_URL",
        "https://platform-api2.max.ru",
    ).rstrip("/")

    if not token:
        raise RuntimeError("В .env не заполнен MAX_BOT_TOKEN")

    return token, base_url


class MaxAPI:
    def __init__(self, token, base_url):
        self.token = token
        self.base_url = base_url

    def request(self, method, path, params=None, body=None):
        url = self.base_url + path

        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {
            "Authorization": self.token,
        }

        data = None

        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(
                body,
                ensure_ascii=False,
            ).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )

        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)

    def get_updates(self, marker=None):
        params = {
            "timeout": 25,
            "limit": 20,
            "types": "message_created",
        }

        if marker is not None:
            params["marker"] = marker

        return self.request("GET", "/updates", params=params)

    def send_message(self, user_id, text):
        return self.request(
            "POST",
            "/messages",
            params={"user_id": user_id},
            body={"text": text[:4000]},
        )


def run():
    token, base_url = load_settings()
    api = MaxAPI(token, base_url)

    marker = None
    seen_messages = set()

    print("Адаптер MAX запущен.")
    print("Открой личный чат с Корсиком и отправь текст «Привет».")
    print("Для остановки: Ctrl+C")

    while True:
        try:
            response = api.get_updates(marker)

            for update in response.get("updates", []):
                if update.get("update_type") != "message_created":
                    continue

                message = update.get("message") or {}
                sender = message.get("sender") or {}
                recipient = message.get("recipient") or {}
                body = message.get("body") or {}

                # На первом этапе отвечаем только в личном диалоге.
                if recipient.get("chat_type") != "dialog":
                    continue

                if sender.get("is_bot"):
                    continue

                user_id = sender.get("user_id")
                text = body.get("text")
                message_id = body.get("mid")

                if user_id is None or not text:
                    continue

                if message_id and message_id in seen_messages:
                    continue

                print("Получено текстовое сообщение из личного чата.")

                # Небольшая задержка между ответами.
                time.sleep(0.6)

                api.send_message(
                    user_id,
                    "Привет! Я Корсик. Подключение работает ✅\n"
                    "Сейчас это проверка канала MAX, "
                    "онбординг подключим следующим шагом.",
                )

                if message_id:
                    seen_messages.add(message_id)

            marker = response.get("marker", marker)

        except urllib.error.HTTPError as error:
            print(f"Ошибка API MAX: HTTP {error.code}")

            if error.code in (401, 403, 405, 409):
                print(
                    "Остановлено. Проверь токен, разрешения "
                    "и отсутствие активного Webhook."
                )
                return

            time.sleep(5)

        except urllib.error.URLError as error:
            print("Ошибка соединения:", error.reason)
            time.sleep(5)

        except TimeoutError:
            print("Тайм-аут соединения. Повторяем запрос.")
            time.sleep(3)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nАдаптер остановлен.")
    except RuntimeError as error:
        print(error)