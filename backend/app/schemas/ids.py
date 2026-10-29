from typing import Annotated

from pydantic import PlainSerializer


# DuckDB BIGINT identifiers routinely exceed JavaScript's 53-bit safe integer
# range. Keep them as integers inside Python and serialize them as decimal
# strings at the HTTP boundary.
ApiId = Annotated[int, PlainSerializer(lambda value: str(value), return_type=str, when_used="json")]


__all__ = ["ApiId"]
