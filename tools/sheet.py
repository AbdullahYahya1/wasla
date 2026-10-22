"""Tile screenshots into one contact sheet: python tools/sheet.py out.png a.png b.png ..."""
import sys
from PIL import Image

out, files = sys.argv[1], sys.argv[2:]
ims = [Image.open(f).convert("RGB") for f in files]
w, h = ims[0].size
scale = 0.5
cols = 2
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (int(w * scale) * cols + 10 * (cols - 1), int(h * scale) * rows + 10 * (rows - 1)), "white")
for i, im in enumerate(ims):
    im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    sheet.paste(im, ((i % cols) * (int(w * scale) + 10), (i // cols) * (int(h * scale) + 10)))
sheet.save(out)
