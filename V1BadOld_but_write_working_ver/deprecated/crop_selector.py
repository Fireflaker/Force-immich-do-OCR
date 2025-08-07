#!/usr/bin/env python3
"""Interactive crop selector for OCR tuning.

Usage::

    # Single image
    python crop_selector.py path/to/image.jpg

    # Entire folder – will iterate over every picture, press ESC to skip
    python crop_selector.py path/to/folder

Click-and-drag to draw a rectangle around the text you want to OCR.  When you
release the mouse button the coordinates are printed to stdout in the format::

    IMG_1234.jpg: left top right bottom  (width×height)

You can copy these numbers into your OCR script for a precise crop.

Requirements:
    pip install opencv-python

Press ESC or close the window to move to the next image (or quit if none).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import cv2  # type: ignore

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif"}

def iter_images(path: Path) -> Iterable[Path]:
    """Yield one or many image files depending on *path*."""
    if path.is_file():
        yield path
    elif path.is_dir():
        for p in sorted(path.iterdir()):
            if p.suffix.lower() in IMAGE_SUFFIXES:
                yield p
    else:
        print(f"Path {path} does not exist", file=sys.stderr)


def select_roi(img_path: Path) -> None:
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"Failed to read {img_path}", file=sys.stderr)
        return

    window_name = "Draw rectangle and press ENTER / SPACE – ESC to skip"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, img)

    # selectROI returns (x, y, w, h)
    x, y, w, h = cv2.selectROI(window_name, img, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(window_name)

    if w == 0 or h == 0:
        print(f"{img_path.name}: skipped")
        return

    left, top, right, bottom = x, y, x + w, y + h
    print(f"{img_path.name}: {left} {top} {right} {bottom}  ({w}×{h})")


def main() -> None:  # noqa: D401
    parser = argparse.ArgumentParser(description="Interactively pick crop rectangle(s) for OCR")
    parser.add_argument("path", help="Image file or directory of images")
    args = parser.parse_args()

    for img_path in iter_images(Path(args.path)):
        select_roi(img_path)


if __name__ == "__main__":
    main()
