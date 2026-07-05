from typing import Any


class NoopNotifier:
    def send(self, message: dict[str, Any]) -> None:
        return None
