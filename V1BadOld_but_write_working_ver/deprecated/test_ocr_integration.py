#!/usr/bin/env python3
"""Quick integration test against a live Immich instance.

Prerequisites
-------------
1. Immich server running and reachable.
2. API key with *asset.upload* + *asset.read* + *asset.update* scopes.
3. OCR container already running and pointing at the same Immich (so it will
   see the file we upload).

What the test does
------------------
1. Upload a known test screenshot (png/jpg) via Immich upload API.
2. Poll Immich until the asset becomes *ready* and OCR service has PATCHed the
   description ("OCR: …").
3. Print success/failure and the final description string.

Usage
-----
    export IMMICH_URL=http://immich:3001
    export IMMICH_API_KEY=your_api_key
    python test_ocr_integration.py path/to/screenshot.png
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

IMMICH_URL = os.environ.get("IMMICH_URL", "http://localhost:3001").rstrip("/")
API_KEY = os.environ.get("IMMICH_API_KEY")

HEADERS = {"x-api-key": API_KEY or "", "Accept": "application/json"}

UPLOAD_ENDPOINT = f"{IMMICH_URL}/api/assets/upload"
GET_ASSET_ENDPOINT = f"{IMMICH_URL}/api/assets"  # /{assetId} later

TIMEOUT_SEC = 120  # how long to wait for OCR patch


def upload_image(path: Path) -> str:
    """Upload image → return assetId."""
    files = {"assetData": open(path, "rb")}
    data = {"deviceAssetId": path.stem, "deviceId": "ocr-test", "isFavorite": "false"}
    resp = requests.post(UPLOAD_ENDPOINT, headers=HEADERS, files=files, data=data, timeout=60)
    resp.raise_for_status()
    res_json: list[dict[str, Any]] = resp.json()
    asset_id = res_json[0]["id"]  # upload returns a list
    return asset_id


def get_asset(asset_id: str) -> dict[str, Any]:
    resp = requests.get(f"{GET_ASSET_ENDPOINT}/{asset_id}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main(img_path: Path) -> None:
    if not API_KEY:
        print("IMMICH_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    asset_id = upload_image(img_path)
    print("Uploaded", img_path.name, "→ asset", asset_id)

    start = time.time()
    while time.time() - start < TIMEOUT_SEC:
        asset = get_asset(asset_id)
        desc = asset.get("description")
        if desc and desc.startswith("OCR:"):
            print("SUCCESS: description set =>", desc)
            return
        time.sleep(5)
    print("FAIL: OCR description not patched within timeout")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_ocr_integration.py screenshot.png", file=sys.stderr)
        sys.exit(2)
    main(Path(sys.argv[1]))
