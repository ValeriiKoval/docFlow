#!/usr/bin/env python3
"""Turn clean synthetic PDFs into 'scanned' image-only PDFs with controlled degradation.

Labels are not copied: scans share ground truth with the clean PDF of the same
name (eval/dataset/labels/<name>.json).

Usage:
    pip install -r requirements.txt        # pypdfium2, pillow, numpy — no system deps
    python eval/make_scans.py --levels light medium heavy --seed 42

Result: eval/dataset/scans/<level>/<name>.pdf
"""
import argparse
import io
import random
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageEnhance, ImageFilter

HERE = Path(__file__).resolve().parent

# angle (deg), blur radius, noise sigma, jpeg quality, contrast, shadow strength
LEVELS = {
    "light":  dict(angle=1.0, blur=0.6, noise=6,  jpeg=70, contrast=0.95, shadow=0.10),
    "medium": dict(angle=2.5, blur=1.2, noise=14, jpeg=45, contrast=0.85, shadow=0.25),
    "heavy":  dict(angle=4.5, blur=2.0, noise=24, jpeg=25, contrast=0.70, shadow=0.40),
}


def rasterize(pdf: Path, dpi: int = 150) -> Image.Image:
    """Render the first page to a grayscale image."""
    doc = pdfium.PdfDocument(str(pdf))
    try:
        return doc[0].render(scale=dpi / 72).to_pil().convert("L")
    finally:
        doc.close()


def degrade(img: Image.Image, p: dict, rng: random.Random) -> Image.Image:
    angle = rng.uniform(-p["angle"], p["angle"])
    img = img.rotate(angle, expand=True, fillcolor=255, resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(p["blur"] * rng.uniform(0.7, 1.3)))
    img = ImageEnhance.Contrast(img).enhance(p["contrast"])
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape
    # uneven lighting: linear gradient from a random edge (scanner / phone shadow)
    gx = np.linspace(0, 1, w)[None, :] if rng.random() < 0.5 else np.linspace(1, 0, w)[None, :]
    arr = arr * (1 - p["shadow"] * gx)
    # sensor noise
    nrng = np.random.default_rng(rng.randint(0, 2**31))
    arr = arr + nrng.normal(0, p["noise"], arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(HERE / "dataset"))
    ap.add_argument("--levels", nargs="+", default=["light", "medium", "heavy"], choices=LEVELS)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    src = Path(a.src)
    rng = random.Random(a.seed)
    pdfs = sorted((src / "pdf").glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs in {src / 'pdf'}. Run generate_dataset.py first.")
    for level in a.levels:
        out_pdf = src / "scans" / level
        out_pdf.mkdir(parents=True, exist_ok=True)
        for pdf in pdfs:
            img = degrade(rasterize(pdf, a.dpi), LEVELS[level], rng)
            # round-trip through JPEG in memory so compression artifacts are real
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=LEVELS[level]["jpeg"])
            buf.seek(0)
            Image.open(buf).convert("RGB").save(out_pdf / pdf.name, "PDF", resolution=a.dpi)
        print(f"{level}: {len(pdfs)} scans -> {out_pdf}")


if __name__ == "__main__":
    main()
