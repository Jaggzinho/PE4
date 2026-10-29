from __future__ import annotations

import pytest

from pe3_qc_app.services.qc_avg import avg_of_texts


def test_avg_of_texts_partial_values() -> None:
    assert avg_of_texts(["10", "", "20", "", ""], decimals=2) == "15.00"


def test_avg_of_texts_comma_decimal() -> None:
    assert avg_of_texts(["10,5", "9,5"], decimals=2) == "10.00"


def test_avg_of_texts_empty_all_returns_none() -> None:
    assert avg_of_texts(["", "  ", ""], decimals=2) is None


def test_avg_of_texts_invalid_raises() -> None:
    with pytest.raises(ValueError):
        avg_of_texts(["10", "abc"], decimals=2)

