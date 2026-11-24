"""Input preprocessing (type sniffing, PDF inspection) and original-file storage."""
import hashlib
from dataclasses import dataclass
from pathlib import Path

EXT = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
       "image/gif": ".gif"}


class InputError(ValueError):
    def __init__(self, message, status_code=422):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Inspected:
    sha256: str
    media_type: str
    size_bytes: int
    pages: int | None
    has_text_layer: bool | None


def sniff(data: bytes) -> str:
    """Detect the type from magic bytes; the client-declared content type is not trusted."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    raise InputError("unsupported file type: expected PDF, JPEG, PNG, WEBP or GIF", 415)


def inspect(data: bytes, max_mb: int, max_pages: int) -> Inspected:
    if not data:
        raise InputError("empty file", 400)
    if len(data) > max_mb * 1024 * 1024:
        raise InputError(f"file larger than {max_mb} MB", 413)
    media_type = sniff(data)
    pages = text_layer = None
    if media_type == "application/pdf":
        import pypdfium2 as pdfium
        try:
            doc = pdfium.PdfDocument(data)
        except Exception as e:
            raise InputError(f"unreadable PDF: {e}") from e
        try:
            pages = len(doc)
            if pages == 0:
                raise InputError("PDF has no pages")
            if pages > max_pages:
                raise InputError(f"PDF has {pages} pages, limit is {max_pages}", 413)
            # born-digital PDFs have a text layer; scans saved as PDF usually do not
            text = doc[0].get_textpage().get_text_range()
            text_layer = len(text.strip()) >= 20
        finally:
            doc.close()
    return Inspected(hashlib.sha256(data).hexdigest(), media_type, len(data), pages, text_layer)


def store(storage_dir: Path, sha256: str, media_type: str, data: bytes) -> Path:
    """Content-addressed storage: <dir>/<ab>/<sha256>.<ext>. Idempotent."""
    path = Path(storage_dir) / sha256[:2] / f"{sha256}{EXT[media_type]}"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return path
