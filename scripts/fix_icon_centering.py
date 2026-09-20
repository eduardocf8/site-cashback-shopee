"""Recentraliza verticalmente o conteúdo dos ícones PNG do cash-b (bug pré-existente
no icon-512.png/192/180: o monograma 'cb' estava desalinhado pra baixo)."""
from PIL import Image, ImageChops

FILES = [
    "static/icons/icon-512.png",
    "static/icons/icon-192.png",
    "static/icons/icon-180.png",
]

for path in FILES:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    bg = im.getpixel((0, 0))
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg))
    bbox = diff.getbbox()
    left, top, right, bottom = bbox
    content = im.crop(bbox)
    cw, ch = content.size

    canvas = Image.new("RGB", (w, h), bg)
    new_left = (w - cw) // 2
    new_top = (h - ch) // 2
    canvas.paste(content, (new_left, new_top))
    canvas.save(path)

    # confere o resultado
    diff2 = ImageChops.difference(canvas, Image.new("RGB", canvas.size, bg))
    bbox2 = diff2.getbbox()
    print(f"{path}: bbox antes {bbox} -> bbox depois {bbox2} (canvas {w}x{h})")
