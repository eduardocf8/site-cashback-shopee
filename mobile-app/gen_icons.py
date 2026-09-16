from PIL import Image
import glob
import os

BRAND_PURPLE = (109, 40, 217)  # #6d28d9


def make_splash(canvas_w, canvas_h, logo_src):
    short_side = min(canvas_w, canvas_h)
    logo_size = int(short_side * 0.35)
    logo = logo_src.resize((logo_size, logo_size), Image.LANCZOS)
    canvas = Image.new("RGB", (canvas_w, canvas_h), BRAND_PURPLE)
    offset = ((canvas_w - logo_size) // 2, (canvas_h - logo_size) // 2)
    canvas.paste(logo, offset)
    return canvas

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

# Android splash screens (cada densidade/orientação tem seu próprio tamanho)
for path in glob.glob(f"{RES}/drawable*/splash.png"):
    with Image.open(path) as existing:
        w, h = existing.size
    make_splash(w, h, src).save(path)
    print(f"android splash {path}: {w}x{h} ok")

# Play Store listing icon (512x512, required exactly this size)
src.resize((512, 512), Image.LANCZOS).save("play_store_icon_512.png")
print("play store icon ok")

# --- iOS ---
IOS_APPICON = "ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png"
if os.path.exists(os.path.dirname(IOS_APPICON)):
    # App Store icon: exactly 1024x1024, sem canal alpha (Apple rejeita com transparência)
    ios_icon = src.resize((1024, 1024), Image.LANCZOS).convert("RGB")
    ios_icon.save(IOS_APPICON)
    print("ios app icon ok")

IOS_SPLASH_DIR = "ios/App/App/Assets.xcassets/Splash.imageset"
if os.path.exists(IOS_SPLASH_DIR):
    canvas_size = 2732
    logo_size = int(canvas_size * 0.32)
    logo = src.resize((logo_size, logo_size), Image.LANCZOS)
    splash = Image.new("RGB", (canvas_size, canvas_size), (109, 40, 217))  # brand purple #6d28d9
    offset = ((canvas_size - logo_size) // 2, (canvas_size - logo_size) // 2)
    splash.paste(logo, offset)
    for filename in ("splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"):
        splash.save(f"{IOS_SPLASH_DIR}/{filename}")
    print("ios splash ok")
