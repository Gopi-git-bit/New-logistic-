"""Engine-agnostic OCR provider (R2 decision point deferred).

The OCRExtractor protocol is the fixed interface. The PRD says:
> workers/ocr_provider.py interface is engine-agnostic.
> Choose Tesseract (self-hosted, free) vs vision-LLM (better accuracy, per-call cost).

Implementors:
- TesseractExtractor (default, self-hosted)
- VisionLLMExtractor (future, needs API key)

Usage:
    provider = make_ocr_provider("tesseract")  # reads OCR_PROVIDER env
    result = provider.extract(image_bytes, "image/jpeg")
    print(result.raw_text, result.confidence)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class OCRRawResult:
    """Structured output from any OCR engine."""
    raw_text: str
    confidence: float       # 0.0–1.0 (best-effort; Tesseract returns per-word avg)
    provider: str           # 'tesseract' | 'vision_llm' | ...
    word_count: int = 0
    char_count: int = 0

    def __post_init__(self):
        # derived fields auto-computed
        if self.word_count == 0 and self.raw_text:
            object.__setattr__(self, 'word_count', len(self.raw_text.split()))
        if self.char_count == 0 and self.raw_text:
            object.__setattr__(self, 'char_count', len(self.raw_text))


@runtime_checkable
class OCRExtractor(Protocol):
    """Protocol that every OCR engine must satisfy."""

    @property
    def provider_name(self) -> str: ...

    def extract(self, image_bytes: bytes, content_type: str = "image/jpeg") -> OCRRawResult: ...


class TesseractExtractor:
    """Self-hosted, free OCR via tesseract CLI.

    Requires: tesseract-ocr installed (Dockerfile installs it).
    Falls back to provider='tesseract_unavailable' if binary missing.
    """

    def __init__(self, tesseract_cmd: str | None = None):
        self._cmd = tesseract_cmd or os.getenv("TESSERACT_CMD", "tesseract")

    @property
    def provider_name(self) -> str:
        return "tesseract"

    def extract(self, image_bytes: bytes, content_type: str = "image/jpeg") -> OCRRawResult:
        suffix = _content_type_to_suffix(content_type)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
            tmp_in.write(image_bytes)
            tmp_in.flush()
            tmp_path = Path(tmp_in.name)

        try:
            return self._run_tesseract(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _run_tesseract(self, image_path: Path) -> OCRRawResult:
        out_base = image_path.with_suffix("")
        try:
            subprocess.run(
                [self._cmd, str(image_path), str(out_base),
                 "--oem", "3", "--psm", "6", "-l", "eng"],
                capture_output=True, check=True, timeout=30,
            )
        except FileNotFoundError:
            return OCRRawResult(
                raw_text="", confidence=0.0,
                provider="tesseract_unavailable",
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            return OCRRawResult(
                raw_text="", confidence=0.0,
                provider=f"tesseract_error:{type(exc).__name__}",
            )

        tsv_path = out_base.with_suffix(".tsv")
        try:
            return self._parse_tsv(tsv_path)
        finally:
            tsv_path.unlink(missing_ok=True)

    def _parse_tsv(self, tsv_path: Path) -> OCRRawResult:
        words: list[str] = []
        confs: list[float] = []

        try:
            lines = tsv_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except FileNotFoundError:
            return OCRRawResult(raw_text="", confidence=0.0,
                                provider="tesseract")

        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 12 and parts[0] not in ("level", ""):
                conf_val = float(parts[10]) if parts[10] not in ("", "-1") else 0.0
                word = parts[11].strip()
                if word and conf_val > 0:
                    words.append(word)
                    confs.append(conf_val)

        raw = " ".join(words)
        avg_conf = sum(confs) / len(confs) / 100.0 if confs else 0.0
        return OCRRawResult(
            raw_text=raw,
            confidence=round(avg_conf, 4),
            provider="tesseract",
        )


def _content_type_to_suffix(ct: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
        "image/bmp": ".bmp",
        "application/pdf": ".pdf",
    }.get(ct, ".jpg")


def make_ocr_provider(name: str | None = None) -> OCRExtractor:
    """Factory — defaults to Tesseract. Swap to VisionLLM when ready."""
    engine = name or os.getenv("OCR_PROVIDER", "tesseract")
    if engine == "tesseract":
        return TesseractExtractor()
    raise ValueError(f"Unknown OCR provider: {engine!r} (choose 'tesseract')")
