from __future__ import annotations

from collections.abc import Callable
import logging


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[], None]]] = {}

    def subscribe(self, event: str, cb: Callable[[], None]) -> None:
        self._subs.setdefault(event, []).append(cb)

    def emit(self, event: str) -> None:
        for cb in list(self._subs.get(event, [])):
            try:
                cb()
            except Exception:  # noqa: BLE001
                logging.getLogger("pe3_qc_app.event_bus").exception("EventBus callback failed (event=%s)", event)
