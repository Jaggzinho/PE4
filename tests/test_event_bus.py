from __future__ import annotations

import unittest
import logging

from pe3_qc_app.core.event_bus import EventBus


class TestEventBus(unittest.TestCase):
    def test_emit_continues_on_exception(self) -> None:
        logging.getLogger("pe3_qc_app.event_bus").disabled = True
        bus = EventBus()
        seen: list[str] = []

        def bad() -> None:
            raise RuntimeError("boom")

        def ok() -> None:
            seen.append("ok")

        bus.subscribe("x", bad)
        bus.subscribe("x", ok)
        bus.emit("x")
        self.assertEqual(seen, ["ok"])
        logging.getLogger("pe3_qc_app.event_bus").disabled = False


if __name__ == "__main__":
    unittest.main()
