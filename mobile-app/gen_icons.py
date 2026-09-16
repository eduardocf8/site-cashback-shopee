from PIL import Image
import os

SRC = "../static/icons/icon-512.png"
RES = "android/app/src/main/res"

# legacy full-bleed launcher icon (square + round use same source)
LEGACY_SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

# adaptive icon foreground canvas sizes (108dp canvas at each density)
FOREGROUND_SIZES = {
    "mdpi": 108,
    "hdpi": 162,
    "xhdpi": 216,
    "xxhdpi": 324,
    "xxxhdpi": 432,
}

src = Image.open(SRC).convert("RGBA")

for density, size in LEGACY_SIZES.items():
    resized = src.resize((size, size), Image.LANCZOS)
    folder = f"{RES}/mipmap-{density}"
    resized.save(f"{folder}/ic_launcher.png")
    resized.save(f"{folder}/ic_launcher_round.png")
    print(f"legacy {density}: {size}x{size} ok")

for density, canvas_size in FOREGROUND_SIZES.items():
    # logo occupies ~62% of the canvas (safe zone for adaptive icons), centered
    logo_size = int(canvas_size * 0.62)
    logo = src.resize((logo_size, logo_size), Image.LANCZOS)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    offset = ((canvas_size - logo_size) // 2, (canvas_size - logo_size) // 2)
    canvas.paste(logo, offset, logo)
    folder = f"{RES}/mipmap-{density}"
    canvas.save(f"{folder}/ic_launcher_foreground.png")
    print(f"foreground {density}: canvas {canvas_size}x{canvas_size}, logo {logo_size}x{logo_size} ok")

# Play Store listing icon (512x512, required exactly this size)
src.resize((512, 512), Image.LANCZOS).save("play_store_icon_512.png")
print("play store icon ok")
