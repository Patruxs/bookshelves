from __future__ import annotations

import importlib
from io import BytesIO
from pathlib import Path
from types import ModuleType
from zipfile import BadZipFile

from .constants import COVER_QUALITY, COVER_SIZE_WARNING_BYTES, COVER_WIDTH

WHITE = (255, 255, 255)
MIN_COVER_QUALITY = 20
COVER_QUALITY_STEP = 10


def import_pymupdf() -> ModuleType | None:
    for module_name in ("pymupdf", "fitz"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    return None


pymupdf = import_pymupdf()
HAS_PYMUPDF = pymupdf is not None

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    from docx import Document as DocxDocument
    from docx.opc.exceptions import OpcError
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False


def dependency_status() -> dict[str, bool]:
    return {
        "PyMuPDF": HAS_PYMUPDF,
        "Pillow": HAS_PILLOW,
        "python-docx": HAS_PYTHON_DOCX,
    }


def extract_cover(file_path: Path, output_path: Path) -> bool:
    extracted, _reason = extract_cover_with_reason(file_path, output_path)
    return extracted


def extract_cover_with_reason(file_path: Path, output_path: Path) -> tuple[bool, str]:
    ext = file_path.suffix.lower()
    if ext in {".pdf", ".epub"}:
        return _render_first_page(file_path, output_path)
    if ext == ".docx":
        return _extract_docx_image(file_path, output_path)
    return False, f"unsupported format {ext or '(none)'}"


def _render_first_page(file_path: Path, output_path: Path) -> tuple[bool, str]:
    if pymupdf is None:
        return False, "PyMuPDF is not installed"
    if not HAS_PILLOW:
        return False, "Pillow is not installed"
    try:
        doc = pymupdf.open(str(file_path))
        try:
            if doc.page_count == 0:
                return False, "document has no pages"
            first_page = doc[0]
            zoom = render_zoom(first_page.rect.width)
            pix = first_page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            save_webp(img, output_path)
            return True, ""
        finally:
            doc.close()
    except (OSError, ValueError, RuntimeError) as exc:
        return False, _describe(exc)


def _extract_docx_image(file_path: Path, output_path: Path) -> tuple[bool, str]:
    if not HAS_PYTHON_DOCX:
        return False, "python-docx is not installed"
    if not HAS_PILLOW:
        return False, "Pillow is not installed"
    try:
        doc = DocxDocument(str(file_path))
        for rel in doc.part.rels.values():
            if "image" not in rel.reltype:
                continue
            try:
                img = Image.open(BytesIO(rel.target_part.blob))
                img.load()
                save_webp(img, output_path)
            except Exception:
                continue
            return True, ""
    except (OSError, ValueError, KeyError, BadZipFile, OpcError) as exc:
        return False, _describe(exc)
    return False, "no embedded image found"


def render_zoom(page_width: float) -> float:
    if page_width <= 0:
        return 1.0
    return COVER_WIDTH / page_width


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "P":
        img = img.convert("RGBA")
    if img.mode in ("RGBA", "LA", "PA"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, WHITE)
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def cover_qualities() -> list[int]:
    qualities = list(range(COVER_QUALITY, MIN_COVER_QUALITY, -COVER_QUALITY_STEP))
    return [*qualities, MIN_COVER_QUALITY]


def encode_webp(img: Image.Image, quality: int) -> bytes:
    buffer = BytesIO()
    img.save(buffer, "WEBP", quality=quality, method=6)
    return buffer.getvalue()


def save_webp(img: Image.Image, output_path: Path) -> None:
    img = _flatten_to_rgb(img)
    if img.width > COVER_WIDTH:
        ratio = COVER_WIDTH / img.width
        img = img.resize((COVER_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
    encoded = b""
    for quality in cover_qualities():
        encoded = encode_webp(img, quality)
        if len(encoded) <= COVER_SIZE_WARNING_BYTES:
            break
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encoded)
