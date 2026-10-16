"""Read a research paper PDF into page-numbered text."""

from __future__ import annotations

import io
from dataclasses import dataclass

from pypdf import PdfReader


class PaperError(Exception):
    """A user-safe error about the uploaded file."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class Paper:
    filename: str
    pages: list[str]

    def as_prompt_text(self, max_chars: int = 60000) -> str:
        """Paper text with [Page N] markers so reviewers can cite page numbers."""
        text = "\n\n".join(f"[Page {i}]\n{page}" for i, page in enumerate(self.pages, 1))
        return text[:max_chars]

    def full_text(self) -> str:
        return "\n".join(self.pages)


def read_pdf(data: bytes, filename: str, max_mb: int = 15, max_pages: int = 40) -> Paper:
    if not data:
        raise PaperError("The uploaded file is empty.", 400)
    if len(data) > max_mb * 1024 * 1024:
        raise PaperError(f"The file is larger than {max_mb} MB.", 413)
    if not data[:1024].lstrip().startswith(b"%PDF-"):
        raise PaperError("Please upload a PDF file.", 415)
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise PaperError("The PDF is password-protected.")
        if len(reader.pages) > max_pages:
            raise PaperError(f"The PDF has more than {max_pages} pages.", 413)
        pages = [" ".join((page.extract_text() or "").split()) for page in reader.pages]
    except PaperError:
        raise
    except Exception as exc:  # pypdf raises many different errors for broken files
        raise PaperError("The PDF could not be read; it may be damaged.") from exc
    if sum(len(p) for p in pages) < 200:
        raise PaperError("No readable text was found. The PDF may be a scanned image.")
    return Paper(filename=filename[:200], pages=pages)
