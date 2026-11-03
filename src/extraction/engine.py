"""OCR engines: EasyOCR (Bengali and English) and a scripted fake for tests.

Purpose: read the text boxes of a page image. Everything above this module works with `Box`
    values and does not care which engine made them.
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (section 10).

EasyOCR runs on the CPU: the first start downloads its Bengali and English models (about
100 MB, once; `python tasks.py ocr-setup` does it ahead of time) and a page takes a minute or
two, so reading is done by a background worker (src/extraction/worker.py), never inside a
web request. EasyOCR is not trained on handwriting (its own roadmap lists handwriting as
future work): handwritten values come out with low confidence or wrong, and a person always
corrects them. Nothing here judges a signature.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Box:
    """A piece of text with how sure the engine was (0 to 1) and where it is (pixels)."""

    text: str
    conf: float
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return max(self.y1 - self.y0, 1.0)


class OcrEngine(Protocol):
    name: str
    version: str

    def read(self, image: Any) -> list[Box]:  # image: a PIL image
        ...


class EasyOcrEngine:
    name = "easyocr"

    def __init__(self, languages: list[str]) -> None:
        self.languages = languages
        self._reader: Any = None
        self._lock = threading.Lock()
        import easyocr

        self.version = easyocr.__version__

    def _load(self) -> Any:
        with self._lock:
            if self._reader is None:
                import easyocr

                self._reader = easyocr.Reader(self.languages, gpu=False, verbose=False)
            return self._reader

    def read(self, image: Any) -> list[Box]:
        import numpy as np

        reader = self._load()
        boxes = []
        for points, text, conf in reader.readtext(np.array(image.convert("RGB"))):
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            boxes.append(Box(str(text), float(conf), min(xs), min(ys), max(xs), max(ys)))
        return boxes


class FakeOcrEngine:
    """Returns the boxes it was given, one list per page read (for tests)."""

    name = "fake"
    version = "test"

    def __init__(self, pages: list[list[Box]]) -> None:
        self.pages = list(pages)
        self.calls = 0

    def read(self, image: Any) -> list[Box]:
        page = self.pages[min(self.calls, len(self.pages) - 1)]
        self.calls += 1
        return list(page)


_engine: OcrEngine | None = None
_engine_lock = threading.Lock()


def get_engine(config: dict[str, Any]) -> OcrEngine:
    """The shared engine. `CREDLENS_OCR_ENGINE=none` means no engine is available."""
    global _engine
    with _engine_lock:
        if _engine is None:
            if os.environ.get("CREDLENS_OCR_ENGINE", "").strip().lower() == "none":
                raise RuntimeError("OCR is switched off (CREDLENS_OCR_ENGINE=none).")
            _engine = EasyOcrEngine(list(config["ocr"]["languages"]))
        return _engine


def set_engine(engine: OcrEngine | None) -> None:
    """Install an engine (tests) or forget it."""
    global _engine
    with _engine_lock:
        _engine = engine
