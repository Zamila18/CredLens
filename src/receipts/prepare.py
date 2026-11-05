"""Straighten a receipt photo before it is read.

Purpose: a phone photo is rarely square to the page. Rows of text then slope across the picture,
    and the table's rows and columns can no longer be told apart (the first check of the reader
    got almost every amount wrong on tilted photos). This finds the tilt from the lines of text
    themselves and turns the picture back, which is what a person does with the paper.
Owner role: C (assessment).
Implements: "verify the OCR to work properly" of the Records Desk redesign.

The angle is the one that makes the dark text rows most distinct from the white gaps between
them (the standard projection-profile method). A picture with too little text, or with no
clear angle, is left as it was.
"""

from __future__ import annotations

from typing import Any

MAX_ANGLE = 10.0
COARSE = 0.5
FINE = 0.1
MIN_GAIN = 1.05  # the best angle must beat "no turn" by this factor, else leave it alone


def _score(binary: Any, angle: float) -> float:
    import cv2
    import numpy as np

    h, w = binary.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    turned = cv2.warpAffine(binary, matrix, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    profile = turned.sum(axis=1).astype("float64")
    return float(np.var(np.diff(profile)))


def estimate_tilt(image: Any) -> float:
    """The angle, in degrees, to turn the picture by (counter-clockwise positive); 0 if unclear."""
    import cv2
    import numpy as np

    gray = np.asarray(image.convert("L"))
    scale = 700.0 / max(gray.shape[1], 1)
    if scale < 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12
    )
    if binary.sum() < 255 * 200:  # almost no ink
        return 0.0
    angles = np.arange(-MAX_ANGLE, MAX_ANGLE + COARSE, COARSE)
    coarse = max(angles, key=lambda a: _score(binary, float(a)))
    fine = np.arange(coarse - COARSE, coarse + COARSE + FINE, FINE)
    best = max(fine, key=lambda a: _score(binary, float(a)))
    base = _score(binary, 0.0)
    if base <= 0 or _score(binary, float(best)) < MIN_GAIN * base:
        return 0.0
    return float(best)


def straighten(image: Any) -> Any:
    """The picture turned upright. A tilt of under a third of a degree is not worth a resample."""
    from PIL import Image

    angle = estimate_tilt(image)
    if abs(angle) < 0.3:
        return image
    return image.convert("RGB").rotate(
        angle, expand=True, fillcolor=(255, 255, 255), resample=Image.BICUBIC
    )
