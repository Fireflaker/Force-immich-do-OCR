#!/usr/bin/env python3
"""Run OCR on every image under /data and print result."""
import pathlib,re,sys
from io import BytesIO
from PIL import Image,ImageOps
import pytesseract
import shutil, platform, os
# Ensure Tesseract executable is found on Windows even if not in PATH
if platform.system() == "Windows":
    if shutil.which("tesseract") is None:
        default_path = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        if os.path.exists(default_path):
            pytesseract.pytesseract.tesseract_cmd = default_path

# ---------------------------------------------------------------------------
# ROI_LIST – Where on the screen we expect the tiny "Reply to …" username.
# ---------------------------------------------------------------------------
# Each entry is a tuple of FOUR RELATIVE FRACTIONS:
#     (left_frac, top_frac, right_frac, bottom_frac)
# All values are between 0 and 1 and are multiplied by the actual width/height
# at runtime, so the same fractions work for any resolution with the same
# aspect/layout.
#
# How to add a new layout when screenshots change again:
#   1. Run   python crop_selector.py  your_image.png
#   2. Draw a tight rectangle around the username (include the ellipsis).
#   3. Copy the printed pixel coords:  left  top  right  bottom .
#   4. Convert to fractions → divide by width/height respectively.
#      E.g.   left=258 on width 1080  →  258/1080 ≈ 0.239
#   5. Append a new tuple here and (optionally) add that resolution to
#      SCREENSHOT_SIZES below so the test script skips non-screenshots.
#   6. Commit – both the test script and ocr_service.py share the same list.
#
# Current known layouts:
ROI_LIST = [
    (0.24, 0.92, 0.78, 0.97),  # 1080×2412 layout
    (0.23, 0.935, 0.78, 0.97),  # 1440×3200 layout
]


def get_text(img):
    """Return text from either the ROI rectangle or fallback bottom crops."""
    w, h = img.size

    # 1. Try multiple ROI rectangles first
    for l_f, t_f, r_f, b_f in ROI_LIST:
        roi_box = (int(l_f * w), int(t_f * h), int(r_f * w), int(b_f * h))
        crop = img.crop(roi_box)
        gray = ImageOps.grayscale(crop)
        txt = pytesseract.image_to_string(ImageOps.autocontrast(gray, cutoff=2), config="--psm 6").strip()
        if txt:
            return txt

    # 2. Fallback – progressive bigger strips from the bottom
    for frac in (0.75, 0.6, 0.5):
        crop = img.crop((0, int(h * frac), w, h))
        gray = ImageOps.grayscale(crop)
        txt = pytesseract.image_to_string(ImageOps.autocontrast(gray, cutoff=2), config="--psm 6").strip()
        if txt:
            return txt
    return ""

# SCREENSHOT_SIZES – quick check to skip photos that are not screenshots.
# Add resolutions (width, height) of any new layouts you support.
SCREENSHOT_SIZES = {
    (1080, 2412), (2412, 1080),
    (720, 1608), (1608, 720),
    (1440, 3200), (3200, 1440),
}

def main(folder: pathlib.Path):
    for p in folder.iterdir():
        if p.suffix.lower() not in ('.jpg','.jpeg','.png'):
            continue
        with Image.open(p) as im:
            if im.size not in SCREENSHOT_SIZES:
                print(f"{p.name} -> SKIPPED (not screenshot)")
                continue
            raw = get_text(im)
        # Try primary pattern with explicit ellipsis
        m = re.search(r"Reply to\s+([^\n\r]{2,60}?)\.\.\.", raw, re.I)
        if m:
            user = m.group(1).strip()
        else:
            # Fallback pattern without forcing ellipsis
            m = re.search(r"Reply to\s+([^\n\r]{2,60})", raw, re.I)
            user = m.group(1).strip() if m else None
        if user and user.endswith("..."):
            user = user[:-3].rstrip()
        # Final fallback: take first three words of OCR output
        if not user:
            tokens = raw.replace("\n", " ").split()
            user = " ".join(tokens[:3]) if tokens else None
        print(f"{p.name} -> {user or 'NO USER'}")
        print(' RAW:', raw.replace('\n',' '))

if __name__=='__main__':
    folder = pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path('test_images')
    sys.exit(main(folder))
