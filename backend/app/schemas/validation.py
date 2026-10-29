from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("Must not be blank")
    return value


NonBlankStr = Annotated[str, Field(min_length=1), AfterValidator(_non_blank)]
