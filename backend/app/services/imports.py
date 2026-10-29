from __future__ import annotations

from pathlib import Path
import tempfile
from zipfile import BadZipFile, ZipFile


class InvalidWorkbookError(ValueError):
    pass


class WorkbookTooLargeError(ValueError):
    pass


class ImportService:
    allowed_extensions = {".xlsm", ".xlsx"}
    allowed_content_types = {
        "application/octet-stream",
        "application/vnd.ms-excel.sheet.macroenabled.12",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    def save_validated_upload(self, upload, *, max_bytes: int) -> Path:
        suffix = Path(upload.filename or "").suffix.casefold()
        if suffix not in self.allowed_extensions:
            raise InvalidWorkbookError("Expected .xlsm/.xlsx upload")
        content_type = (upload.content_type or "application/octet-stream").casefold()
        if content_type not in self.allowed_content_types:
            raise InvalidWorkbookError("Unsupported workbook content type")

        path: Path | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as destination:
                path = Path(destination.name)
                while chunk := upload.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise WorkbookTooLargeError(f"Workbook exceeds {max_bytes} bytes")
                    destination.write(chunk)
            if total == 0:
                raise InvalidWorkbookError("Workbook is empty")
            self.validate_structure(path)
            return path
        except Exception:
            if path is not None:
                path.unlink(missing_ok=True)
            raise
        finally:
            upload.file.close()

    @staticmethod
    def validate_structure(path: Path) -> None:
        try:
            with ZipFile(path) as workbook:
                names = set(workbook.namelist())
        except BadZipFile as exc:
            raise InvalidWorkbookError("Workbook is not a valid Office file") from exc
        required = {"[Content_Types].xml", "xl/workbook.xml"}
        if not required.issubset(names):
            raise InvalidWorkbookError("Workbook structure is incomplete")
