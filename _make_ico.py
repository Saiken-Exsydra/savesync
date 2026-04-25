"""Convert assets/savesync.svg to savesync.ico + assets/savesync.png. Called by build_exe.bat."""
import sys, os, io

svg = os.path.join("assets", "savesync.svg")
ico = "savesync.ico"
png_out = os.path.join("assets", "savesync.png")
sizes = [16, 32, 48, 64, 128, 256]

if not os.path.exists(svg):
    print(f"WARNING: {svg} not found — skipping icon conversion.")
    sys.exit(0)

def save_outputs(imgs):
    imgs[0].save(ico, format="ICO",
                 sizes=[(i.width, i.height) for i in imgs],
                 append_images=imgs[1:])
    # 256px PNG used by win11toast for notification icon at runtime
    next(i for i in imgs if i.width == 256).save(png_out, format="PNG")

# Primary: cairosvg + Pillow
try:
    import cairosvg
    from PIL import Image
    imgs = []
    for s in sizes:
        png = cairosvg.svg2png(url=svg, output_width=s, output_height=s)
        imgs.append(Image.open(io.BytesIO(png)).convert("RGBA"))
    save_outputs(imgs)
    print(f"Icon saved: {ico}, {png_out}")
    sys.exit(0)
except ImportError:
    print("NOTE: cairosvg not installed — trying Qt fallback.")
except Exception as e:
    print(f"WARNING: cairosvg conversion failed ({e}) — trying Qt fallback.")

# Fallback: PyQt6 rasterizer
try:
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from PIL import Image

    app = QApplication.instance() or QApplication(sys.argv)
    renderer = QSvgRenderer(svg)
    imgs = []
    for s in sizes:
        img = QImage(s, s, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        renderer.render(p)
        p.end()
        ba = img.bits().asarray(s * s * 4)
        pil = Image.frombuffer("RGBA", (s, s), bytes(ba), "raw", "BGRA", 0, 1)
        imgs.append(pil)
    save_outputs(imgs)
    print(f"Icon saved via Qt fallback: {ico}, {png_out}")
    sys.exit(0)
except Exception as e:
    print(f"WARNING: Icon conversion failed ({e}) — exe will use default icon.")
    sys.exit(0)
