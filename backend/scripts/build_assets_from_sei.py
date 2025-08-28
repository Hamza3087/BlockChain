#!/usr/bin/env python3
import os
import json
import glob
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_ROOT = ROOT / "migration_output"
ASSETS_DIR = ROOT / "assets"

def latest_run_dir():
    candidates = sorted([p for p in MIGRATION_ROOT.glob("*") if p.is_dir()])
    if not candidates:
        raise SystemExit("No migration_output directories found")
    return candidates[-1]

def load_sei_json(nft_dir: Path):
    fp = nft_dir / "01_sei_original_data.json"
    with fp.open() as f:
        return json.load(f)

def download_image(url: str, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r, open(dst, 'wb') as out:
        out.write(r.read())

def to_metaplex_json(sei: dict, idx: int, image_filename: str) -> dict:
    md = sei.get("metadata", {})
    name = md.get("name") or f"Sei NFT #{sei.get('token_id', idx)}"
    symbol = md.get("symbol") or "SEI"
    description = md.get("description") or md.get("collection") or "Imported from Sei"
    attributes = md.get("attributes") or []
    collection = md.get("collection") or "Sei Collection"
    return {
        "name": f"{name}",
        "symbol": symbol,
        "description": description,
        "image": image_filename,
        "seller_fee_basis_points": 500,
        "attributes": attributes,
        "properties": {
            "files": [{"uri": image_filename, "type": "image/png"}],
            "category": "image"
        },
        "collection": {"name": collection, "family": collection}
    }

def build_assets():
    run_dir = latest_run_dir()
    nft_dirs = sorted([p for p in run_dir.glob("nft_*") if p.is_dir()], key=lambda p: int(p.name.split('_')[-1]))
    if not nft_dirs:
        raise SystemExit(f"No nft_* directories in {run_dir}")

    # Prepare assets dir cleanly
    if ASSETS_DIR.exists():
        # keep simple: clean existing files
        for p in ASSETS_DIR.glob("*"):
            if p.is_file():
                p.unlink()
    else:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    for idx, nd in enumerate(nft_dirs):
        try:
            sei = load_sei_json(nd)
            md = sei.get("metadata", {})
            img_url = md.get("image")
            if not img_url:
                print(f"Skipping {nd.name}: no image URL")
                continue
            img_name = f"{count}.png"
            img_path = ASSETS_DIR / img_name
            print(f"Downloading image: {img_url} -> {img_path}")
            download_image(img_url, img_path)

            mjson = to_metaplex_json(sei, count, img_name)
            json_path = ASSETS_DIR / f"{count}.json"
            with json_path.open('w') as f:
                json.dump(mjson, f, indent=2)

            count += 1
        except Exception as e:
            print(f"Error processing {nd}: {e}")

    print(f"Prepared {count} assets in {ASSETS_DIR}")

if __name__ == "__main__":
    build_assets()

