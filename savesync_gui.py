"""
SaveSync GUI — PyQt6 frontend matching the HTML prototype.
Logic layer: savesync.py (never modified here).
pip install PyQt6 pillow requests
"""
import os, sys, json, time, hashlib, urllib.parse, datetime, threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget,
    QLineEdit, QTextEdit, QDialog, QFileDialog, QMessageBox, QSizePolicy,
    QCheckBox, QSystemTrayIcon, QMenu, QSpacerItem, QProgressBar,
    QGraphicsDropShadowEffect, QScrollBar, QToolButton, QToolTip,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QRect, QPropertyAnimation,
    QEasingCurve, pyqtProperty, QEvent, QRectF,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QPixmap, QIcon,
    QPainterPath, QLinearGradient, QRadialGradient, QCursor, QAction,
    QFontMetrics,
)
from PyQt6.QtSvg import QSvgRenderer

import savesync as ss

CFG = ss.load_config()

# ── Drive-scan diagnostic trap ────────────────────────────────────────────────
# Set DRIVE_SCAN_TRAP = True to record every QWidget.show() + subprocess launch
# during a Drive scan into %USERPROFILE%\Desktop\savesync_scan_trap.log
# Disable once the flashing window is identified.
DRIVE_SCAN_TRAP = False
_TRAP_LOG = Path.home() / "Desktop" / "savesync_scan_trap.log"
_trap_active = False  # unused now — trap runs always

def _trap_log(msg: str):
    try:
        with open(_TRAP_LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def _install_drive_scan_trap():
    import traceback
    import subprocess as _sp

    # — QWidget.show patch — logs ALL top-level window shows, always —
    _orig_show = QWidget.show
    def _patched_show(self_w):
        if self_w.isWindow():
            cls   = type(self_w).__name__
            title = getattr(self_w, 'windowTitle', lambda: '')()
            flags = int(self_w.windowFlags())
            stack = "".join(traceback.format_stack(limit=8)[:-1])
            _trap_log(
                f"\n[QWidget.show] {cls!r} title={title!r} flags=0x{flags:x}\n"
                f"  parent={type(self_w.parent()).__name__ if self_w.parent() else 'None'}\n"
                f"{stack}"
            )
        _orig_show(self_w)
    QWidget.show = _patched_show

    # — subprocess.Popen patch — logs ALL subprocess launches —
    _orig_popen = _sp.Popen.__init__
    def _patched_popen(self_p, args, **kwargs):
        stack = "".join(traceback.format_stack(limit=8)[:-1])
        _trap_log(f"\n[subprocess.Popen] args={args!r}\n{stack}")
        _orig_popen(self_p, args, **kwargs)
    _sp.Popen.__init__ = _patched_popen

_TRAP_INSTALLED = False
def _ensure_trap():
    global _TRAP_INSTALLED
    if not DRIVE_SCAN_TRAP or _TRAP_INSTALLED:
        return
    _TRAP_INSTALLED = True
    _trap_log(f"\n{'='*60}\nDrive-scan trap installed at {datetime.datetime.now()}\n{'='*60}")
    _install_drive_scan_trap()
# ─────────────────────────────────────────────────────────────────────────────

try:
    import requests as _req
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from PIL import Image as _PilImg
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ── Palette ──────────────────────────────────────────────────────────────────
C = {
    "bg":          "#07091a",
    "bg2":         "#0c1022",
    "card":        "#0f1628",
    "cardH":       "#131c35",
    "border":      "#1c2540",
    "borderH":     "#3a4d8a",
    "accent":      "#7c6fff",
    "accentD":     "#5249cc",
    "text":        "#e8eaf2",
    "textMid":     "#8b93b3",
    "textDim":     "#4a5278",
    "success":     "#3dd68c",
    "warning":     "#f0a830",
    "error":       "#f05060",
    "driveBg":     "#0d1c3e",
    "driveFg":     "#6aacf5",
    "zipBg":       "#1e1500",
    "zipFg":       "#f0c040",
    "autoBg":      "#091a10",
    "autoFg":      "#3dd68c",
}

# Assets must come from the PyInstaller extraction folder when frozen, since
# __file__ points inside the bundled .pyc archive that callers cannot read.
if getattr(sys, "frozen", False):
    ASSETS_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets"
else:
    ASSETS_DIR = Path(__file__).parent / "assets"

def svg_icon(name: str, color: str, size: int = 18) -> QPixmap:
    """Render a named SVG from assets/ with the given hex color into a QPixmap."""
    svg_path = ASSETS_DIR / f"{name}.svg"
    data = svg_path.read_bytes().replace(b'fill="#000000"', f'fill="{color}"'.encode())
    renderer = QSvgRenderer(data)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm

QSS = f"""
* {{ font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 13px; color: {C['text']}; }}
QWidget {{ border: none; }}
QMainWindow, QDialog {{ background: {C['bg']}; }}
QWidget#panel {{ background: {C['bg']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    border: none; background: {C['bg']}; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #2a3560; border-radius: 3px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QLineEdit {{
    background: {C['bg2']}; border: 1px solid {C['border']};
    border-radius: 8px; padding: 8px 12px; color: {C['text']};
    font-family: 'JetBrains Mono', 'Consolas', monospace;
}}
QLineEdit:focus {{ border-color: {C['accent']}; }}
QTextEdit {{
    background: {C['bg2']}; border: 1px solid {C['border']};
    border-radius: 8px; color: {C['text']};
}}
QCheckBox {{ spacing: 8px; color: {C['text']}; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border-radius: 3px;
    border: 1px solid {C['border']}; background: {C['bg2']};
}}
QCheckBox::indicator:checked {{
    background: {C['accent']}; border-color: {C['accent']};
}}
QMenu {{
    background: {C['card']}; border: 1px solid {C['border']};
    border-radius: 8px; padding: 4px;
}}
QMenu::item {{ padding: 8px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: rgba(124,111,255,0.15); }}
QProgressBar {{
    background: {C['border']}; border: none; border-radius: 2px; height: 4px;
}}
QProgressBar::chunk {{ background: {C['accent']}; border-radius: 2px; }}
"""

# ── Utilities ────────────────────────────────────────────────────────────────
def relative_time(iso):
    if not iso:
        return "never"
    try:
        dt = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc)
        diff = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
    except Exception:
        return "never"
    if diff < 60:    return "just now"
    if diff < 3600:  return f"{int(diff/60)}m ago"
    if diff < 86400: return f"{int(diff/3600)}h ago"
    return f"{int(diff/86400)}d ago"

def placeholder_color(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    hue = h % 360
    return QColor.fromHsv(hue, 80, 60)

def initials(name):
    parts = name.split()
    return "".join(p[0].upper() for p in parts[:2]) if parts else "?"

def str_hue(name):
    h = 0
    for c in name:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return h % 360

def card_colors(name):
    hue = str_hue(name)
    from_c = QColor.fromHsv(hue, 70, 30)
    to_c   = QColor.fromHsv(hue, 50, 20)
    text_c = QColor.fromHsv(hue, 60, 190)
    return from_c, to_c, text_c


def install_enter_to_advance(dialog, advance_callable):
    """Wire Enter / Return on `dialog` to invoke `advance_callable`.

    Skips when focus is in a multi-line text edit (where Enter inserts a
    newline) or when a button currently has focus (let the user activate
    the focused control instead). Esc still maps to reject() via Qt default.
    """
    _orig = dialog.keyPressEvent

    def _kp(ev):
        key = ev.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            mods = ev.modifiers()
            # Ignore if a modifier (Shift/Ctrl/Alt) is held — preserve newline-in-textedit etc.
            if mods & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier
                       | Qt.KeyboardModifier.AltModifier):
                return _orig(ev)
            fw = dialog.focusWidget()
            # Multi-line edits: let Enter insert a newline.
            if isinstance(fw, QTextEdit):
                return _orig(ev)
            # If a button has focus, let it click itself.
            if isinstance(fw, (QPushButton, QToolButton)):
                fw.click()
                ev.accept()
                return
            try:
                advance_callable()
            except Exception:
                pass
            ev.accept()
            return
        return _orig(ev)

    dialog.keyPressEvent = _kp

# ── Thumbnail ────────────────────────────────────────────────────────────────
SGDB_KEY   = "eef436c06c902672e16d69ba375c0cb7"
THUMB_DIR  = ss.BASE_DIR / "thumbnail_cache"
THUMB_DIR.mkdir(exist_ok=True)

def _thumb_path(name):
    safe = "".join(c if c.isalnum() else "_" for c in name)
    return THUMB_DIR / f"{safe}.png"

def get_thumb_pixmap(name):
    p = _thumb_path(name)
    if p.exists():
        return QPixmap(str(p))
    return None

class ThumbWorker(QThread):
    done = pyqtSignal(str, str)   # name, path

    def __init__(self, name):
        super().__init__()
        self.name = name

    def run(self):
        if not REQUESTS_OK:
            return
        p = _thumb_path(self.name)
        if p.exists():
            self.done.emit(self.name, str(p))
            return
        try:
            hdrs = {"Authorization": f"Bearer {SGDB_KEY}"}
            url  = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{urllib.parse.quote(self.name)}"
            r    = _req.get(url, headers=hdrs, timeout=6)
            data = r.json().get("data", [])
            if not data: return
            gid  = data[0]["id"]
            r2   = _req.get(f"https://www.steamgriddb.com/api/v2/grids/game/{gid}?dimensions=600x900&limit=1&nsfw=false",
                            headers=hdrs, timeout=6)
            grids = r2.json().get("data", [])
            if not grids:
                r2 = _req.get(f"https://www.steamgriddb.com/api/v2/grids/game/{gid}?limit=1&nsfw=false",
                              headers=hdrs, timeout=6)
                grids = r2.json().get("data", [])
            if not grids: return
            img_bytes = _req.get(grids[0]["url"], timeout=10).content
            if PIL_OK:
                import io
                img = _PilImg.open(io.BytesIO(img_bytes)).convert("RGBA")
                img.save(str(p), "PNG")
            else:
                p.write_bytes(img_bytes)
            self.done.emit(self.name, str(p))
        except Exception as e:
            pass

# ── Animated Widgets ─────────────────────────────────────────────────────────
class PulseDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self._phase = 0.0
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(50)

    def _tick(self):
        self._phase = (self._phase + 0.08) % 1.0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = 7, 7
        # Pulsing ring
        r = 4 + self._phase * 5
        alpha = int(200 * (1 - self._phase))
        p.setPen(QPen(QColor(61, 214, 140, alpha), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - r, cy - r, r*2, r*2))
        # Core dot
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#3dd68c"))
        p.drawEllipse(QRectF(cx - 4, cy - 4, 8, 8))


class RadarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(72, 72)
        self._running = False
        self._phases  = [0.0, 0.33, 0.66]
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(40)

    def set_running(self, v):
        self._running = v
        self.update()

    def _tick(self):
        if self._running:
            self._phases = [(ph + 0.012) % 1.0 for ph in self._phases]
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, r0 = 36, 36, 22
        if self._running:
            for ph in self._phases:
                rr = r0 + ph * 28
                alpha = int(180 * (1 - ph))
                p.setPen(QPen(QColor(61, 214, 140, alpha), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx-rr, cy-rr, rr*2, rr*2))
            # Green circle bg
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(61, 214, 140, 30))
            p.drawEllipse(QRectF(cx-r0, cy-r0, r0*2, r0*2))
            p.setPen(QPen(QColor("#3dd68c"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-r0, cy-r0, r0*2, r0*2))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#3dd68c"))
            p.drawEllipse(QRectF(cx-6, cy-6, 12, 12))
        else:
            p.setPen(QPen(QColor("#4a5278"), 2))
            p.setBrush(QColor(74, 82, 120, 50))
            p.drawEllipse(QRectF(cx-r0, cy-r0, r0*2, r0*2))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#4a5278"))
            p.drawEllipse(QRectF(cx-6, cy-6, 12, 12))


# ── Toast ─────────────────────────────────────────────────────────────────────
class Toast(QWidget):
    _COLORS = {
        "success": ("#3dd68c", "rgba(61,214,140,0.12)",  "rgba(61,214,140,0.3)"),
        "error":   ("#f05060", "rgba(240,80,96,0.12)",   "rgba(240,80,96,0.3)"),
        "warning": ("#f0a830", "rgba(240,168,48,0.12)",  "rgba(240,168,48,0.3)"),
        "info":    ("#6aacf5", "rgba(106,172,245,0.12)", "rgba(106,172,245,0.3)"),
    }

    def __init__(self, message, kind="info", parent=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                              | Qt.WindowType.Tool
                              | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        fg, bg, bdr = self._COLORS.get(kind, self._COLORS["info"])
        self.setStyleSheet(f"""
            QWidget#toast {{
                background: {C['card']}; border: 1px solid {bdr};
                border-left: 3px solid {fg}; border-radius: 10px;
            }}
            QLabel {{ background: transparent; border: none; color: {C['text']}; font-size: 12px; }}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QWidget()
        box.setObjectName("toast")
        outer.addWidget(box)
        row = QHBoxLayout(box)
        row.setContentsMargins(14, 11, 14, 11)
        row.setSpacing(10)
        icon_map = {"success":"✓","error":"✗","warning":"⚠","info":"ℹ"}
        icon = QLabel(icon_map.get(kind,"ℹ"))
        icon.setStyleSheet(f"color:{fg}; font-weight:700; font-size:13px;")
        row.addWidget(icon)
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        row.addWidget(lbl, 1)
        self.setFixedWidth(320)
        self.adjustSize()
        QTimer.singleShot(4000, self.close)


_active_toasts = []

_TOAST_H = 48  # approximate fixed row height for stacking

def show_toast(message, kind="info", parent=None):
    t = Toast(message, kind, parent)
    _active_toasts.append(t)
    idx = len(_active_toasts) - 1
    def _cleanup():
        if t in _active_toasts:
            _active_toasts.remove(t)
    t.destroyed.connect(_cleanup)
    t.show()
    t.adjustSize()
    if parent:
        win = parent.window()
        rect = win.rect()
        bottom_right = win.mapToGlobal(rect.bottomRight())
        th = t.height()
        x = bottom_right.x() - 340
        y = bottom_right.y() - th - 16 - idx * (th + 8)
        t.move(x, y)


# ── TitleBar ──────────────────────────────────────────────────────────────────
class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(f"background:{C['bg2']}; border-bottom:1px solid rgba(255,255,255,0.06);")
        self._drag_pos = None

        l = QHBoxLayout(self)
        l.setContentsMargins(16, 0, 8, 0)
        l.setSpacing(0)

        l.addStretch()

        for sym, slot, hover_col in [
            ("—", self._minimize, C['textDim']),
            ("✕", self._close,   C['error']),
        ]:
            btn = QPushButton(sym)
            btn.setFixedSize(32, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; font-size:13px; }}"
                f"QPushButton:hover {{ background:rgba(255,255,255,0.07); color:{hover_col}; }}"
            )
            btn.clicked.connect(slot)
            l.addWidget(btn)

    def _minimize(self):
        self.window().showMinimized()

    def _close(self):
        self.window().close()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None


# ── Sidebar ───────────────────────────────────────────────────────────────────
class Sidebar(QWidget):
    nav_clicked = pyqtSignal(str)

    _ITEMS = [
        ("games",    "games",    "Games"),
        ("watcher",  "watcher",  "Watcher"),
        ("restore",  "drive",    "Drive"),
        ("settings", "settings", "Settings"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(210)
        self.setObjectName("sidebar")
        self.setStyleSheet(f"QWidget#sidebar {{ background:{C['bg2']}; border-right:1px solid rgba(255,255,255,0.06); }}")
        self._active = "games"
        self._btns   = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Logo
        logo_w = QWidget()
        logo_l = QHBoxLayout(logo_w)
        logo_l.setContentsMargins(18, 22, 18, 18)
        logo_l.setSpacing(10)
        logo_icon = QLabel()
        logo_icon.setFixedSize(28, 28)
        logo_icon.setStyleSheet(f"""
            background: rgba(124,111,255,0.15); border-radius: 14px;
            border: 1.5px solid {C['accent']};
        """)
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_icon.setText("S")
        logo_icon.setStyleSheet(f"background:rgba(124,111,255,0.15); border-radius:14px; border:1.5px solid {C['accent']}; color:{C['accent']}; font-weight:800; font-size:13px;")
        logo_l.addWidget(logo_icon)
        txt_col = QVBoxLayout()
        txt_col.setSpacing(1)
        name_lbl = QLabel("SaveSync")
        name_lbl.setStyleSheet(f"color:{C['text']}; font-size:15px; font-weight:700; letter-spacing:-0.3px;")
        sub_lbl  = QLabel("SAVE MANAGER")
        sub_lbl.setStyleSheet(f"color:{C['textDim']}; font-size:10px; letter-spacing:0.3px;")
        txt_col.addWidget(name_lbl)
        txt_col.addWidget(sub_lbl)
        logo_l.addLayout(txt_col)
        root.addWidget(logo_w)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:rgba(255,255,255,0.06); margin: 0 18px;")
        root.addWidget(div)
        root.addSpacing(8)

        # Nav buttons
        for key, icon, label in self._ITEMS:
            btn = self._make_btn(key, icon, label)
            self._btns[key] = btn
            root.addWidget(btn)

        root.addStretch(1)

        # Watcher chip
        chip_sep = QFrame()
        chip_sep.setFixedHeight(1)
        chip_sep.setStyleSheet(f"background:rgba(255,255,255,0.06);")
        root.addWidget(chip_sep)
        self._chip = QWidget()
        chip_l = QHBoxLayout(self._chip)
        chip_l.setContentsMargins(18, 14, 18, 14)
        chip_l.setSpacing(8)
        self._pulse = PulseDot()
        self._pulse.hide()
        chip_l.addWidget(self._pulse)
        self._dot_off = QWidget()
        self._dot_off.setFixedSize(8, 8)
        self._dot_off.setStyleSheet(f"background:{C['textDim']}; border-radius:4px; border:none;")
        chip_l.addWidget(self._dot_off)
        self._chip_lbl = QLabel("Watcher stopped")
        self._chip_lbl.setStyleSheet(f"color:{C['textDim']}; font-size:11px; font-weight:500;")
        chip_l.addWidget(self._chip_lbl)
        root.addWidget(self._chip)

        self._set_active("games")

    def _make_btn(self, key, icon_name, label):
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(44)
        btn.setStyleSheet(self._btn_style(False))
        layout = QHBoxLayout(btn)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(18, 18)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setPixmap(svg_icon(icon_name, C['textDim'], 18))
        layout.addWidget(icon_lbl)
        text_lbl = QLabel(label)
        text_lbl.setStyleSheet(f"color:{C['textMid']}; font-size:13px;")
        layout.addWidget(text_lbl, 1)
        btn._icon_lbl  = icon_lbl
        btn._icon_name = icon_name
        btn._text_lbl  = text_lbl
        btn._key       = key
        btn.clicked.connect(lambda checked, k=key: self._on_click(k))
        return btn

    def _btn_style(self, active):
        if active:
            return f"""
                QPushButton {{ background: rgba(124,111,255,0.10); border: none;
                    border-left: 3px solid {C['accent']}; border-radius: 0; text-align:left; }}
            """
        return f"""
            QPushButton {{ background: transparent; border: none; border-radius: 0; text-align:left; }}
            QPushButton:hover {{ background: rgba(124,111,255,0.08); }}
        """

    def _on_click(self, key):
        self._set_active(key)
        self.nav_clicked.emit(key)

    def _set_active(self, key):
        self._active = key
        for k, btn in self._btns.items():
            active = k == key
            btn.setChecked(active)
            btn.setStyleSheet(self._btn_style(active))
            icon_color = C['accent'] if active else C['textDim']
            btn._icon_lbl.setPixmap(svg_icon(btn._icon_name, icon_color, 18))
            btn._text_lbl.setStyleSheet(f"color:{C['text'] if active else C['textMid']}; font-size:13px; font-weight:{'600' if active else '400'};")

    def set_watcher(self, running):
        self._pulse.setVisible(running)
        self._dot_off.setVisible(not running)
        col = C['success'] if running else C['textDim']
        self._chip_lbl.setText("Watcher running" if running else "Watcher stopped")
        self._chip_lbl.setStyleSheet(f"color:{col}; font-size:11px; font-weight:500;")

    def set_active(self, key):
        self._set_active(key)


# ── RoundedThumb ─────────────────────────────────────────────────────────────
class _RoundedThumb(QWidget):
    """Thumbnail widget that clips its pixmap to the card's top rounded corners."""
    RADIUS = 14

    def __init__(self, w, h, parent=None):
        super().__init__(parent)
        self.setFixedSize(w, h)
        self._pixmap = None

    def setPixmap(self, px):
        self._pixmap = px
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.RADIUS
        path = QPainterPath()
        path.moveTo(r, 0)
        path.lineTo(self.width() - r, 0)
        path.arcTo(self.width() - 2*r, 0, 2*r, 2*r, 90, -90)
        path.lineTo(self.width(), self.height())
        path.lineTo(0, self.height())
        path.arcTo(0, 0, 2*r, 2*r, 180, -90)
        path.closeSubpath()
        p.setClipPath(path)
        if self._pixmap:
            scaled = self._pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            p.fillRect(self.rect(), QColor(C['card']))


# ── GameCard ──────────────────────────────────────────────────────────────────
class GameCard(QFrame):
    sig_sync        = pyqtSignal(dict)
    sig_backup      = pyqtSignal(dict)
    sig_edit        = pyqtSignal(dict)
    sig_remove      = pyqtSignal(dict)
    sig_open_folder = pyqtSignal(dict)

    CARD_W = 220

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.setFixedWidth(self.CARD_W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False
        self._pixmap  = None
        self._update_style(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Thumbnail area
        self._thumb_lbl = _RoundedThumb(self.CARD_W, int(self.CARD_W * 1.4))
        self._draw_placeholder()
        root.addWidget(self._thumb_lbl)

        # Info area
        info = QWidget()
        info.setStyleSheet("background: transparent;")
        info_l = QVBoxLayout(info)
        info_l.setContentsMargins(14, 12, 14, 14)
        info_l.setSpacing(0)

        # Name
        name_lbl = QLabel(game.get("name","?"))
        name_lbl.setStyleSheet(f"font-size:14px; font-weight:600; color:{C['text']}; letter-spacing:-0.2px;")
        name_lbl.setWordWrap(False)
        fm = QFontMetrics(name_lbl.font())
        name_lbl.setFixedWidth(self.CARD_W - 28)
        info_l.addWidget(name_lbl)

        # Last sync row
        sync_row = QHBoxLayout()
        sync_row.setSpacing(4)
        sync_lbl = QLabel("Last sync")
        sync_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        sync_row.addWidget(sync_lbl)
        ts = game.get("backup_timestamp") or game.get("last_sync")
        rel = relative_time(ts)
        is_recent = False
        if ts:
            try:
                dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                is_recent = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() < 3600
            except Exception:
                pass
        self._time_lbl = QLabel(rel)
        self._time_lbl.setStyleSheet(f"font-size:11px; font-weight:500; color:{C['success'] if is_recent else C['textMid']};")
        sync_row.addWidget(self._time_lbl)
        sync_row.addStretch()
        info_l.addSpacing(4)
        info_l.addLayout(sync_row)

        # Badges
        badge_row = QHBoxLayout()
        badge_row.setSpacing(5)
        badge_row.setContentsMargins(0, 9, 0, 0)
        if game.get("drive_folder"):
            badge_row.addWidget(self._badge("Drive", C["driveBg"], C["driveFg"]))
        if game.get("archive_path"):
            badge_row.addWidget(self._badge(".7z", C["zipBg"], C["zipFg"]))
        interval = game.get("interval_min", 0)
        trigger  = "close" if game.get("trigger_close") else ("launch" if game.get("trigger_launch") else "")
        if interval:
            badge_row.addWidget(self._badge(f"{interval} min", C["autoBg"], C["autoFg"]))
        elif trigger:
            badge_row.addWidget(self._badge(f"on {trigger}", C["autoBg"], C["autoFg"]))
        badge_row.addStretch()
        info_l.addLayout(badge_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.setContentsMargins(0, 12, 0, 0)
        if game.get("drive_folder"):
            self._btn_main = self._mk_btn("Sync", primary=True)
            self._btn_main.clicked.connect(lambda: self.sig_sync.emit(self.game))
        else:
            self._btn_main = self._mk_btn("Backup", primary=False)
            self._btn_main.clicked.connect(lambda: self.sig_backup.emit(self.game))
        btn_row.addWidget(self._btn_main, 1)

        more_btn = self._mk_btn("···", primary=False)
        more_btn.setFixedWidth(34)
        more_btn.clicked.connect(lambda: self._show_menu(more_btn))
        btn_row.addWidget(more_btn)
        info_l.addLayout(btn_row)

        root.addWidget(info)
        self.adjustSize()

    def _badge(self, text, bg, fg):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            background:{bg}; color:{fg}; font-size:10px; font-weight:600;
            border-radius:99px; padding: 3px 7px;
        """)
        return lbl

    def _mk_btn(self, text, primary):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{ background:{C['accent']}; color:#fff; border:none; border-radius:8px;
                    padding:7px 14px; font-size:12px; font-weight:600; }}
                QPushButton:hover {{ background:{C['accentD']}; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{ background:{C['cardH']}; color:{C['textMid']}; border:1px solid {C['border']};
                    border-radius:8px; padding:7px 10px; font-size:12px; }}
                QPushButton:hover {{ background:{C['border']}; }}
            """)
        return btn

    def _show_menu(self, anchor):
        menu = QMenu(self)
        menu.addAction("Backup now",          lambda: self.sig_backup.emit(self.game))
        menu.addAction("Edit",                lambda: self.sig_edit.emit(self.game))
        menu.addAction("Open local save folder", lambda: self.sig_open_folder.emit(self.game))
        menu.addSeparator()
        a = menu.addAction("Remove")
        a.triggered.connect(lambda: self.sig_remove.emit(self.game))
        menu.exec(anchor.mapToGlobal(QPoint(0, -menu.sizeHint().height() - 4)))

    def _draw_placeholder(self):
        w, h = self.CARD_W, int(self.CARD_W * 1.4)
        px = QPixmap(w, h)
        name = self.game.get("name","?")
        fc, tc, txtc = card_colors(name)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, fc)
        grad.setColorAt(1, tc)
        p.fillRect(0, 0, w, h, grad)
        # Grid overlay
        p.setPen(QPen(QColor(255,255,255,15), 0.5))
        for x in range(0, w, 24):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 24):
            p.drawLine(0, y, w, y)
        # Initials
        font = QFont("Inter", 36, QFont.Weight.ExtraBold)
        p.setFont(font)
        p.setPen(QColor(txtc.red(), txtc.green(), txtc.blue(), 180))
        p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, initials(name))
        p.end()
        self._thumb_lbl.setPixmap(px)

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        self._thumb_lbl.setPixmap(pixmap)

    def _update_style(self, hovered):
        border = C['borderH'] if hovered else C['border']
        shadow = "0 0 0 1px rgba(124,111,255,0.3), 0 8px 32px rgba(7,9,26,0.6)" if hovered else ""
        self.setStyleSheet(f"""
            GameCard {{
                border: 1px solid {border};
                border-radius: 14px;
                background: {C['card']};
            }}
        """)

    def enterEvent(self, e):
        self._hovered = True
        self._update_style(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self._update_style(False)
        super().leaveEvent(e)

    def refresh(self, game):
        self.game = game
        ts = game.get("backup_timestamp") or game.get("last_sync")
        rel = relative_time(ts)
        is_recent = False
        if ts:
            try:
                dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                is_recent = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() < 3600
            except Exception:
                pass
        self._time_lbl.setText(rel)
        self._time_lbl.setStyleSheet(
            f"font-size:11px; font-weight:500; color:{C['success'] if is_recent else C['textMid']};"
        )

# ── Worker Thread ─────────────────────────────────────────────────────────────
class Worker(QThread):
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn   = fn
        self._args = args
        self._kw   = kwargs

    def run(self):
        try:
            self.finished.emit(self._fn(*self._args, **self._kw))
        except Exception as e:
            self.error.emit(str(e))


# ── Log box ───────────────────────────────────────────────────────────────────
class LogBox(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(
            f"QTextEdit {{ background:{C['bg2']}; border:1px solid {C['border']};"
            f" border-radius:8px; color:{C['textMid']}; font-size:11px;"
            f" font-family:'JetBrains Mono','Consolas',monospace; padding:8px; }}"
        )

    def append_line(self, text, ok=None):
        if ok is True:
            color = C['success']
        elif ok is False:
            color = C['error']
        else:
            color = C['textMid']
        self.append(f"<span style='color:{color};'>{text}</span>")
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


# ── Button helpers ────────────────────────────────────────────────────────────
def _icon_btn_primary(text: str, svg_name: str, small=False):
    pad = "7px 14px" if small else "8px 18px"
    b = QPushButton()
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ background:{C['accent']}; border:none; border-radius:8px; padding:{pad}; }}"
        f"QPushButton:hover {{ background:{C['accentD']}; }}"
        f"QPushButton:disabled {{ background:{C['textDim']}; }}"
    )
    b.setIcon(QIcon(svg_icon(svg_name, "#ffffff", 16)))
    b.setIconSize(QSize(16, 16))
    b.setText(text)
    b.setStyleSheet(
        f"QPushButton {{ background:{C['accent']}; color:#fff; border:none; border-radius:8px;"
        f" padding:{pad}; font-size:12px; font-weight:600; }}"
        f"QPushButton:hover {{ background:{C['accentD']}; }}"
        f"QPushButton:disabled {{ background:{C['textDim']}; color:{C['bg']}; }}"
    )
    return b

def _icon_btn_ghost(text: str, svg_name: str, small=False):
    return btn_ghost(text, small)

def btn_primary(text, small=False):
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    pad = "7px 14px" if small else "8px 18px"
    b.setStyleSheet(
        f"QPushButton {{ background:{C['accent']}; color:#fff; border:none; border-radius:8px;"
        f" padding:{pad}; font-size:12px; font-weight:600; }}"
        f"QPushButton:hover {{ background:{C['accentD']}; }}"
        f"QPushButton:disabled {{ background:{C['textDim']}; color:{C['bg']}; }}"
    )
    return b

def btn_ghost(text, small=False):
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    pad = "6px 10px" if small else "8px 14px"
    b.setStyleSheet(
        f"QPushButton {{ background:{C['cardH']}; color:{C['textMid']}; border:1px solid {C['border']};"
        f" border-radius:8px; padding:{pad}; font-size:12px; }}"
        f"QPushButton:hover {{ background:{C['border']}; }}"
    )
    return b

def btn_danger(text, small=False):
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    pad = "6px 10px" if small else "8px 14px"
    b.setStyleSheet(
        f"QPushButton {{ background:rgba(240,80,96,0.06); color:{C['error']};"
        f" border:1px solid rgba(240,80,96,0.3); border-radius:8px; padding:{pad}; font-size:12px; }}"
        f"QPushButton:hover {{ background:rgba(240,80,96,0.15); }}"
    )
    return b

def section_title(text):
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    l = QVBoxLayout(w)
    l.setContentsMargins(0, 8, 0, 6)
    l.setSpacing(0)
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{C['textDim']}; font-size:10px; font-weight:700; letter-spacing:1.2px;"
    )
    l.addWidget(lbl)
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:rgba(255,255,255,0.06); margin-top:6px;")
    l.addWidget(sep)
    return w


def section_title_with_info(text, tooltip):
    """Like section_title() but adds a small (i) info badge that shows
    `tooltip` on hover."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    l = QVBoxLayout(w)
    l.setContentsMargins(0, 8, 0, 6)
    l.setSpacing(0)

    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(8)

    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{C['textDim']}; font-size:10px; font-weight:700; letter-spacing:1.2px;"
    )
    title_row.addWidget(lbl)

    info = QToolButton()
    info.setText("i")
    info.setFixedSize(16, 16)
    info.setCursor(Qt.CursorShape.PointingHandCursor)
    info.setToolTip(tooltip)
    info.setStyleSheet(
        f"QToolButton {{ color:{C['textDim']};"
        f" background:rgba(255,255,255,0.08);"
        f" border:1px solid rgba(255,255,255,0.15);"
        f" border-radius:8px;"
        f" font-size:10px; font-weight:700; font-family:'Segoe UI'; }}"
        f"QToolButton:hover {{ color:{C['accent']};"
        f" border-color:{C['accent']}; }}"
    )
    info.clicked.connect(lambda: QToolTip.showText(
        info.mapToGlobal(info.rect().bottomLeft()), tooltip, info
    ))
    title_row.addWidget(info)
    title_row.addStretch()
    l.addLayout(title_row)

    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:rgba(255,255,255,0.06); margin-top:6px;")
    l.addWidget(sep)
    return w


# ── DbSearchResultsDialog ─────────────────────────────────────────────────────
class DbSearchResultsDialog(QDialog):
    """Shows Ludusavi database search results in a dedicated window."""

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self._query  = query
        self._worker = None
        self.setWindowTitle("Database Search")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(520)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
            f" QLabel {{ color:{C['text']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Database Search")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(4)

        # Query subtitle
        sub = QLabel(f"Results for: {query}")
        sub.setStyleSheet(f"font-size:12px; color:{C['textDim']};")
        root.addWidget(sub)
        root.addSpacing(16)

        # Spinner / status
        self._status = QLabel("Searching…")
        self._status.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        root.addWidget(self._status)
        root.addSpacing(8)

        # Scrollable results area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(340)
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(inner)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(6)
        self._results_layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)
        root.addSpacing(16)

        # Footer
        foot = QHBoxLayout()
        close_btn = btn_ghost("Close")
        close_btn.clicked.connect(self.reject)
        foot.addStretch()
        foot.addWidget(close_btn)
        root.addLayout(foot)

        self._sig = pyqtSignal_standalone = None  # use QTimer trick via Worker
        self._run_search()

        install_enter_to_advance(self, self.reject)

    def _run_search(self):
        q = self._query

        def _do():
            return ss.search_manifest_split(q)

        self._worker = Worker(_do)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, result):
        self._status.hide()
        exact, candidates = result if isinstance(result, tuple) else (None, [])

        # Remove stretch placeholder
        item = self._results_layout.itemAt(self._results_layout.count() - 1)
        if item and item.spacerItem():
            self._results_layout.removeItem(item)

        items = []
        if exact:
            name, paths = exact
            for path in paths:
                items.append((name, path, True))
        for entry in (candidates or []):
            name, paths = entry
            for path in paths:
                items.append((name, path, False))

        if not items:
            lbl = QLabel("No results found in the database.")
            lbl.setStyleSheet(f"color:{C['textDim']}; font-size:12px;")
            self._results_layout.addWidget(lbl)
            self._results_layout.addStretch()
            return

        # Section: exact match
        if exact:
            sec = QLabel("EXACT MATCH")
            sec.setStyleSheet(
                f"font-size:10px; font-weight:700; color:{C['success']}; letter-spacing:1px;"
            )
            self._results_layout.addWidget(sec)
            name, paths = exact
            for path in paths:
                self._results_layout.addWidget(self._make_card(name, path, exact=True))

        # Section: similar
        if candidates:
            sec2 = QLabel("SIMILAR GAMES")
            sec2.setStyleSheet(
                f"font-size:10px; font-weight:700; color:{C['textDim']}; letter-spacing:1px; margin-top:6px;"
            )
            self._results_layout.addWidget(sec2)
            for name, paths in candidates:
                self._results_layout.addWidget(self._make_card(name, paths[0] if paths else "—", exact=False))

        self._results_layout.addStretch()

    def _on_error(self, msg):
        self._status.setText(f"Error: {msg}")
        self._status.setStyleSheet(f"font-size:12px; color:{C['error']};")

    def _make_card(self, name, path, exact=False):
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:{C['card']}; border:1px solid "
            f"{'rgba(61,214,140,0.35)' if exact else C['border']}; border-radius:8px; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(4)
        nl = QLabel(name)
        nl.setStyleSheet(f"font-size:12px; font-weight:600; color:{C['text']};")
        pl = QLabel(path)
        pl.setWordWrap(True)
        pl.setStyleSheet(
            f"font-size:10px; color:{C['driveFg']};"
            f" font-family:'JetBrains Mono','Consolas',monospace;"
        )
        cl.addWidget(nl)
        cl.addWidget(pl)
        return card


# ── LudusaviDbDialog ──────────────────────────────────────────────────────────
class LudusaviDbDialog(QDialog):
    """Download/update the Ludusavi manifest and rebuild the search index,
    with real-time progress bars for each phase."""

    _sig_dl_prog  = pyqtSignal(int, str)
    _sig_idx_prog = pyqtSignal(int, str)
    _sig_done     = pyqtSignal(bool, str)   # success, message

    def __init__(self, mode="update", parent=None):
        """mode: 'update' = download+index, 'rebuild' = index only."""
        super().__init__(parent)
        self._mode   = mode
        self._worker = None
        self.setWindowTitle("Ludusavi Database")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(460)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
            f" QLabel {{ color:{C['text']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        title_txt = "Download / Update Database" if mode == "update" else "Rebuild Search Index"
        title = QLabel(title_txt)
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._x_btn = QPushButton("✕")
        self._x_btn.setFixedSize(28, 28)
        self._x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._x_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        self._x_btn.clicked.connect(self.reject)
        hdr.addWidget(self._x_btn)
        root.addLayout(hdr)
        root.addSpacing(20)

        # Warning
        warn_row = QHBoxLayout()
        warn_row.setSpacing(6)
        warn_icon = QLabel("⚠")
        warn_icon.setStyleSheet(f"color:{C['warning']}; font-size:13px;")
        warn_icon.setFixedWidth(16)
        warn_txt = QLabel(
            "Indexing parses the full manifest and may appear frozen for "
            "several seconds before progress updates begin — please wait."
        )
        warn_txt.setWordWrap(True)
        warn_txt.setStyleSheet(
            f"color:{C['warning']}; font-size:11px; font-style:italic;"
        )
        warn_row.addWidget(warn_icon)
        warn_row.addWidget(warn_txt)
        warn_row.addStretch()
        root.addLayout(warn_row)
        root.addSpacing(14)

        # Status label
        self._status = QLabel("Starting…")
        self._status.setStyleSheet(f"color:{C['textMid']}; font-size:12px;")
        root.addWidget(self._status)
        root.addSpacing(14)

        # Phase 1 — Download (hidden in rebuild-only mode)
        if mode == "update":
            dl_lbl = QLabel("Download")
            dl_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']}; font-weight:600; letter-spacing:0.5px;")
            root.addWidget(dl_lbl)
            root.addSpacing(4)
            self._dl_bar = QProgressBar()
            self._dl_bar.setRange(0, 100)
            self._dl_bar.setValue(0)
            self._dl_bar.setFixedHeight(6)
            self._dl_bar.setTextVisible(False)
            self._dl_bar.setStyleSheet(
                f"QProgressBar {{ background:{C['border']}; border:none; border-radius:3px; }}"
                f"QProgressBar::chunk {{ background:{C['accent']}; border-radius:3px; }}"
            )
            root.addWidget(self._dl_bar)
            root.addSpacing(16)
        else:
            self._dl_bar = None

        # Phase 2 — Index
        idx_lbl = QLabel("Build Index")
        idx_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']}; font-weight:600; letter-spacing:0.5px;")
        root.addWidget(idx_lbl)
        root.addSpacing(4)
        self._idx_bar = QProgressBar()
        # Start in indeterminate (busy) mode so the user sees motion during
        # the YAML parse, which can take several seconds with no progress reports.
        self._idx_bar.setRange(0, 0)
        self._idx_bar.setFixedHeight(6)
        self._idx_bar.setTextVisible(False)
        self._idx_bar.setStyleSheet(
            f"QProgressBar {{ background:{C['border']}; border:none; border-radius:3px; }}"
            f"QProgressBar::chunk {{ background:{C['success']}; border-radius:3px; }}"
        )
        root.addWidget(self._idx_bar)
        root.addSpacing(24)

        # Footer
        foot = QHBoxLayout()
        foot.setSpacing(8)
        self._close_btn = btn_ghost("Close")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)
        foot.addStretch()
        foot.addWidget(self._close_btn)
        root.addLayout(foot)

        # Wire signals
        self._sig_dl_prog.connect(self._on_dl_prog)
        self._sig_idx_prog.connect(self._on_idx_prog)
        self._sig_done.connect(self._on_done)

        # Enter closes the dialog once the Close button is enabled.
        install_enter_to_advance(
            self,
            lambda: self.accept() if self._close_btn.isEnabled() else None,
        )

    def showEvent(self, e):
        super().showEvent(e)
        self._start()

    def _start(self):
        mode = self._mode

        def _run():
            try:
                if mode == "update":
                    ok = ss.download_manifest(
                        silent=True,
                        progress_cb=lambda p, m: self._sig_dl_prog.emit(p, m),
                    )
                    if not ok:
                        self._sig_done.emit(False, "Download failed.")
                        return
                ok2 = ss.build_manifest_index(
                    silent=True,
                    progress_cb=lambda p, m: self._sig_idx_prog.emit(p, m),
                )
                if ok2:
                    self._sig_done.emit(True, "Done.")
                else:
                    self._sig_done.emit(False, "Index build failed (is PyYAML installed?).")
            except Exception as exc:
                self._sig_done.emit(False, str(exc))

        self._worker = threading.Thread(target=_run, daemon=True)
        self._worker.start()

    def _on_dl_prog(self, pct, msg):
        if self._dl_bar:
            self._dl_bar.setValue(pct)
        self._status.setText(msg)

    def _on_idx_prog(self, pct, msg):
        # Switch from indeterminate (busy) animation to determinate progress
        # the first time real per-iteration progress arrives.
        if pct > 0 and self._idx_bar.maximum() == 0:
            self._idx_bar.setRange(0, 100)
        if self._idx_bar.maximum() != 0:
            self._idx_bar.setValue(pct)
        self._status.setText(msg)

    def _on_done(self, ok, msg):
        self._status.setText(msg)
        self._status.setStyleSheet(
            f"color:{C['success'] if ok else C['error']}; font-size:12px;"
        )
        if self._dl_bar:
            self._dl_bar.setValue(100)
        # Restore determinate mode so the bar stops animating on completion.
        if self._idx_bar.maximum() == 0:
            self._idx_bar.setRange(0, 100)
        self._idx_bar.setValue(100)
        self._close_btn.setEnabled(True)
        self._x_btn.setEnabled(True)


# ── BackupDialog ──────────────────────────────────────────────────────────────
class BackupDialog(QDialog):
    sig_synced = pyqtSignal(dict)

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self._worker = None
        self._fake_timer = None
        self._step = 0
        self._steps = []
        self.setWindowTitle(f"Backup — {game['name']}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(480)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
            f" QLabel {{ color:{C['text']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        title = QLabel(f"Backup — {game['name']}")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(18)

        stats = QGridLayout()
        stats.setSpacing(0)
        ts = game.get("backup_timestamp") or game.get("last_sync")
        items = [
            ("Save files", str(game.get("save_count", "—"))),
            ("Last backup", relative_time(ts)),
            ("Drive folder", game.get("drive_folder") or "—"),
            ("Archive path", game.get("archive_path") or "—"),
        ]
        for i, (k, v) in enumerate(items):
            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 10, 16, 10)
            kl = QLabel(k.upper())
            kl.setStyleSheet(f"font-size:10px; color:{C['textDim']}; letter-spacing:0.5px;")
            vl = QLabel(v)
            vl.setStyleSheet(f"font-size:14px; font-weight:600; color:{C['text']};")
            vl.setWordWrap(True)
            cl.addWidget(kl)
            cl.addWidget(vl)
            stats.addWidget(cell, i // 2, i % 2)
            # horizontal divider between rows
            if i == 1:
                div = QFrame()
                div.setFixedHeight(1)
                div.setStyleSheet(f"background:rgba(255,255,255,0.05);")
                stats.addWidget(div, 2, 0, 1, 2)
        root.addLayout(stats)
        root.addSpacing(16)

        self._log = LogBox()
        self._log.setFixedHeight(130)
        self._log.hide()
        root.addWidget(self._log)

        self._prog = QProgressBar()
        self._prog.setRange(0, 100)
        self._prog.setValue(0)
        self._prog.hide()
        root.addWidget(self._prog)
        root.addSpacing(16)

        self._action_row = QWidget()
        ar = QHBoxLayout(self._action_row)
        ar.setContentsMargins(0, 0, 0, 0)
        ar.setSpacing(8)
        if game.get("drive_folder"):
            b = _icon_btn_primary("Backup to Drive", "drive")
            b.clicked.connect(lambda: self._run("drive"))
            ar.addWidget(b, 1)
        if game.get("archive_path"):
            b2 = btn_ghost("Create .7z")
            b2.clicked.connect(lambda: self._run("archive"))
            ar.addWidget(b2, 1)
        if game.get("drive_folder") and game.get("archive_path"):
            b3 = btn_ghost("Both")
            b3.clicked.connect(lambda: self._run("both"))
            ar.addWidget(b3, 1)
        if not game.get("drive_folder") and not game.get("archive_path"):
            note = QLabel("No backup destinations configured. Edit the game to add Drive or archive path.")
            note.setStyleSheet(f"color:{C['textMid']}; font-size:12px;")
            note.setWordWrap(True)
            ar.addWidget(note)
        root.addWidget(self._action_row)

        self._done_btn = btn_primary("Done")
        self._done_btn.clicked.connect(self.accept)
        self._done_btn.hide()
        root.addWidget(self._done_btn)

        def _on_enter():
            # If the backup finished, Enter closes the dialog. Otherwise it
            # triggers the most useful default action (Drive when configured,
            # else archive, else nothing).
            if self._done_btn.isVisible():
                self.accept()
                return
            if self._action_row.isVisible():
                if self.game.get("drive_folder"):
                    self._run("drive")
                elif self.game.get("archive_path"):
                    self._run("archive")
        install_enter_to_advance(self, _on_enter)

    def _run(self, target):
        self._action_row.hide()
        self._log.show()
        self._prog.show()
        self._prog.setValue(0)
        self._step = 0
        game = dict(self.game)
        if target == "drive":
            game["archive_path"] = ""
            game["local_copy"] = ""
        elif target == "archive":
            game["drive_folder"] = ""
            game["local_copy"] = ""
        self._steps = [
            "Scanning save files…",
            "Compressing…",
            "Uploading…" if game.get("drive_folder") else "Writing archive…",
            "Updating timestamp…",
        ]
        self._worker = Worker(ss.run_backup, game, "manual", True)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._fake_timer = QTimer(self)
        self._fake_timer.timeout.connect(self._fake_step)
        self._fake_timer.start(600)
        self._worker.start()

    def _fake_step(self):
        if self._step < len(self._steps):
            self._log.append_line(self._steps[self._step])
            self._prog.setValue(int((self._step + 1) / (len(self._steps) + 1) * 88))
            self._step += 1

    def _on_done(self, result):
        if self._fake_timer:
            self._fake_timer.stop()
        self._prog.setValue(100)
        ok = result is not False
        self._log.append_line("✓ Backup complete" if ok else "✗ Backup failed", ok=ok)
        if ok:
            self.sig_synced.emit(self.game)
        self._done_btn.show()

    def _on_err(self, msg):
        if self._fake_timer:
            self._fake_timer.stop()
        self._log.append_line(f"✗ {msg}", ok=False)
        self._done_btn.show()


# ── SyncDialog ────────────────────────────────────────────────────────────────
class SyncDialog(QDialog):
    sig_synced = pyqtSignal(dict)

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self._worker = None
        self._fake_t = None
        self._drive_worker = None
        self._step = 0
        self._steps = []
        self.setWindowTitle(f"Sync — {game['name']}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(480)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
            f" QLabel {{ color:{C['text']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        title = QLabel(f"Sync — {game['name']}")
        title.setStyleSheet(f"font-size:15px; font-weight:700; color:{C['text']}; background:transparent; border:none;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(18)

        ts_row = QHBoxLayout()
        ts_row.setSpacing(10)
        ts = game.get("backup_timestamp") or game.get("last_sync")

        for cell_name, lbl_text, val in [("syncCellL", "Local", relative_time(ts)), ("syncCellR", "Drive", "—")]:
            cell = QFrame()
            cell.setObjectName(cell_name)
            cell.setStyleSheet(
                f"QFrame#{cell_name} {{ background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px; }}"
                f"QFrame#{cell_name} QLabel {{ background:transparent; border:none; }}"
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(14, 10, 14, 10)
            kl = QLabel(lbl_text.upper())
            kl.setStyleSheet(f"font-size:10px; color:{C['textDim']}; letter-spacing:0.5px;")
            vl = QLabel(val)
            vl.setStyleSheet(f"font-size:14px; font-weight:600; color:{C['text']};")
            cl.addWidget(kl)
            cl.addWidget(vl)
            if cell_name == "syncCellR":
                self._drive_ts_lbl = vl
            ts_row.addWidget(cell, 1)
        root.addLayout(ts_row)

        # Fetch Drive timestamp in background only if Drive folder is configured
        if game.get("drive_folder") and ss.GDRIVE_AVAILABLE:
            self._drive_ts_lbl.setText("checking…")
            def _fetch_drive_ts():
                svc       = ss.get_drive_service()
                folder_id = ss.get_or_create_drive_folder(svc, game["drive_folder"])
                cfg       = ss.fetch_game_config_from_drive(svc, folder_id)
                if cfg:
                    return cfg.get("backup_timestamp") or cfg.get("last_sync") or ""
                return ""
            def _on_drive_ts(ts_str):
                self._drive_ts_lbl.setText(relative_time(ts_str) if ts_str else "no backup yet")
            def _on_drive_ts_err(_e):
                self._drive_ts_lbl.setText("unavailable")
            self._drive_worker = Worker(_fetch_drive_ts)
            self._drive_worker.finished.connect(_on_drive_ts)
            self._drive_worker.error.connect(_on_drive_ts_err)
            self._drive_worker.start()
        root.addSpacing(14)

        # ── Save info row ──────────────────────────────────────────────────────
        info_box = QFrame()
        info_box.setObjectName("syncInfoBox")
        info_box.setStyleSheet(
            f"QFrame#syncInfoBox {{ background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px; }}"
            f"QFrame#syncInfoBox QLabel {{ background:transparent; border:none; }}"
        )
        info_l = QVBoxLayout(info_box)
        info_l.setContentsMargins(14, 10, 14, 10)
        info_l.setSpacing(4)

        save_path = game.get("save_path", "")
        _path_label = QLabel(save_path or "(no path set)")
        _path_label.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        _path_label.setWordWrap(True)
        info_l.addWidget(_path_label)

        try:
            import os
            from pathlib import Path as _P
            p = _P(save_path)
            if p.is_dir():
                files = [f for f in p.rglob("*") if f.is_file()]
                total = sum(f.stat().st_size for f in files)
            elif p.is_file():
                files = [p]
                total = p.stat().st_size
            else:
                files = []
                total = 0
            n = len(files)
            if total >= 1_048_576:
                size_str = f"{total/1_048_576:.1f} MB"
            elif total >= 1024:
                size_str = f"{total/1024:.1f} KB"
            else:
                size_str = f"{total} B"
            stats_str = f"{n} file{'s' if n != 1 else ''}  ·  {size_str}"
        except Exception:
            stats_str = "—"

        _stats_label = QLabel(stats_str)
        _stats_label.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        info_l.addWidget(_stats_label)

        root.addWidget(info_box)
        root.addSpacing(10)

        dir_box = QFrame()
        dir_box.setObjectName("syncDirBox")
        dir_box.setStyleSheet(
            "QFrame#syncDirBox { background:rgba(124,111,255,0.08); border:1px solid rgba(124,111,255,0.2); border-radius:10px; }"
            "QFrame#syncDirBox QLabel { background:transparent; border:none; }"
        )
        dir_l = QHBoxLayout(dir_box)
        dir_l.setContentsMargins(16, 12, 16, 12)
        dir_lbl = QLabel("↑ Local → Drive (upload)")
        dir_lbl.setStyleSheet(f"color:{C['text']}; font-size:12px;")
        dir_l.addWidget(dir_lbl)
        root.addWidget(dir_box)
        root.addSpacing(12)

        self._log = LogBox()
        self._log.setFixedHeight(110)
        self._log.hide()
        root.addWidget(self._log)

        self._prog = QProgressBar()
        self._prog.setRange(0, 100)
        self._prog.hide()
        root.addWidget(self._prog)
        root.addSpacing(16)

        foot = QHBoxLayout()
        self._cancel_btn = btn_ghost("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        foot.addWidget(self._cancel_btn)
        foot.addStretch()
        self._sync_btn = btn_primary("↑ Sync to Drive")
        self._sync_btn.clicked.connect(self._run)
        foot.addWidget(self._sync_btn)
        root.addLayout(foot)

        self._done_btn = btn_primary("Done")
        self._done_btn.clicked.connect(self.accept)
        self._done_btn.hide()
        root.addWidget(self._done_btn)

        def _on_enter():
            if self._done_btn.isVisible():
                self.accept()
            elif self._sync_btn.isVisible():
                self._run()
        install_enter_to_advance(self, _on_enter)

    def _run(self):
        self._sync_btn.hide()
        self._cancel_btn.hide()
        self._log.show()
        self._prog.show()
        self._prog.setValue(0)
        self._step = 0
        self._steps = ["Creating snapshot…", "Connecting to Drive…", "Uploading files…", "Finalising…"]
        self._worker = Worker(ss.run_backup, self.game, "manual sync", True)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._fake_t = QTimer(self)
        self._fake_t.timeout.connect(self._fake_step)
        self._fake_t.start(600)
        self._worker.start()

    def _fake_step(self):
        if self._step < len(self._steps):
            self._log.append_line(self._steps[self._step])
            self._prog.setValue(int((self._step + 1) / (len(self._steps) + 1) * 88))
            self._step += 1

    def _on_done(self, result):
        if self._fake_t:
            self._fake_t.stop()
        self._prog.setValue(100)
        ok = result is not False
        self._log.append_line("✓ Sync complete" if ok else "✗ Sync failed", ok=ok)
        if ok:
            self.sig_synced.emit(self.game)
        self._done_btn.show()

    def _on_err(self, msg):
        if self._fake_t:
            self._fake_t.stop()
        self._log.append_line(f"✗ {msg}", ok=False)
        self._done_btn.show()


# ── EditGameDialog ─────────────────────────────────────────────────────────────
class EditGameDialog(QDialog):
    saved = pyqtSignal(dict)

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = dict(game)
        self.setWindowTitle(f"Edit — {game['name']}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(500)
        self.setMinimumHeight(500)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
            f" QLabel {{ color:{C['text']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        title = QLabel(f"Edit — {game['name']}")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px;"
            f" font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        form = QVBoxLayout(inner)
        form.setSpacing(14)
        form.setContentsMargins(0, 0, 12, 0)

        self._fields = {}
        field_defs = [
            ("Game name",           "name",         False, None),
            ("Save path",           "save_path",    True,  "dir"),
            ("Exe name",            "exe_name",     True,  None),
            ("Exe path (optional)", "exe_path",     True,  "file"),
            ("Google Drive folder", "drive_folder", False, None),
            ("Archive path",        "archive_path", True,  "dir"),
        ]
        for label, key, mono, browse in field_defs:
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
            form.addWidget(lbl)
            le = QLineEdit(str(game.get(key, "") or ""))
            if not mono:
                le.setStyleSheet(le.styleSheet() + "font-family:'Inter','Segoe UI',sans-serif;")
            if browse:
                row = QHBoxLayout()
                row.setSpacing(6)
                row.addWidget(le, 1)
                br = btn_ghost("Browse…", small=True)
                if browse == "dir":
                    br.clicked.connect(lambda _, e=le: self._browse_dir(e))
                else:
                    br.clicked.connect(lambda _, e=le: self._browse_file(e))
                row.addWidget(br)
                form.addLayout(row)
            else:
                form.addWidget(le)
            self._fields[key] = le

        lbl_t = QLabel("TRIGGERS")
        lbl_t.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
        form.addWidget(lbl_t)
        trig_row = QHBoxLayout()
        trig_row.setSpacing(8)
        self._chk_launch = self._toggle_btn("On launch", game.get("trigger_launch", True))
        self._chk_close  = self._toggle_btn("On close",  game.get("trigger_close",  True))
        trig_row.addWidget(self._chk_launch)
        trig_row.addWidget(self._chk_close)
        trig_row.addStretch()
        form.addLayout(trig_row)

        lbl_i = QLabel("INTERVAL (MINUTES, 0 = OFF)")
        lbl_i.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
        form.addWidget(lbl_i)
        self._interval = QLineEdit(str(game.get("interval_min", 0)))
        self._interval.setFixedWidth(80)
        form.addWidget(self._interval)

        scroll.setWidget(inner)
        root.addWidget(scroll)
        root.addSpacing(16)

        foot = QHBoxLayout()
        c_btn = btn_ghost("Cancel")
        c_btn.clicked.connect(self.reject)
        foot.addWidget(c_btn)
        foot.addStretch()
        s_btn = btn_primary("Save Changes")
        s_btn.clicked.connect(self._save)
        foot.addWidget(s_btn)
        root.addLayout(foot)

        install_enter_to_advance(self, self._save)

    def _toggle_btn(self, text, checked):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setChecked(checked)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        def _rs():
            on = b.isChecked()
            b.setStyleSheet(
                f"QPushButton {{ background:{'rgba(124,111,255,0.15)' if on else C['cardH']};"
                f" color:{C['accent'] if on else C['textMid']};"
                f" border:1px solid {C['accentD'] if on else C['border']};"
                f" border-radius:8px; padding:8px 14px; font-size:12px; }}"
            )
        b.toggled.connect(lambda _: _rs())
        _rs()
        return b

    def _browse_dir(self, edit):
        d = QFileDialog.getExistingDirectory(self, "Select folder")
        if d:
            edit.setText(d)

    def _browse_file(self, edit):
        f, _ = QFileDialog.getOpenFileName(self, "Select file")
        if f:
            edit.setText(f)

    def _save(self):
        g = dict(self.game)
        for k, le in self._fields.items():
            g[k] = le.text().strip()
        g["trigger_launch"] = self._chk_launch.isChecked()
        g["trigger_close"]  = self._chk_close.isChecked()
        try:
            g["interval_min"] = int(self._interval.text())
        except Exception:
            g["interval_min"] = 0
        self.saved.emit(g)
        self.accept()


# ── AddGameWizard ─────────────────────────────────────────────────────────────
WIZARD_STEPS = ["Name", "Save Path", "Launcher", "Destinations", "Triggers", "Confirm"]


class AddGameWizard(QDialog):
    added = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Game")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(520)
        self.setMinimumHeight(420)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
            f" QLabel {{ color:{C['text']}; }}"
        )
        self._step = 0
        self._form = {
            "name": "", "save_path": "", "exe_name": "", "exe_path": "",
            "drive_folder": "", "archive_path": "",
            "trigger_launch": True, "trigger_close": True,
            "interval_min": 0, "max_backups": 10,
        }
        self._search_worker  = None
        self._search_worker2 = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        self._title_lbl = QLabel("Add Game")
        self._title_lbl.setStyleSheet("font-size:16px; font-weight:700;")
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        self._step_lbl = QLabel("Step 1 of 6")
        self._step_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        hdr.addWidget(self._step_lbl)
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px;"
            f" font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(16)

        sb_outer = QVBoxLayout()
        sb_outer.setSpacing(4)
        bar_row = QHBoxLayout()
        bar_row.setSpacing(4)
        lbl_row = QHBoxLayout()
        lbl_row.setSpacing(4)
        self._step_bars   = []
        self._step_labels = []
        for s in WIZARD_STEPS:
            f = QFrame()
            f.setFixedHeight(3)
            f.setStyleSheet(f"background:{C['border']}; border-radius:99px;")
            bar_row.addWidget(f, 1)
            self._step_bars.append(f)
            lbl = QLabel(s.upper())
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"font-size:9px; color:{C['textDim']}; letter-spacing:0.5px;")
            lbl_row.addWidget(lbl, 1)
            self._step_labels.append(lbl)
        sb_outer.addLayout(bar_row)
        sb_outer.addLayout(lbl_row)
        root.addLayout(sb_outer)
        root.addSpacing(20)

        self._content = QStackedWidget()
        self._content.setMinimumHeight(200)
        root.addWidget(self._content)
        root.addStretch(1)
        root.addSpacing(20)

        foot = QHBoxLayout()
        self._back_btn = btn_ghost("Cancel")
        self._back_btn.clicked.connect(self._go_back)
        foot.addWidget(self._back_btn)
        foot.addStretch()
        self._next_btn = btn_primary("Next →")
        self._next_btn.clicked.connect(self._go_next)
        foot.addWidget(self._next_btn)
        root.addLayout(foot)

        self._pages = [
            self._page_name(),
            self._page_save_path(),
            self._page_launcher(),
            self._page_destinations(),
            self._page_triggers(),
            self._page_confirm(),
        ]
        for pg in self._pages:
            self._content.addWidget(pg)

        self._refresh()

        # Enter advances to the next step / saves on the final step.
        install_enter_to_advance(
            self,
            lambda: self._next_btn.click() if self._next_btn.isEnabled() else None,
        )

    def _page_name(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(10)
        hint = QLabel("Enter the name of the game as it appears in your library.")
        hint.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        hint.setWordWrap(True)
        l.addWidget(hint)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Dark Souls III")
        self._name_edit.setStyleSheet(
            self._name_edit.styleSheet() + "font-family:'Inter','Segoe UI',sans-serif;"
        )
        self._name_edit.textChanged.connect(self._on_name_changed)
        l.addWidget(self._name_edit)
        self._db_results_widget = QWidget()
        self._db_results_layout = QVBoxLayout(self._db_results_widget)
        self._db_results_layout.setContentsMargins(0, 0, 0, 0)
        self._db_results_layout.setSpacing(4)
        l.addWidget(self._db_results_widget)
        l.addStretch()
        return w

    def _page_save_path(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(10)
        self._path_hint = QLabel("Where does the game store save files?")
        self._path_hint.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        self._path_hint.setWordWrap(True)
        l.addWidget(self._path_hint)
        self._sug_widget = QWidget()
        self._sug_layout = QVBoxLayout(self._sug_widget)
        self._sug_layout.setContentsMargins(0, 0, 0, 0)
        self._sug_layout.setSpacing(4)
        l.addWidget(self._sug_widget)
        row = QHBoxLayout()
        self._save_edit = QLineEdit()
        self._save_edit.setPlaceholderText("C:/Users/…/SaveFolder")
        row.addWidget(self._save_edit, 1)
        br = btn_ghost("Browse…", small=True)
        br.clicked.connect(lambda: self._browse_dir(self._save_edit))
        row.addWidget(br)
        l.addLayout(row)
        l.addStretch()
        return w

    def _page_launcher(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(10)
        hint = QLabel("Optional: enables automatic backups on game launch/close.")
        hint.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        hint.setWordWrap(True)
        l.addWidget(hint)
        lbl1 = QLabel("EXE NAME (e.g. hollow_knight.exe)")
        lbl1.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
        l.addWidget(lbl1)
        self._exe_name_edit = QLineEdit()
        self._exe_name_edit.setPlaceholderText("game.exe")
        l.addWidget(self._exe_name_edit)
        lbl2 = QLabel("EXE FULL PATH (OPTIONAL)")
        lbl2.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
        l.addWidget(lbl2)
        row = QHBoxLayout()
        self._exe_path_edit = QLineEdit()
        self._exe_path_edit.setPlaceholderText("C:/Games/…/game.exe")
        row.addWidget(self._exe_path_edit, 1)
        br = btn_ghost("Browse…", small=True)
        br.clicked.connect(lambda: self._browse_file(self._exe_path_edit))
        row.addWidget(br)
        l.addLayout(row)
        skip = QLabel("Leave blank to use manual backup only.")
        skip.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        l.addWidget(skip)
        l.addStretch()
        return w

    def _page_destinations(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)
        hint = QLabel("Where should backups be stored?")
        hint.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        l.addWidget(hint)
        lbl1 = QLabel("GOOGLE DRIVE FOLDER")
        lbl1.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
        l.addWidget(lbl1)
        self._drive_edit = QLineEdit()
        self._drive_edit.setPlaceholderText("SaveSync/GameName")
        self._drive_edit.setStyleSheet(
            self._drive_edit.styleSheet() + "font-family:'Inter','Segoe UI',sans-serif;"
        )
        l.addWidget(self._drive_edit)
        lbl2 = QLabel("LOCAL .7Z ARCHIVE PATH")
        lbl2.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
        l.addWidget(lbl2)
        row = QHBoxLayout()
        self._archive_edit = QLineEdit()
        self._archive_edit.setPlaceholderText("D:/Backups/GameName")
        row.addWidget(self._archive_edit, 1)
        br = btn_ghost("Browse…", small=True)
        br.clicked.connect(lambda: self._browse_dir(self._archive_edit))
        row.addWidget(br)
        l.addLayout(row)
        l.addStretch()
        return w

    def _page_triggers(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(16)
        hint = QLabel("When should automatic backups run?")
        hint.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        l.addWidget(hint)
        tr = QHBoxLayout()
        tr.setSpacing(8)
        self._wiz_launch = self._toggle_chk("On game launch", True)
        self._wiz_close  = self._toggle_chk("On game close",  True)
        tr.addWidget(self._wiz_launch)
        tr.addWidget(self._wiz_close)
        tr.addStretch()
        l.addLayout(tr)
        lbl_i = QLabel("INTERVAL BACKUP (MINUTES, 0 = DISABLED)")
        lbl_i.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
        l.addWidget(lbl_i)
        self._wiz_interval = QLineEdit("0")
        self._wiz_interval.setFixedWidth(80)
        l.addWidget(self._wiz_interval)
        lbl_m = QLabel("MAX LOCAL SNAPSHOTS")
        lbl_m.setStyleSheet(f"font-size:11px; color:{C['textDim']}; letter-spacing:0.5px;")
        l.addWidget(lbl_m)
        self._wiz_max = QLineEdit("10")
        self._wiz_max.setFixedWidth(80)
        l.addWidget(self._wiz_max)
        l.addStretch()
        return w

    def _page_confirm(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(8)
        hint = QLabel("Review your configuration before saving.")
        hint.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        l.addWidget(hint)
        self._confirm_lbl = QLabel()
        self._confirm_lbl.setWordWrap(True)
        self._confirm_lbl.setStyleSheet("font-size:12px; line-height:1.6;")
        l.addWidget(self._confirm_lbl)
        l.addStretch()
        return w

    def _refresh(self):
        self._content.setCurrentIndex(self._step)
        self._step_lbl.setText(f"Step {self._step + 1} of {len(WIZARD_STEPS)}")
        for i, (bar, lbl) in enumerate(zip(self._step_bars, self._step_labels)):
            done = i < self._step
            curr = i == self._step
            bar.setStyleSheet(
                f"background:{C['accent'] if (done or curr) else C['border']}; border-radius:99px;"
            )
            lbl.setStyleSheet(
                f"font-size:9px; letter-spacing:0.5px;"
                f" color:{C['accent'] if curr else (C['accentD'] if done else C['textDim'])};"
            )
        self._back_btn.setText("Cancel" if self._step == 0 else "← Back")
        self._next_btn.setText("✓ Save Game" if self._step == len(WIZARD_STEPS) - 1 else "Next →")
        self._next_btn.setEnabled(self._can_next())
        if self._step == len(WIZARD_STEPS) - 1:
            self._update_confirm()

    def _can_next(self):
        if self._step == 0:
            return bool(self._form["name"].strip())
        return True

    def _collect(self):
        s = self._step
        if s == 0:
            self._form["name"] = self._name_edit.text().strip()
        elif s == 1:
            self._form["save_path"] = self._save_edit.text().strip()
        elif s == 2:
            self._form["exe_name"] = self._exe_name_edit.text().strip()
            self._form["exe_path"] = self._exe_path_edit.text().strip()
        elif s == 3:
            self._form["drive_folder"] = self._drive_edit.text().strip()
            self._form["archive_path"] = self._archive_edit.text().strip()
        elif s == 4:
            self._form["trigger_launch"] = self._wiz_launch.isChecked()
            self._form["trigger_close"]  = self._wiz_close.isChecked()
            try:    self._form["interval_min"] = int(self._wiz_interval.text())
            except: self._form["interval_min"] = 0
            try:    self._form["max_backups"]   = int(self._wiz_max.text())
            except: self._form["max_backups"]   = 10

    def _go_next(self):
        self._collect()
        if self._step == len(WIZARD_STEPS) - 1:
            self.added.emit(dict(self._form))
            self.accept()
            return
        self._step += 1
        if self._step == 1:
            self._populate_suggestions()
        self._refresh()

    def _go_back(self):
        if self._step == 0:
            self.reject()
            return
        self._step -= 1
        self._refresh()

    def _update_confirm(self):
        f = self._form
        trigs = ", ".join(filter(None, [
            "launch" if f["trigger_launch"] else "",
            "close"  if f["trigger_close"]  else "",
            f"{f['interval_min']} min" if f["interval_min"] else "",
        ])) or "none"
        lines = [
            f"<b>Name:</b> {f['name'] or '—'}",
            f"<b>Save path:</b> {f['save_path'] or '—'}",
            f"<b>Exe name:</b> {f['exe_name'] or 'not set'}",
            f"<b>Drive folder:</b> {f['drive_folder'] or 'not set'}",
            f"<b>Archive path:</b> {f['archive_path'] or 'not set'}",
            f"<b>Triggers:</b> {trigs}",
            f"<b>Max snapshots:</b> {f['max_backups']}",
        ]
        self._confirm_lbl.setText("<br>".join(lines))

    def _on_name_changed(self, text):
        self._form["name"] = text
        self._next_btn.setEnabled(self._can_next())
        for i in reversed(range(self._db_results_layout.count())):
            w = self._db_results_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        if len(text) < 2:
            return
        if self._search_worker and self._search_worker.isRunning():
            return
        self._search_worker = Worker(ss.search_manifest_split, text)
        self._search_worker.finished.connect(self._on_db_results)
        self._search_worker.start()

    def _on_db_results(self, result):
        for i in reversed(range(self._db_results_layout.count())):
            w = self._db_results_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        _, candidates = result if isinstance(result, tuple) else (None, [])
        if not candidates:
            return
        lbl = QLabel("Ludusavi database matches:")
        lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        self._db_results_layout.addWidget(lbl)
        for entry in (candidates or [])[:3]:
            # entry is (display_name, [paths])
            name = entry[0] if isinstance(entry, (tuple, list)) else ""
            if not name:
                continue
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background:{C['bg2']}; border:1px solid {C['border']};"
                f" border-radius:8px; padding:8px 12px; text-align:left; color:{C['text']};"
                f" font-size:12px; font-family:'Inter','Segoe UI',sans-serif; }}"
                f"QPushButton:hover {{ border-color:{C['accent']}; }}"
            )
            btn.clicked.connect(lambda _, n=name: self._pick_name(n))
            self._db_results_layout.addWidget(btn)

    def _pick_name(self, name):
        self._name_edit.setText(name)
        for i in reversed(range(self._db_results_layout.count())):
            w = self._db_results_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

    def _populate_suggestions(self):
        for i in reversed(range(self._sug_layout.count())):
            w = self._sug_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        name = self._form["name"]
        if not name:
            return
        self._search_worker2 = Worker(ss.search_manifest_split, name)
        self._search_worker2.finished.connect(self._on_path_suggestions)
        self._search_worker2.start()

    def _on_path_suggestions(self, result):
        for i in reversed(range(self._sug_layout.count())):
            w = self._sug_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        exact, candidates = result if isinstance(result, tuple) else (None, [])
        paths = []
        # exact is (name, [paths]) or None
        if exact:
            _, exact_paths = exact
            paths.extend(exact_paths[:3])
        if not paths and candidates:
            for entry in (candidates or [])[:2]:
                _, entry_paths = entry
                paths.extend(entry_paths[:1])
        if not paths:
            return
        lbl = QLabel("Suggested paths from database:")
        lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        self._sug_layout.addWidget(lbl)
        for path in paths[:3]:
            btn = QPushButton(path)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background:{C['bg2']}; border:1px solid {C['border']};"
                f" border-radius:8px; padding:8px 12px; text-align:left;"
                f" color:{C['driveFg']}; font-family:'JetBrains Mono','Consolas',monospace;"
                f" font-size:11px; }}"
                f"QPushButton:hover {{ border-color:{C['accent']}; }}"
            )
            btn.clicked.connect(lambda _, p=path: self._save_edit.setText(p))
            self._sug_layout.addWidget(btn)

    def _toggle_chk(self, text, checked):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setChecked(checked)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        def _rs():
            on = b.isChecked()
            b.setStyleSheet(
                f"QPushButton {{ background:{'rgba(124,111,255,0.15)' if on else C['cardH']};"
                f" color:{C['accent'] if on else C['textMid']};"
                f" border:1px solid {C['accentD'] if on else C['border']};"
                f" border-radius:8px; padding:8px 14px; font-size:12px; }}"
            )
        b.toggled.connect(lambda _: _rs())
        _rs()
        return b

    def _browse_dir(self, edit):
        d = QFileDialog.getExistingDirectory(self, "Select folder")
        if d:
            edit.setText(d)

    def _browse_file(self, edit):
        f, _ = QFileDialog.getOpenFileName(self, "Select file")
        if f:
            edit.setText(f)



# ── GamesPanel ────────────────────────────────────────────────────────────────
class GamesPanel(QWidget):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._main_win   = main_win
        self._games      = CFG.get("games", [])
        self._cards      = {}   # name -> GameCard
        self._workers    = []
        self._col_count  = 4

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        topbar = QWidget()
        topbar.setStyleSheet(f"background:{C['bg']};")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(24, 18, 24, 0)
        tb.setSpacing(12)

        title = QLabel("Games")
        title.setStyleSheet(f"font-size:17px; font-weight:700; letter-spacing:-0.3px; color:{C['text']};")
        tb.addWidget(title)

        # Search
        search_wrap = QWidget()
        search_wrap.setFixedWidth(260)
        sw = QHBoxLayout(search_wrap)
        sw.setContentsMargins(0, 0, 0, 0)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search games…")
        self._search.setStyleSheet(
            f"QLineEdit {{ background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;"
            f" padding:7px 10px 7px 28px; font-size:12px; color:{C['text']}; }}"
            f"QLineEdit:focus {{ border-color:{C['accent']}; }}"
        )
        self._search.textChanged.connect(self._apply_filter)
        sw.addWidget(self._search)
        tb.addWidget(search_wrap)

        tb.addStretch()
        add_from_drive = _icon_btn_ghost("Add from Drive", "drive", small=True)
        add_from_drive.clicked.connect(self._import_from_drive)
        tb.addWidget(add_from_drive)
        add_btn = btn_primary("+ Add Game", small=True)
        add_btn.clicked.connect(self._add_game)
        tb.addWidget(add_btn)

        root.addWidget(topbar)
        root.addSpacing(16)

        # Scrollable grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet(f"background:{C['bg']};")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(24, 0, 24, 24)
        self._grid.setSpacing(16)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_widget)
        root.addWidget(self._scroll, 1)

        self._rebuild_grid()

    def _rebuild_grid(self, filter_text=""):
        # Clear
        for i in reversed(range(self._grid.count())):
            item = self._grid.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        self._cards.clear()
        self._workers.clear()

        filtered = [g for g in self._games
                    if filter_text.lower() in g.get("name","").lower()]

        if not filtered:
            if not self._games:
                self._show_empty()
            return

        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._grid_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        row, col = 0, 0
        cols = max(1, self._col_count)
        for game in filtered:
            card = GameCard(game)
            card.sig_sync.connect(lambda g: self._open_sync_dialog(g))
            card.sig_backup.connect(lambda g: self._do_backup(g))
            card.sig_edit.connect(self._edit_game)
            card.sig_remove.connect(self._remove_game)
            card.sig_open_folder.connect(self._open_save_folder)
            self._grid.addWidget(card, row, col)
            self._cards[game.get("name","")] = card

            # Prefetch thumbnail
            pm = get_thumb_pixmap(game.get("name",""))
            if pm:
                card.set_pixmap(pm)
            else:
                w = ThumbWorker(game.get("name",""))
                w.done.connect(self._on_thumb)
                self._workers.append(w)
                w.start()

            col += 1
            if col >= cols:
                col = 0
                row += 1


    def _show_empty(self):
        self._grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        empty = QWidget()
        empty.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        el = QVBoxLayout(empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("💾")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size:40px;")
        el.addWidget(icon)
        h = QLabel("No games yet")
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.setStyleSheet(f"font-size:18px; font-weight:700; color:{C['text']};")
        el.addWidget(h)
        sub = QLabel("Add your first game to start protecting save files.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"font-size:13px; color:{C['textMid']};")
        el.addWidget(sub)
        el.addSpacing(20)
        add_btn = btn_primary("+ Add First Game")
        add_btn.clicked.connect(self._add_game)
        el.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignCenter)
        self._grid.addWidget(empty, 0, 0, 1, max(1, self._col_count))

    def _on_thumb(self, name, path):
        card = self._cards.get(name)
        if card and Path(path).exists():
            card.set_pixmap(QPixmap(path))

    def _apply_filter(self, text):
        self._rebuild_grid(text)

    def resizeEvent(self, e):
        super().resizeEvent(e)

    def _add_game(self):
        dlg = AddGameWizard(self)
        dlg.added.connect(self._on_game_added)
        dlg.exec()

    def _on_game_added(self, form):
        game = {**ss.GAME_DEFAULTS, **form}
        self._games.append(game)
        CFG["games"] = self._games
        ss.save_config(CFG)
        self._rebuild_grid(self._search.text())
        self._main_win._panel_watcher._rebuild_proc_list()
        show_toast(f"{form['name']} added to SaveSync", "success", self._main_win)

    def _open_save_folder(self, game):
        path = game.get("save_path", "")
        if not path or not Path(path).exists():
            show_toast("Save folder not found.", "error", self._main_win)
            return
        import subprocess
        subprocess.Popen(["explorer", str(Path(path))])

    def _edit_game(self, game):
        dlg = EditGameDialog(game, self)
        dlg.saved.connect(self._on_game_saved)
        dlg.exec()

    def _on_game_saved(self, updated):
        for i, g in enumerate(self._games):
            if g.get("name") == updated.get("name") or g is self._edit_target:
                self._games[i] = updated
                break
        CFG["games"] = self._games
        ss.save_config(CFG)
        self._rebuild_grid(self._search.text())
        self._main_win._panel_watcher._rebuild_proc_list()
        show_toast(f"{updated['name']} updated", "success", self._main_win)

    def _remove_game(self, game):
        name = game.get("name", "")
        dlg = QDialog(self)
        dlg.setWindowTitle("Remove game")
        dlg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        dlg.setFixedWidth(360)
        dlg.setStyleSheet(
            f"QDialog {{ background:transparent; }}"
        )

        outer = QWidget(dlg)
        outer.setObjectName("confirmOuter")
        outer.setStyleSheet(
            f"#confirmOuter {{ background:{C['card']}; border:1px solid {C['border']};"
            f" border-radius:12px; }}"
        )

        lbl = QLabel(f"Remove <b>{name}</b> from SaveSync?")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{C['text']}; font-size:13px; border:none;")

        btn_cancel = btn_ghost("Cancel", small=True)
        btn_remove = QPushButton("Remove")
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setStyleSheet(
            f"QPushButton {{ background:{C['error']}; color:#fff; border:none;"
            f" border-radius:8px; padding:7px 18px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:#c03040; }}"
        )

        btn_cancel.clicked.connect(dlg.reject)
        btn_remove.clicked.connect(dlg.accept)

        btns = QHBoxLayout()
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_remove)

        inner = QVBoxLayout(outer)
        inner.setContentsMargins(24, 20, 24, 20)
        inner.setSpacing(16)
        inner.addWidget(lbl)
        inner.addLayout(btns)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(outer)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._games = [g for g in self._games if g.get("name") != name]
            CFG["games"] = self._games
            ss.save_config(CFG)
            self._rebuild_grid(self._search.text())
            self._main_win._panel_watcher._rebuild_proc_list()
            show_toast(f"{name} removed", "info", self._main_win)

    def _open_sync_dialog(self, game):
        dlg = SyncDialog(game, self)
        dlg.sig_synced.connect(self._on_game_synced)
        dlg.exec()

    def _do_backup(self, game):
        dlg = BackupDialog(game, self)
        dlg.sig_synced.connect(self._on_game_synced)
        dlg.exec()

    def _on_game_synced(self, game):
        fresh_cfg = ss.load_config()
        for g in fresh_cfg.get("games", []):
            if g["name"] == game["name"]:
                game.update(g)
                break
        card = self._cards.get(game["name"])
        if card:
            card.refresh(game)

    def _import_from_drive(self):
        if not ss.GDRIVE_AVAILABLE:
            show_toast("Google Drive not available. Install google-api-python-client.", "error", self._main_win)
            return
        show_toast("Scanning Drive for game folders…", "info", self._main_win)
        def _scan():
            svc = ss.get_drive_service()
            return ss.list_drive_game_folders(svc)
        w = Worker(_scan)
        w.finished.connect(self._on_drive_folders)
        w.error.connect(lambda e: show_toast(f"Drive error: {e}", "error", self._main_win))
        self._import_worker = w
        w.start()

    def _on_drive_folders(self, folders):
        existing = {g.get("name", "") for g in self._games}
        new_folders = [f for f in folders if f["name"] not in existing]
        if not new_folders:
            show_toast("No new games found on Drive.", "info", self._main_win)
            return
        new_names = [f["name"] for f in new_folders]
        dlg = DriveImportDialog(new_names, self._main_win)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        chosen_names = set(dlg.selected_names())
        if not chosen_names:
            show_toast("No games selected.", "info", self._main_win)
            return
        chosen_folders = [f for f in new_folders if f["name"] in chosen_names]
        show_toast(f"Fetching config for {len(chosen_folders)} game(s)…", "info", self._main_win)

        def _fetch_configs():
            svc = ss.get_drive_service()
            results = []
            for folder in chosen_folders:
                cfg = ss.fetch_game_config_from_drive(svc, folder["id"]) or {}
                game = {**ss.GAME_DEFAULTS, "name": folder["name"],
                        "drive_folder": f"SaveSync/{folder['name']}", **cfg}
                game["name"]         = folder["name"]
                game["drive_folder"] = f"SaveSync/{folder['name']}"
                results.append(game)
            return results

        def _on_configs(games):
            for game in games:
                self._games.append(game)
            CFG["games"] = self._games
            ss.save_config(CFG)
            self._rebuild_grid(self._search.text())
            show_toast(f"Imported {len(games)} game(s) from Drive.", "success", self._main_win)

        w2 = Worker(_fetch_configs)
        w2.finished.connect(_on_configs)
        w2.error.connect(lambda e: show_toast(f"Config fetch error: {e}", "error", self._main_win))
        self._import_cfg_worker = w2
        w2.start()

    def refresh(self):
        self._games = CFG.get("games", [])
        self._rebuild_grid(self._search.text())


# ── WatcherPanel ──────────────────────────────────────────────────────────────
class WatcherPanel(QWidget):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._main_win  = main_win
        self._running   = False
        self._watcher   = None
        self._start_time = None
        self._tick_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        topbar = QWidget()
        topbar.setStyleSheet(f"background:{C['bg']};")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(24, 18, 24, 0)
        tb.setSpacing(12)
        title = QLabel("Watcher")
        title.setStyleSheet(f"font-size:17px; font-weight:700; letter-spacing:-0.3px;")
        tb.addWidget(title)
        tb.addStretch()
        self._uptime_lbl = QLabel("")
        self._uptime_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        tb.addWidget(self._uptime_lbl)
        root.addWidget(topbar)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C['bg']};")
        il = QVBoxLayout(inner)
        il.setContentsMargins(32, 8, 32, 32)
        il.setSpacing(0)

        # Hero status card
        hero = QWidget()
        hero.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(0, 16, 0, 20)
        hl.setSpacing(24)

        self._radar = RadarWidget()
        hl.addWidget(self._radar)

        info_col = QVBoxLayout()
        info_col.setSpacing(4)
        self._status_title = QLabel("Watcher is stopped")
        self._status_title.setStyleSheet(f"font-size:15px; font-weight:700; color:{C['text']};")
        info_col.addWidget(self._status_title)
        self._status_sub = QLabel("Start the watcher to enable automatic backups")
        self._status_sub.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        info_col.addWidget(self._status_sub)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(0, 8, 0, 0)
        self._toggle_btn = btn_primary("Start Watcher", small=True)
        self._toggle_btn.clicked.connect(self._toggle)
        self._toggle_btn.setFixedWidth(160)
        btn_row.addWidget(self._toggle_btn)
        startup_btn = btn_ghost("Add to Startup", small=True)
        startup_btn.clicked.connect(self._add_to_startup)
        btn_row.addWidget(startup_btn)
        health_btn = btn_ghost("Health Check", small=True)
        health_btn.clicked.connect(self._health_check)
        btn_row.addWidget(health_btn)
        btn_row.addStretch()
        info_col.addLayout(btn_row)

        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(24)
        self._stat_watching = self._stat_widget("0", "Watching")
        self._stat_active   = self._stat_widget("0", "Active")
        self._stat_today    = self._stat_widget("0", "Backups today")
        self._stats_row.addWidget(self._stat_watching[0])
        self._stats_row.addWidget(self._stat_active[0])
        self._stats_row.addWidget(self._stat_today[0])
        self._stats_row.addStretch()
        stats_w = QWidget()
        stats_w.setLayout(self._stats_row)
        stats_w.hide()
        self._stats_widget = stats_w
        info_col.addWidget(stats_w)
        hl.addLayout(info_col, 1)
        il.addWidget(hero)

        # Process list
        il.addWidget(section_title("Watched Processes"))
        self._proc_container = QWidget()
        self._proc_container.setStyleSheet("background: transparent;")
        self._proc_layout = QVBoxLayout(self._proc_container)
        self._proc_layout.setContentsMargins(0, 0, 0, 0)
        self._proc_layout.setSpacing(0)
        self._rebuild_proc_list()
        il.addWidget(self._proc_container)

        # Activity log
        il.addWidget(section_title("Activity Log"))
        self._log = LogBox()
        self._log.setMinimumHeight(160)
        il.addWidget(self._log)

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # Uptime ticker
        self._ticker = QTimer(self)
        self._ticker.timeout.connect(self._tick)
        self._ticker.start(1000)

    def _stat_widget(self, val, label):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(2)
        val_lbl = QLabel(val)
        val_lbl.setStyleSheet(f"font-size:18px; font-weight:700; color:{C['text']};")
        lbl_lbl = QLabel(label.upper())
        lbl_lbl.setStyleSheet(f"font-size:10px; color:{C['textDim']}; letter-spacing:0.5px;")
        l.addWidget(val_lbl)
        l.addWidget(lbl_lbl)
        return w, val_lbl

    def _rebuild_proc_list(self):
        for i in reversed(range(self._proc_layout.count())):
            item = self._proc_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        games = CFG.get("games", [])
        watched = [g for g in games if g.get("exe_name")]

        if self._running:
            self._status_sub.setText(f"Monitoring {len(watched)} process(es)")
            self._stat_watching[1].setText(str(len(watched)))

        if not watched:
            lbl = QLabel("No games with exe configured. Edit a game to add its exe name.")
            lbl.setStyleSheet(f"color:{C['textDim']}; font-size:12px;")
            self._proc_layout.addWidget(lbl)
            return

        for idx, game in enumerate(watched):
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 12, 0, 12)
            rl.setSpacing(12)

            dot = QWidget()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background:{C['textDim']}; border-radius:4px; border:none;"
            )
            rl.addWidget(dot)

            info = QVBoxLayout()
            info.setSpacing(2)
            name_lbl = QLabel(game.get("name",""))
            name_lbl.setStyleSheet(f"font-size:12px; font-weight:500; color:{C['text']};")
            info.addWidget(name_lbl)
            exe_lbl = QLabel(game.get("exe_name",""))
            exe_lbl.setStyleSheet(
                f"font-size:10px; color:{C['textDim']}; font-family:'JetBrains Mono','Consolas',monospace;"
            )
            info.addWidget(exe_lbl)
            rl.addLayout(info, 1)

            ts = game.get("backup_timestamp") or game.get("last_sync")
            if ts:
                last_lbl = QLabel(f"last backup {relative_time(ts)}")
                last_lbl.setStyleSheet(f"font-size:10px; color:{C['textDim']};")
                rl.addWidget(last_lbl)

            backup_btn = btn_ghost("Backup now", small=True)
            backup_btn.clicked.connect(lambda _, g=game: self._backup_now(g))
            rl.addWidget(backup_btn)

            self._proc_layout.addWidget(row)

            if idx < len(watched) - 1:
                div = QFrame()
                div.setFixedHeight(1)
                div.setStyleSheet("background: rgba(255,255,255,0.05);")
                self._proc_layout.addWidget(div)

    def _backup_now(self, game):
        dlg = BackupDialog(game, self)
        dlg.exec()

    def _toggle(self):
        if self._running:
            self._stop_watcher()
        else:
            self._start_watcher()

    def _start_watcher(self):
        games = CFG.get("games", [])
        watched = [g for g in games if g.get("exe_name")]
        if not watched:
            show_toast("No games with exe configured.", "warning", self._main_win)
            return
        self._watcher = ss.GameWatcher(watched)
        self._watcher.start()
        threading.Thread(target=ss._watcher_check_manifest_update, daemon=True).start()
        self._running = True
        self._start_time = time.time()
        self._radar.set_running(True)
        self._toggle_btn.setText("Stop Watcher")
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background:rgba(240,80,96,0.12); color:{C['error']};"
            f" border:1px solid rgba(240,80,96,0.3); border-radius:8px; padding:6px 12px; font-size:12px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.2); }}"
        )
        self._status_title.setText("Watcher is running")
        self._status_sub.setText(f"Monitoring {len(watched)} process(es)")
        self._stats_widget.show()
        self._stat_watching[1].setText(str(len(watched)))
        pass  # hero no longer a card frame
        self._main_win.sidebar.set_watcher(True)
        self._log_entry("Watcher started")
        show_toast("Watcher started", "success", self._main_win)

    def _stop_watcher(self):
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        self._running = False
        self._radar.set_running(False)
        self._toggle_btn.setText("Start Watcher")
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background:{C['cardH']}; color:{C['textMid']};"
            f" border:1px solid {C['border']}; border-radius:8px; padding:6px 12px; font-size:12px; }}"
            f"QPushButton:hover {{ background:{C['border']}; }}"
        )
        self._status_title.setText("Watcher is stopped")
        self._status_sub.setText("Start the watcher to enable automatic backups")
        self._stats_widget.hide()
        self._main_win.sidebar.set_watcher(False)
        self._log_entry("Watcher stopped")
        show_toast("Watcher stopped", "info", self._main_win)

    def _tick(self):
        if self._running and self._start_time:
            elapsed = int(time.time() - self._start_time)
            m, s = divmod(elapsed, 60)
            self._uptime_lbl.setText(f"Uptime: {m}m {s}s")
            if self._watcher:
                active = len(self._watcher.running_pids)
                self._stat_active[1].setText(str(active))
        elif not self._running:
            self._uptime_lbl.setText("")

    def _log_entry(self, msg):
        t = time.strftime("%H:%M:%S")
        self._log.append(
            f"<span style='color:{C['textDim']}'>[{t}]</span>"
            f" <span style='color:{C['textMid']}'>{msg}</span>"
        )

    def _health_check(self):
        dlg = HealthCheckDialog(self._main_win)
        dlg.exec()

    def _add_to_startup(self):
        dlg = StartupTaskDialog(self._main_win)
        dlg.exec()

    def refresh(self):
        self._rebuild_proc_list()


class _ConfirmDialog(QDialog):
    def __init__(self, title, body, confirm_text="Confirm", danger=False, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(380)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet(f"font-size:14px; font-weight:700; color:{C['text']}; background:transparent; border:none;")
        hdr.addWidget(t)
        hdr.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(26, 26)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:13px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(12)

        msg = QLabel(body)
        msg.setWordWrap(True)
        msg.setStyleSheet(f"font-size:13px; color:{C['textMid']}; background:transparent; border:none;")
        root.addWidget(msg)
        root.addSpacing(20)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(
            f"QPushButton {{ background:{C['bg2']}; color:{C['text']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:7px 18px; font-size:13px; }}"
            f"QPushButton:hover {{ border-color:{C['accent']}; }}"
        )
        cancel.clicked.connect(self.reject)
        foot.addWidget(cancel)
        foot.addStretch()
        if danger:
            ok_style = (
                f"QPushButton {{ background:rgba(240,80,96,0.15); color:{C['error']};"
                f" border:1px solid rgba(240,80,96,0.4); border-radius:8px; padding:7px 18px;"
                f" font-size:13px; font-weight:600; }}"
                f"QPushButton:hover {{ background:rgba(240,80,96,0.28); border-color:{C['error']}; }}"
            )
        else:
            ok_style = (
                f"QPushButton {{ background:{C['accent']}; color:#fff; border:none;"
                f" border-radius:8px; padding:7px 18px; font-size:13px; font-weight:600; }}"
                f"QPushButton:hover {{ background:{C['accentD']}; }}"
            )
        ok = QPushButton(confirm_text)
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(ok_style)
        ok.clicked.connect(self.accept)
        foot.addWidget(ok)
        root.addLayout(foot)

        install_enter_to_advance(self, self.accept)


# ── StartupTaskDialog ─────────────────────────────────────────────────────────
class DriveImportDialog(QDialog):
    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(420)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
            f" QLabel {{ color:{C['text']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        title = QLabel("Import from Drive")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(6)

        sub = QLabel(f"{len(names)} new game(s) found. Select which to import:")
        sub.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        sub.setWordWrap(True)
        root.addWidget(sub)
        root.addSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(260)
        scroll.setStyleSheet("background:transparent;")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        inner_l = QVBoxLayout(inner)
        inner_l.setContentsMargins(0, 0, 0, 0)
        inner_l.setSpacing(4)

        self._checkboxes = []
        for name in names:
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.setStyleSheet(
                f"QCheckBox {{ color:{C['text']}; font-size:13px; padding:6px 8px;"
                f" background:{C['bg2']}; border:1px solid {C['border']}; border-radius:6px; }}"
                f"QCheckBox::indicator {{ width:16px; height:16px; }}"
                f"QCheckBox:hover {{ border-color:{C['accent']}; }}"
            )
            inner_l.addWidget(cb)
            self._checkboxes.append((name, cb))

        inner_l.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)
        root.addSpacing(18)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(
            f"QPushButton {{ background:{C['bg2']}; color:{C['text']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:8px 20px; font-size:13px; }}"
            f"QPushButton:hover {{ border-color:{C['accent']}; }}"
        )
        cancel.clicked.connect(self.reject)
        foot.addWidget(cancel)
        foot.addStretch()
        add = QPushButton("Add Selected")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.setStyleSheet(
            f"QPushButton {{ background:{C['accent']}; color:#fff; border:none;"
            f" border-radius:8px; padding:8px 20px; font-size:13px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C['accentD']}; }}"
        )
        add.clicked.connect(self.accept)
        foot.addWidget(add)
        root.addLayout(foot)

        install_enter_to_advance(self, self.accept)

    def selected_names(self):
        return [name for name, cb in self._checkboxes if cb.isChecked()]


class StartupTaskDialog(QDialog):
    _TASK = "SaveSyncWatcher"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(520)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
            f" QLabel {{ color:{C['text']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Watcher Startup Task")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(20)

        # Status chip
        self._status_lbl = QLabel()
        self._status_lbl.setFixedHeight(32)
        self._status_lbl.setContentsMargins(12, 0, 12, 0)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self._status_lbl)
        root.addSpacing(20)

        # Explanation box — what this does
        info = QFrame()
        info.setStyleSheet(
            f"QFrame {{ background:rgba(124,111,255,0.07); border:none; border-radius:10px; }}"
        )
        info_l = QVBoxLayout(info)
        info_l.setContentsMargins(16, 14, 16, 14)
        info_l.setSpacing(10)

        def _row(heading, body):
            w = QWidget()
            w.setStyleSheet("background:transparent;")
            col = QVBoxLayout(w)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(3)
            h = QLabel(heading)
            h.setStyleSheet(f"font-size:12px; font-weight:600; color:{C['text']}; background:transparent;")
            b = QLabel(body)
            b.setStyleSheet(f"font-size:11px; color:{C['textMid']}; background:transparent;")
            b.setWordWrap(True)
            col.addWidget(h)
            col.addWidget(b)
            return w

        info_l.addWidget(_row(
            "What this does",
            "Registers a Windows Task Scheduler task (SaveSyncWatcher) that runs the "
            "watcher silently in the background every time you log into Windows — "
            "no GUI, no terminal window, fully automatic."
        ))

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background:rgba(255,255,255,0.06);")
        info_l.addWidget(div)

        info_l.addWidget(_row(
            "How it differs from \"Start with Windows\" in Settings",
            "Settings → Start with Windows launches the full SaveSync GUI minimised to "
            "the system tray. This task starts only the lightweight background watcher "
            "(savesync.py --watch) — no interface, lower resource use. "
            "You can use both together or either independently."
        ))
        root.addWidget(info)
        root.addSpacing(20)

        # Action buttons
        self._install_btn = btn_primary("Install Startup Task")
        self._install_btn.clicked.connect(self._install)
        self._remove_btn = btn_ghost("Remove Task", small=False)
        self._remove_btn.clicked.connect(self._remove)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(self._install_btn, 1)
        btn_row.addWidget(self._remove_btn)
        root.addLayout(btn_row)

        self._refresh_status()

        def _on_enter():
            # Run the primary action — install if visible, otherwise remove.
            if self._install_btn.isVisible() and self._install_btn.isEnabled():
                self._install()
            elif self._remove_btn.isVisible() and self._remove_btn.isEnabled():
                self._remove()
        install_enter_to_advance(self, _on_enter)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _task_installed(self):
        import subprocess
        r = subprocess.run(
            ["schtasks", "/query", "/tn", self._TASK],
            capture_output=True
        )
        return r.returncode == 0

    def _refresh_status(self):
        installed = self._task_installed()
        if installed:
            self._status_lbl.setText("● Task installed — watcher starts automatically on login")
            self._status_lbl.setStyleSheet(
                f"font-size:11px; font-weight:500; color:{C['success']};"
                f" background:rgba(61,214,140,0.08); border:none; border-radius:6px;"
            )
            self._install_btn.setText("Reinstall / Update Task")
            self._remove_btn.setVisible(True)
        else:
            self._status_lbl.setText("○ Not installed — watcher must be started manually")
            self._status_lbl.setStyleSheet(
                f"font-size:11px; font-weight:500; color:{C['textMid']};"
                f" background:rgba(255,255,255,0.04); border:none; border-radius:6px;"
            )
            self._install_btn.setText("Install Startup Task")
            self._remove_btn.setVisible(False)

    def _install(self):
        import subprocess, platform
        if platform.system() != "Windows":
            QMessageBox.warning(self, "Not supported", "Task Scheduler is only available on Windows.")
            return

        # When running as a PyInstaller EXE, schedule the EXE itself.
        # Otherwise fall back to pythonw.exe + the script path.
        if getattr(sys, "frozen", False):
            exe_path = Path(sys.executable)
            tr = f'"{exe_path}" --minimized'
        else:
            py_path = Path(sys.executable)
            pythonw = py_path.parent / "pythonw.exe"
            if not pythonw.exists():
                pythonw = py_path
            script_path = Path(ss.__file__).resolve()
            tr = f'"{pythonw}" "{script_path}" --watch'

        # Remove existing first (ignore errors)
        subprocess.run(["schtasks", "/delete", "/tn", self._TASK, "/f"], capture_output=True)

        cmd = [
            "schtasks", "/create",
            "/tn", self._TASK,
            "/tr", tr,
            "/sc", "ONLOGON",
            "/rl", "HIGHEST",
            "/f",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            show_toast("Startup task installed.", "success", self.parent())
        else:
            err = result.stderr.strip() or result.stdout.strip()
            QMessageBox.critical(self, "Failed", f"Could not install task:\n{err}\n\nTry running SaveSync as Administrator.")
        self._refresh_status()

    def _remove(self):
        import subprocess
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", self._TASK, "/f"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            show_toast("Startup task removed.", "info", self.parent())
        else:
            err = result.stderr.strip() or result.stdout.strip()
            QMessageBox.critical(self, "Failed", f"Could not remove task:\n{err}")
        self._refresh_status()


# ── HealthCheckDialog ─────────────────────────────────────────────────────────
class HealthCheckDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Health Check")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(600)
        self.setMinimumHeight(420)
        self.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
        )
        self._results = []
        self._timer = None
        self._fix_workers = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        # header
        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Health Check")
        title.setStyleSheet(f"font-size:16px; font-weight:700; color:{C['text']}; background:transparent; border:none;")
        title_col.addWidget(title)
        sub = QLabel("Verify save paths, Drive folders, and sync timestamps")
        sub.setStyleSheet(f"font-size:11px; color:{C['textDim']}; background:transparent; border:none;")
        title_col.addWidget(sub)
        hdr.addLayout(title_col)
        hdr.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:14px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(20)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # ── page 0: idle ─────────────────────────────────────────────────────
        idle_w = QWidget()
        idle_w.setStyleSheet("background:transparent;")
        idle_l = QVBoxLayout(idle_w)
        idle_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idle_l.setSpacing(12)
        icon_lbl = QLabel("🔍")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size:36px; background:transparent; border:none;")
        idle_l.addWidget(icon_lbl)
        games = CFG.get("games", [])
        desc = QLabel(f"Scans all {len(games)} game(s) — checks save paths, Drive folders, exe names and sync timestamps.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size:13px; color:{C['textMid']}; background:transparent; border:none;")
        idle_l.addWidget(desc)
        idle_l.addSpacing(8)
        run_btn = btn_primary("Run Health Check")
        run_btn.clicked.connect(self._run_check)
        idle_l.addWidget(run_btn, 0, Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(idle_w)

        # ── page 1: scanning ─────────────────────────────────────────────────
        scan_w = QWidget()
        scan_w.setStyleSheet("background:transparent;")
        scan_l = QVBoxLayout(scan_w)
        scan_l.setSpacing(10)
        self._scan_label = QLabel("Scanning…")
        self._scan_label.setStyleSheet(f"font-size:12px; color:{C['textMid']}; background:transparent; border:none;")
        scan_l.addWidget(self._scan_label)
        self._scan_prog = QProgressBar()
        self._scan_prog.setRange(0, 100)
        scan_l.addWidget(self._scan_prog)
        self._stack.addWidget(scan_w)

        # ── page 2: results ───────────────────────────────────────────────────
        done_w = QWidget()
        done_w.setStyleSheet("background:transparent;")
        done_l = QVBoxLayout(done_w)
        done_l.setSpacing(10)

        # summary bar
        self._summary_box = QFrame()
        self._summary_box.setObjectName("hcSummary")
        sum_l = QHBoxLayout(self._summary_box)
        sum_l.setContentsMargins(16, 12, 16, 12)
        sum_l.setSpacing(12)
        self._sum_icon = QLabel("✓")
        self._sum_icon.setStyleSheet(f"font-size:20px; color:{C['success']}; background:transparent; border:none;")
        sum_l.addWidget(self._sum_icon)
        sum_text = QVBoxLayout()
        sum_text.setSpacing(2)
        self._sum_title = QLabel("All games healthy")
        self._sum_title.setStyleSheet(f"font-size:13px; font-weight:600; color:{C['text']}; background:transparent; border:none;")
        self._sum_sub = QLabel("")
        self._sum_sub.setStyleSheet(f"font-size:11px; color:{C['textMid']}; background:transparent; border:none;")
        sum_text.addWidget(self._sum_title)
        sum_text.addWidget(self._sum_sub)
        sum_l.addLayout(sum_text, 1)
        rescan_btn = QPushButton("Re-scan")
        rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rescan_btn.setStyleSheet(
            f"QPushButton {{ background:{C['cardH']}; color:{C['textMid']}; border:1px solid {C['border']};"
            f" border-radius:7px; padding:5px 12px; font-size:12px; }}"
            f"QPushButton:hover {{ background:{C['border']}; }}"
        )
        rescan_btn.clicked.connect(self._run_check)
        sum_l.addWidget(rescan_btn)
        done_l.addWidget(self._summary_box)

        # results list
        self._results_inner = QWidget()
        self._results_inner.setStyleSheet("background:transparent;")
        self._results_l = QVBoxLayout(self._results_inner)
        self._results_l.setContentsMargins(0, 0, 0, 0)
        self._results_l.setSpacing(6)
        res_scroll = QScrollArea()
        res_scroll.setWidgetResizable(True)
        res_scroll.setFrameShape(QFrame.Shape.NoFrame)
        res_scroll.setStyleSheet("background:transparent;")
        res_scroll.setWidget(self._results_inner)
        res_scroll.setMaximumHeight(300)
        done_l.addWidget(res_scroll)

        foot = QHBoxLayout()
        foot.addStretch()
        close_btn = btn_primary("Close")
        close_btn.clicked.connect(self.accept)
        foot.addWidget(close_btn)
        done_l.addLayout(foot)
        self._stack.addWidget(done_w)

        def _on_enter():
            idx = self._stack.currentIndex()
            if idx == 0:           # idle → run
                self._run_check()
            elif idx == 2:         # results → close
                self.accept()
        install_enter_to_advance(self, _on_enter)

    # ── scan ──────────────────────────────────────────────────────────────────
    def _run_check(self):
        self._results = []
        self._stack.setCurrentIndex(1)
        games = CFG.get("games", [])
        self._games_to_check = list(games)
        self._check_idx = 0
        self._scan_prog.setValue(0)
        if self._timer:
            self._timer.stop()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_next)
        self._timer.start(250)

    def _check_next(self):
        games = self._games_to_check
        if self._check_idx >= len(games):
            self._timer.stop()
            self._finish()
            return
        g = games[self._check_idx]
        self._scan_label.setText(f"Scanning: {g.get('name', '')}")
        self._scan_prog.setValue(int((self._check_idx + 1) / len(games) * 100))

        save_path   = g.get("save_path", "")
        exe_name    = g.get("exe_name", "")
        drive_folder= g.get("drive_folder", "")
        ts          = g.get("backup_timestamp") or g.get("last_sync")

        save_path_ok  = bool(save_path) and Path(save_path).exists()
        exe_name_ok   = bool(exe_name)
        drive_set     = bool(drive_folder)
        sync_fresh    = False
        stale_days    = None
        if ts:
            try:
                dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                age = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
                sync_fresh = age < 7 * 86400
                stale_days = int(age / 86400)
            except Exception:
                pass

        issues = []
        if not save_path_ok:
            if not save_path:
                issues.append(("no_save_path", "No save path set", "Set a save path in the game editor."))
            else:
                issues.append(("bad_save_path", f"Save path not found: {save_path}", "The folder doesn't exist. Update the path or create it."))
        if not exe_name_ok:
            issues.append(("no_exe", "No exe name set", "Set the exe name so the watcher can detect when the game runs."))
        if not drive_set:
            issues.append(("no_drive", "No Drive folder configured", "Add a Google Drive folder in the game editor to enable cloud backup."))
        if ts and not sync_fresh:
            issues.append(("stale_sync", f"Last sync was {stale_days}d ago", "Run a manual backup or enable auto-sync."))

        self._results.append({
            "game":         g,
            "save_path_ok": save_path_ok,
            "exe_name_ok":  exe_name_ok,
            "drive_set":    drive_set,
            "sync_fresh":   sync_fresh,
            "ts":           ts,
            "issues":       issues,
        })
        self._check_idx += 1

    # ── results ───────────────────────────────────────────────────────────────
    def _finish(self):
        # clear old rows
        while self._results_l.count():
            item = self._results_l.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        total_issues = sum(len(r["issues"]) for r in self._results)
        ok_count     = sum(1 for r in self._results if not r["issues"])

        for r in self._results:
            self._results_l.addWidget(self._make_result_row(r))
        self._results_l.addStretch()

        # summary bar
        if total_issues == 0:
            self._sum_icon.setText("✓")
            self._sum_icon.setStyleSheet(f"font-size:20px; color:{C['success']}; background:transparent; border:none;")
            self._sum_title.setText("All games healthy")
            self._summary_box.setStyleSheet(
                f"QFrame#hcSummary {{ background:rgba(61,214,140,0.07); border:1px solid rgba(61,214,140,0.2); border-radius:10px; }}"
                f"QFrame#hcSummary QLabel {{ background:transparent; border:none; }}"
            )
        else:
            self._sum_icon.setText("⚠")
            self._sum_icon.setStyleSheet(f"font-size:20px; color:{C['warning']}; background:transparent; border:none;")
            self._sum_title.setText(f"{total_issues} issue{'s' if total_issues != 1 else ''} found")
            self._summary_box.setStyleSheet(
                f"QFrame#hcSummary {{ background:rgba(240,168,48,0.07); border:1px solid rgba(240,168,48,0.2); border-radius:10px; }}"
                f"QFrame#hcSummary QLabel {{ background:transparent; border:none; }}"
            )
        self._sum_sub.setText(f"{len(self._results)} game{'s' if len(self._results)!=1 else ''} scanned · {ok_count} OK")
        self._stack.setCurrentIndex(2)

    def _make_result_row(self, r):
        has_issue = bool(r["issues"])
        oid = f"hcRow{'Warn' if has_issue else 'Ok'}"
        row = QFrame()
        row.setObjectName(oid)
        if has_issue:
            row.setStyleSheet(
                f"QFrame#{oid} {{ background:rgba(240,168,48,0.05); border:1px solid rgba(240,168,48,0.2); border-radius:9px; }}"
                f"QFrame#{oid} QLabel {{ background:transparent; border:none; }}"
            )
        else:
            row.setStyleSheet(
                f"QFrame#{oid} {{ background:{C['bg2']}; border:1px solid {C['border']}; border-radius:9px; }}"
                f"QFrame#{oid} QLabel {{ background:transparent; border:none; }}"
            )

        rl = QVBoxLayout(row)
        rl.setContentsMargins(14, 10, 14, 10)
        rl.setSpacing(6)

        # top row: name + status indicators + fix btn
        top = QHBoxLayout()
        top.setSpacing(10)
        name_lbl = QLabel(r["game"].get("name", ""))
        name_lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{C['text']};")
        top.addWidget(name_lbl, 1)

        for label, ok in [
            ("Path", r["save_path_ok"]),
            ("Exe",  r["exe_name_ok"]),
            ("Drive",r["drive_set"]),
            ("Sync", r["sync_fresh"] if r["ts"] else None),
        ]:
            pill = QWidget()
            pill.setStyleSheet("background:transparent;")
            pl = QHBoxLayout(pill)
            pl.setContentsMargins(6, 3, 6, 3)
            pl.setSpacing(3)
            if ok is None:
                color = C['textDim']
                sym = "—"
            elif ok:
                color = C['success']
                sym = "✓"
            else:
                color = C['error']
                sym = "✗"
            sym_l = QLabel(sym)
            sym_l.setStyleSheet(f"font-size:11px; font-weight:700; color:{color};")
            lbl_l = QLabel(label)
            lbl_l.setStyleSheet(f"font-size:10px; color:{C['textDim']};")
            pl.addWidget(sym_l)
            pl.addWidget(lbl_l)
            pill.setStyleSheet(
                f"background:rgba(255,255,255,0.03); border:1px solid {C['border']}; border-radius:5px;"
            )
            top.addWidget(pill)

        if has_issue:
            fix_btn = QPushButton("Fix…")
            fix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            fix_btn.setStyleSheet(
                f"QPushButton {{ background:rgba(240,168,48,0.12); color:{C['warning']};"
                f" border:1px solid rgba(240,168,48,0.35); border-radius:7px; padding:4px 12px; font-size:12px; font-weight:600; }}"
                f"QPushButton:hover {{ background:rgba(240,168,48,0.22); border-color:rgba(240,168,48,0.6); }}"
            )
            fix_btn.clicked.connect(lambda _, res=r, btn=fix_btn: self._fix(res, btn))
            top.addWidget(fix_btn)
        else:
            ok_badge = QLabel("OK")
            ok_badge.setStyleSheet(
                f"color:{C['success']}; font-size:10px; font-weight:700;"
                f" background:rgba(61,214,140,0.1); border:1px solid rgba(61,214,140,0.25);"
                f" border-radius:5px; padding:3px 8px;"
            )
            top.addWidget(ok_badge)

        rl.addLayout(top)

        # issue detail lines
        for _, short, detail in r["issues"]:
            detail_lbl = QLabel(f"  · {short}: {detail}")
            detail_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
            detail_lbl.setWordWrap(True)
            rl.addWidget(detail_lbl)

        return row

    # ── fix ───────────────────────────────────────────────────────────────────
    def _fix(self, r, fix_btn):
        fix_btn.setEnabled(False)
        fix_btn.setText("Fixing…")
        game = r["game"]
        results_log = []

        def _do():
            for kind, short, _ in r["issues"]:
                if kind == "bad_save_path":
                    try:
                        Path(game["save_path"]).mkdir(parents=True, exist_ok=True)
                        results_log.append(("✓", f"Created folder: {game['save_path']}"))
                    except Exception as e:
                        results_log.append(("✗", f"Could not create folder: {e}"))

                elif kind == "no_save_path":
                    results_log.append(("—", "Save path not set — open the game editor to configure it."))

                elif kind == "no_exe":
                    results_log.append(("—", "Exe name not set — open the game editor to configure it."))

                elif kind == "no_drive":
                    results_log.append(("—", "Drive folder not set — open the game editor to configure it."))

                elif kind == "stale_sync":
                    if game.get("drive_folder"):
                        try:
                            svc = ss.get_drive_service()
                            ss.run_backup(game, "health_fix", True)
                            results_log.append(("✓", "Backup triggered successfully."))
                        except Exception as e:
                            results_log.append(("✗", f"Backup failed: {e}"))
                    else:
                        results_log.append(("—", "No Drive folder set — configure it first."))
            return results_log

        def _on_done(log):
            fix_btn.setEnabled(True)
            fix_btn.setText("Fix…")
            self._show_fix_result(game.get("name", ""), log)
            self._run_check()

        def _on_err(e):
            fix_btn.setEnabled(True)
            fix_btn.setText("Fix…")
            self._show_fix_result(game.get("name", ""), [("✗", f"Unexpected error: {e}")])

        w = Worker(_do)
        w.finished.connect(_on_done)
        w.error.connect(_on_err)
        self._fix_workers.append(w)
        w.start()

    def _show_fix_result(self, name, log):
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dlg.setFixedWidth(400)
        dlg.setStyleSheet(
            f"QDialog {{ background:{C['bg']}; border:1px solid {C['border']}; border-radius:12px; }}"
        )
        root = QVBoxLayout(dlg)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        t = QLabel(f"Fix result — {name}")
        t.setStyleSheet(f"font-size:14px; font-weight:700; color:{C['text']}; background:transparent; border:none;")
        hdr.addWidget(t, 1)
        x = QPushButton("✕")
        x.setFixedSize(26, 26)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['textDim']}; border:none; border-radius:6px; font-size:13px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.15); color:{C['error']}; }}"
        )
        x.clicked.connect(dlg.accept)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(14)

        all_ok = all(sym == "✓" for sym, _ in log)
        any_err = any(sym == "✗" for sym, _ in log)
        if all_ok:
            state_color, state_text = C['success'], "All fixes applied successfully."
        elif any_err:
            state_color, state_text = C['error'], "Some fixes could not be applied automatically."
        else:
            state_color, state_text = C['warning'], "Some issues require manual action."

        state_lbl = QLabel(state_text)
        state_lbl.setWordWrap(True)
        state_lbl.setStyleSheet(f"font-size:12px; color:{state_color}; background:transparent; border:none;")
        root.addWidget(state_lbl)
        root.addSpacing(12)

        for sym, msg in log:
            sym_color = C['success'] if sym == "✓" else (C['error'] if sym == "✗" else C['textDim'])
            line_w = QWidget()
            line_w.setStyleSheet(f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:6px;")
            line_l = QHBoxLayout(line_w)
            line_l.setContentsMargins(10, 7, 10, 7)
            line_l.setSpacing(8)
            sym_lbl = QLabel(sym)
            sym_lbl.setStyleSheet(f"font-size:12px; font-weight:700; color:{sym_color}; background:transparent; border:none;")
            sym_lbl.setFixedWidth(14)
            msg_lbl = QLabel(msg)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet(f"font-size:12px; color:{C['textMid']}; background:transparent; border:none;")
            line_l.addWidget(sym_lbl)
            line_l.addWidget(msg_lbl, 1)
            root.addWidget(line_w)
            root.addSpacing(4)

        root.addSpacing(8)
        ok_btn = btn_primary("OK")
        ok_btn.clicked.connect(dlg.accept)
        root.addWidget(ok_btn, 0, Qt.AlignmentFlag.AlignRight)
        dlg.exec()


# ── RestorePanel ──────────────────────────────────────────────────────────────
class RestorePanel(QWidget):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._main_win = main_win
        self._drive_folders = []   # [{name, id}, …] from last scan
        self._worker = None
        self._delete_worker = None
        self._restore_worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top bar ──────────────────────────────────────────────────────────
        topbar = QWidget()
        topbar.setStyleSheet(f"background:{C['bg']};")
        tb = QVBoxLayout(topbar)
        tb.setContentsMargins(24, 18, 24, 0)
        tb.setSpacing(4)

        tb_row = QHBoxLayout()
        tb_row.setSpacing(12)
        title = QLabel("Drive")
        title.setStyleSheet(f"font-size:17px; font-weight:700; letter-spacing:-0.3px; color:{C['text']};")
        tb_row.addWidget(title)
        tb_row.addStretch()
        self._scan_btn = _icon_btn_ghost("Scan Drive", "drive", small=True)
        self._scan_btn.clicked.connect(self._scan_drive)
        tb_row.addWidget(self._scan_btn)
        tb.addLayout(tb_row)

        self._scan_prog = QProgressBar()
        self._scan_prog.setRange(0, 0)  # indeterminate
        self._scan_prog.setFixedHeight(3)
        self._scan_prog.setTextVisible(False)
        self._scan_prog.setStyleSheet(
            f"QProgressBar {{ background:{C['border']}; border:none; border-radius:1px; }}"
            f"QProgressBar::chunk {{ background:{C['accent']}; border-radius:1px; }}"
        )
        self._scan_prog.hide()
        tb.addWidget(self._scan_prog)

        root.addWidget(topbar)

        # ── legend ───────────────────────────────────────────────────────────
        legend = QWidget()
        legend.setStyleSheet("background:transparent;")
        leg_l = QHBoxLayout(legend)
        leg_l.setContentsMargins(24, 10, 24, 0)
        leg_l.setSpacing(16)
        for dot, label in [
            (C['accent'],  "On Drive & local"),
            (C['warning'], "Drive only — not in local list"),
            (C['textDim'], "Local only — not on Drive"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(5)
            d = QLabel("●")
            d.setStyleSheet(f"color:{dot}; font-size:10px; background:transparent; border:none;")
            t = QLabel(label)
            t.setStyleSheet(f"color:{C['textDim']}; font-size:11px; background:transparent; border:none;")
            row.addWidget(d)
            row.addWidget(t)
            leg_l.addLayout(row)
        leg_l.addStretch()
        root.addWidget(legend)

        # ── scroll content ────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._inner = QWidget()
        self._inner.setStyleSheet(f"background:{C['bg']};")
        self._il = QVBoxLayout(self._inner)
        self._il.setContentsMargins(24, 16, 24, 24)
        self._il.setSpacing(8)

        self._placeholder = QLabel("Click  Scan Drive  to compare local games with Google Drive.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color:{C['textDim']}; font-size:13px; padding:40px 0;")
        self._il.addWidget(self._placeholder)
        self._il.addStretch()

        scroll.setWidget(self._inner)
        root.addWidget(scroll, 1)

    # ── scan ─────────────────────────────────────────────────────────────────
    def _scan_drive(self, silent=False):
        if not ss.GDRIVE_AVAILABLE:
            if not silent:
                show_toast("Google Drive not available.", "error", self._main_win)
            return
        if not self._scan_btn.isEnabled():
            return  # already scanning
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("Scanning…")
        self._scan_prog.show()
        self._clear_list()
        self._placeholder.setText("Scanning Google Drive…")
        self._placeholder.show()

        if DRIVE_SCAN_TRAP:
            _trap_log(f"\n--- Drive scan started {datetime.datetime.now()} ---")

        def _do():
            svc = ss.get_drive_service()
            return ss.list_drive_game_folders(svc)
        self._worker = Worker(_do)
        self._worker.finished.connect(self._on_scan)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    def _on_scan_error(self, e):
        if DRIVE_SCAN_TRAP:
            _trap_log(f"--- Drive scan ERROR: {e} ---")
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("Scan Drive")
        self._scan_prog.hide()
        self._placeholder.setText(f"Scan failed: {e}")
        show_toast(f"Drive scan error: {e}", "error", self._main_win)

    def _on_scan(self, folders):
        if DRIVE_SCAN_TRAP:
            _trap_log(f"--- Drive scan finished OK ({len(folders)} folders) ---")
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("Scan Drive")
        self._scan_prog.hide()
        self._drive_folders = folders
        self._rebuild()

    def _rebuild(self):
        self._clear_list()
        drive_names  = {f["name"]: f for f in self._drive_folders}
        local_names  = {g.get("name", "") for g in CFG.get("games", [])}

        both         = [f for f in self._drive_folders if f["name"] in local_names]
        drive_only   = [f for f in self._drive_folders if f["name"] not in local_names]
        local_only   = [g for g in CFG.get("games", []) if g.get("name","") not in drive_names]

        if not self._drive_folders and not local_only:
            self._placeholder.setText("No games found. Make sure SaveSync has uploaded at least one game.")
            self._placeholder.show()
            self._il.addStretch()
            return

        self._placeholder.hide()

        if drive_only:
            self._il.addWidget(self._section_header(
                f"Drive only  ({len(drive_only)})",
                "On Google Drive but not added to this machine.",
                C['warning'],
            ))
            for f in drive_only:
                self._il.addWidget(self._make_row(f, status="drive_only"))
            self._il.addSpacing(8)

        if both:
            self._il.addWidget(self._section_header(
                f"Synced  ({len(both)})",
                "Present on Drive and in your local game list.",
                C['accent'],
            ))
            for f in both:
                self._il.addWidget(self._make_row(f, status="both"))
            self._il.addSpacing(8)

        if local_only:
            self._il.addWidget(self._section_header(
                f"Local only  ({len(local_only)})",
                "In your local list but no Drive backup found.",
                C['textDim'],
            ))
            for g in local_only:
                self._il.addWidget(self._make_row({"name": g.get("name",""), "id": ""}, status="local_only"))

        self._il.addStretch()

    def _clear_list(self):
        placeholder_removed = False
        while self._il.count():
            item = self._il.takeAt(0)
            w = item.widget()
            if w is self._placeholder:
                placeholder_removed = True
            elif w:
                w.setParent(None)
        if placeholder_removed:
            self._il.addWidget(self._placeholder)

    # ── section header ────────────────────────────────────────────────────────
    def _section_header(self, title, subtitle, color):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 4, 0, 2)
        l.setSpacing(1)
        t = QLabel(title.upper())
        t.setStyleSheet(
            f"color:{color}; font-size:10px; font-weight:700; letter-spacing:1px;"
            f" background:transparent; border:none;"
        )
        s = QLabel(subtitle)
        s.setStyleSheet(f"color:{C['textDim']}; font-size:11px; background:transparent; border:none;")
        l.addWidget(t)
        l.addWidget(s)
        return w

    # ── row ───────────────────────────────────────────────────────────────────
    def _make_row(self, folder, status):
        # status: "drive_only" | "both" | "local_only"
        dot_color = {
            "drive_only": C['warning'],
            "both":       C['accent'],
            "local_only": C['textDim'],
        }[status]

        row = QFrame()
        row.setObjectName("restoreRow")
        row.setStyleSheet(
            f"QFrame#restoreRow {{ background:{C['card']}; border:1px solid {C['border']}; border-radius:10px; }}"
            f"QFrame#restoreRow QLabel {{ background:transparent; border:none; }}"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 11, 14, 11)
        rl.setSpacing(10)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{dot_color}; font-size:11px;")
        rl.addWidget(dot)

        name_lbl = QLabel(folder.get("name", ""))
        name_lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{C['text']};")
        rl.addWidget(name_lbl, 1)

        if status == "local_only":
            note = QLabel("No Drive backup")
            note.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
            rl.addWidget(note)
        else:
            # Delete from Drive
            del_btn = QPushButton("Delete")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(
                f"QPushButton {{ background:rgba(240,80,96,0.06); color:{C['error']};"
                f" border:1px solid rgba(240,80,96,0.25); border-radius:7px; padding:5px 10px; font-size:12px; }}"
                f"QPushButton:hover {{ background:rgba(240,80,96,0.18); border-color:rgba(240,80,96,0.6); }}"
            )
            del_btn.clicked.connect(lambda _, f=folder: self._delete_from_drive(f))
            rl.addWidget(del_btn)

            if status == "drive_only":
                add_btn = QPushButton("+ Add to list")
                add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                add_btn.setStyleSheet(
                    f"QPushButton {{ background:{C['accent']}; color:#fff; border:none;"
                    f" border-radius:7px; padding:5px 10px; font-size:12px; font-weight:600; }}"
                    f"QPushButton:hover {{ background:{C['accentD']}; }}"
                )
                add_btn.clicked.connect(lambda _, f=folder: self._add_from_drive(f))
                rl.addWidget(add_btn)

        return row

    # ── actions ───────────────────────────────────────────────────────────────
    def _restore(self, folder):
        name = folder.get("name", "")
        show_toast(f"Restoring {name}…", "info", self._main_win)
        def _do():
            svc = ss.get_drive_service()
            files = ss.list_drive_save_files(svc, folder["id"])
            for f in files[:3]:
                dest = ss.BASE_DIR / "restored" / name / f["name"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                ss.download_file_from_drive(svc, f["id"], dest)
            return True
        w = Worker(_do)
        w.finished.connect(lambda _: show_toast(f"{name} restored.", "success", self._main_win))
        w.error.connect(lambda e: show_toast(f"Restore error: {e}", "error", self._main_win))
        self._restore_worker = w
        w.start()

    def _add_from_drive(self, folder):
        name      = folder.get("name", "")
        folder_id = folder.get("id", "")
        show_toast(f"Reading config for {name}…", "info", self._main_win)

        def _fetch():
            svc       = ss.get_drive_service()
            drive_cfg = ss.fetch_game_config_from_drive(svc, folder_id) or {}
            return drive_cfg

        def _on_done(drive_cfg):
            game = {**ss.GAME_DEFAULTS, "name": name, "drive_folder": f"SaveSync/{name}", **drive_cfg}
            game["name"]         = name
            game["drive_folder"] = f"SaveSync/{name}"
            CFG.setdefault("games", []).append(game)
            ss.save_config(CFG)
            show_toast(f"{name} added to local list.", "success", self._main_win)
            self._rebuild()
            self._main_win._panel_games._rebuild_grid("")

        w = Worker(_fetch)
        w.finished.connect(_on_done)
        w.error.connect(lambda e: show_toast(f"Could not read Drive config: {e}", "error", self._main_win))
        self._add_worker = w
        w.start()

    def _delete_from_drive(self, folder):
        name = folder.get("name", "")
        folder_id = folder.get("id", "")
        if not folder_id:
            show_toast("No folder ID — cannot delete.", "error", self._main_win)
            return
        confirm = _ConfirmDialog(
            title="Delete from Drive",
            body=f"Permanently delete '{name}' from Google Drive?\n\nThis cannot be undone.",
            confirm_text="Delete",
            danger=True,
            parent=self._main_win,
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return
        show_toast(f"Deleting {name} from Drive…", "info", self._main_win)
        def _do():
            svc = ss.get_drive_service()
            svc.files().delete(fileId=folder_id).execute()
            return True
        def _on_done(_):
            show_toast(f"{name} deleted from Drive.", "success", self._main_win)
            self._drive_folders = [f for f in self._drive_folders if f["id"] != folder_id]
            self._rebuild()
        w = Worker(_do)
        w.finished.connect(_on_done)
        w.error.connect(lambda e: show_toast(f"Delete error: {e}", "error", self._main_win))
        self._delete_worker = w
        w.start()


# ── SettingsPanel ─────────────────────────────────────────────────────────────
class SettingsPanel(QWidget):
    _sig_db_status_refresh = pyqtSignal()

    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._main_win = main_win
        self._sig_db_status_refresh.connect(self._refresh_db_status)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        topbar = QWidget()
        topbar.setStyleSheet(f"background:{C['bg']};")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(24, 18, 24, 0)
        title = QLabel("Settings")
        title.setStyleSheet(f"font-size:17px; font-weight:700; letter-spacing:-0.3px;")
        tb.addWidget(title)
        root.addWidget(topbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C['bg']};")
        il = QVBoxLayout(inner)
        il.setContentsMargins(32, 8, 32, 40)
        il.setSpacing(0)

        # Google Drive section
        il.addWidget(section_title("Google Drive"))
        drive_group = QWidget()
        drive_group.setStyleSheet("background: transparent;")
        dcl = QVBoxLayout(drive_group)
        dcl.setContentsMargins(0, 0, 0, 0)
        dcl.setSpacing(0)

        # Account row
        self._drive_connected = False
        self._drive_btn = btn_primary("Connect Drive", small=True)
        self._drive_btn.clicked.connect(self._toggle_drive)
        self._drive_acct_lbl = QLabel("Not connected")
        self._drive_acct_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        self._drive_err_lbl = QLabel("")
        self._drive_err_lbl.setStyleSheet(f"font-size:11px; color:{C['error']};")
        self._drive_err_lbl.setWordWrap(True)
        self._drive_err_lbl.hide()
        row = QWidget(); row.setStyleSheet("background:transparent;")
        rl = QHBoxLayout(row); rl.setContentsMargins(0,13,0,13); rl.setSpacing(12)
        txt_col = QVBoxLayout(); txt_col.setSpacing(3)
        lbl = QLabel("Account"); lbl.setStyleSheet(f"font-size:13px; color:{C['text']}; font-weight:500;")
        txt_col.addWidget(lbl); txt_col.addWidget(self._drive_acct_lbl)
        txt_col.addWidget(self._drive_err_lbl)
        rl.addLayout(txt_col, 1); rl.addWidget(self._drive_btn)
        dcl.addWidget(row)
        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['border']};")
        dcl.addWidget(sep)
        # Check existing token on load
        if ss.GDRIVE_AVAILABLE and ss.TOKEN_FILE.exists():
            QTimer.singleShot(0, self._check_existing_token)

        drive_folder_edit = QLineEdit(CFG.get("drive_root_folder", "SaveSync"))
        drive_folder_edit.setFixedWidth(160)
        drive_folder_edit.setStyleSheet(
            f"QLineEdit {{ background:{C['bg2']}; border:1px solid {C['border']}; border-radius:7px;"
            f" padding:5px 8px; font-size:12px; font-family:'Inter','Segoe UI',sans-serif; }}"
        )
        drive_folder_edit.textChanged.connect(
            lambda t: CFG.update({"drive_root_folder": t})
        )
        info_btn = QToolButton()
        info_btn.setText("i")
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        info_btn.setFixedSize(18, 18)
        info_btn.setStyleSheet(
            f"QToolButton {{ background:transparent; border:1px solid {C['textDim']};"
            f" border-radius:9px; color:{C['textDim']}; font-size:10px; font-weight:700; }}"
            f"QToolButton:hover {{ border-color:{C['accent']}; color:{C['accent']}; }}"
        )
        _root_info_text = (
            "All backups are stored inside this folder on your Google Drive.\n"
            "Each game gets its own subfolder: <Root folder> / <Game name>.\n"
            "Changing this will not move existing backups."
        )
        info_btn.clicked.connect(lambda: QToolTip.showText(
            info_btn.mapToGlobal(info_btn.rect().bottomLeft()), _root_info_text, info_btn
        ))
        folder_row_widget = QWidget()
        folder_row_widget.setStyleSheet("background:transparent;")
        folder_row_hl = QHBoxLayout(folder_row_widget)
        folder_row_hl.setContentsMargins(0, 0, 0, 0)
        folder_row_hl.setSpacing(6)
        folder_row_hl.addWidget(info_btn)
        folder_row_hl.addWidget(drive_folder_edit)
        self._add_row(dcl, "Root folder", "All backups stored under this folder", folder_row_widget, last=True)
        il.addWidget(drive_group)

        # Notifications section
        il.addWidget(section_title("Notifications"))
        notif_group = QWidget()
        notif_group.setStyleSheet("background: transparent;")
        ncl = QVBoxLayout(notif_group)
        ncl.setContentsMargins(0, 0, 0, 0)
        ncl.setSpacing(0)
        notif_items = [
            ("Backup complete",      "notif_backup",  "Toast when a backup finishes"),
            ("Sync events",          "notif_sync",    "Toast when Drive sync runs"),
            ("Startup health check", "notif_health",  "Notification on Windows login"),
        ]
        for i, (label, key, sub) in enumerate(notif_items):
            toggle = self._toggle_switch(CFG.get(key, True))
            toggle.toggled.connect(lambda v, k=key: CFG.update({k: v}))
            self._add_row(ncl, label, sub, toggle, last=(i == len(notif_items) - 1))
        il.addWidget(notif_group)

        # Startup section
        il.addWidget(section_title("Startup"))
        startup_group = QWidget()
        startup_group.setStyleSheet("background: transparent;")
        scl = QVBoxLayout(startup_group)
        scl.setContentsMargins(0, 0, 0, 0)
        scl.setSpacing(0)
        _vbs_path = Path(os.environ.get("APPDATA","")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "SaveSync.vbs"

        def _vbs_active():
            return _vbs_path.exists()

        def _write_vbs():
            if getattr(sys, "frozen", False):
                target = str(Path(sys.executable))
                run_line = f'objShell.Run """{target}""" & " --minimized", 0, False'
            else:
                target = str(Path(sys.executable))
                script = str(Path(__file__).resolve())
                run_line = f'objShell.Run """{target}""" & " ""{script}"" --minimized", 0, False'
            vbs = (
                'Set objShell = CreateObject("WScript.Shell")\r\n'
                + run_line + "\r\n"
            )
            _vbs_path.write_text(vbs, encoding="utf-8")

        def _delete_vbs():
            if _vbs_path.exists():
                _vbs_path.unlink()

        # status indicator label
        self._startup_status_lbl = QLabel()
        self._startup_status_lbl.setStyleSheet(
            f"font-size:10px; font-weight:600; padding:2px 8px; border-radius:5px; border:none;"
        )

        def _refresh_startup_status():
            if _vbs_active():
                self._startup_status_lbl.setText("● Active")
                self._startup_status_lbl.setStyleSheet(
                    f"font-size:10px; font-weight:600; padding:2px 8px; border-radius:5px;"
                    f" background:rgba(61,214,140,0.12); color:{C['success']}; border:none;"
                )
                self._startup_status_lbl.setToolTip(str(_vbs_path))
            else:
                self._startup_status_lbl.setText("○ Inactive")
                self._startup_status_lbl.setStyleSheet(
                    f"font-size:10px; font-weight:600; padding:2px 8px; border-radius:5px;"
                    f" background:rgba(255,255,255,0.04); color:{C['textDim']}; border:none;"
                )
                self._startup_status_lbl.setToolTip("")

        _refresh_startup_status()

        startup_toggle = self._toggle_switch(_vbs_active())

        def _on_startup_toggle(enabled):
            CFG.update({"start_with_windows": enabled})
            try:
                if enabled:
                    _write_vbs()
                    show_toast("SaveSync added to Windows startup.", "success", self._main_win)
                else:
                    _delete_vbs()
                    show_toast("Removed from Windows startup.", "info", self._main_win)
            except Exception as exc:
                show_toast(f"Startup error: {exc}", "error", self._main_win)
            _refresh_startup_status()

        startup_toggle.toggled.connect(_on_startup_toggle)

        toggle_with_status = QWidget()
        toggle_with_status.setStyleSheet("background:transparent;")
        tws_hl = QHBoxLayout(toggle_with_status)
        tws_hl.setContentsMargins(0, 0, 0, 0)
        tws_hl.setSpacing(10)
        tws_hl.addWidget(self._startup_status_lbl)
        tws_hl.addWidget(startup_toggle)

        self._add_row(scl, "Start with Windows", "Launches minimized to tray", toggle_with_status, last=True)
        il.addWidget(startup_group)

        # Ludusavi Database section
        il.addWidget(section_title_with_info(
            "Ludusavi Database",
            "The Ludusavi database is a community-maintained list of save-file "
            "locations for thousands of PC games (the same data used by the "
            "Ludusavi backup tool). SaveSync downloads it from GitHub and uses "
            "it to auto-suggest save paths when you add a new game, so you "
            "rarely have to hunt them down yourself."
        ))
        db_group = QWidget()
        db_group.setStyleSheet("background: transparent;")
        dbl = QVBoxLayout(db_group)
        dbl.setContentsMargins(0, 0, 0, 0)
        dbl.setSpacing(10)

        # Status (left) + action buttons (right) on a single row.
        db_info_row = QHBoxLayout()
        db_info_row.setSpacing(12)
        self._db_status_lbl = QLabel()
        self._db_status_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._db_status_lbl.setStyleSheet(f"color:{C['textMid']}; font-size:12px;")
        self._db_status_lbl.setWordWrap(True)
        self._db_status_lbl.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        db_info_row.addWidget(self._db_status_lbl, 1)
        update_btn = btn_ghost("Download / Update", small=True)
        update_btn.clicked.connect(self._update_db)
        db_info_row.addWidget(update_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        rebuild_btn = btn_ghost("Rebuild Index", small=True)
        rebuild_btn.clicked.connect(self._rebuild_index)
        db_info_row.addWidget(rebuild_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        dbl.addLayout(db_info_row)

        self._refresh_db_status()
        # Kick off a background remote-version check (no-op if already done today).
        self._kick_db_update_check()

        # Search
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._db_search = QLineEdit()
        self._db_search.setPlaceholderText("Search save location database…")
        search_row.addWidget(self._db_search, 1)
        search_exec = btn_ghost("Search", small=True)
        search_exec.clicked.connect(self._db_search_exec)
        search_row.addWidget(search_exec)
        dbl.addLayout(search_row)

        il.addWidget(db_group)

        # Reset / Danger zone
        il.addWidget(section_title("Reset"))
        danger_row = QHBoxLayout()
        danger_row.setSpacing(8)
        clear_config_btn = btn_danger("Clear Config", small=True)
        clear_config_btn.clicked.connect(self._clear_config)
        danger_row.addWidget(clear_config_btn)
        clear_cache_btn = btn_danger("Clear Thumbnail Cache", small=True)
        clear_cache_btn.clicked.connect(self._clear_thumb_cache)
        danger_row.addWidget(clear_cache_btn)
        danger_row.addStretch()
        il.addLayout(danger_row)

        il.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def _add_row(self, layout, label, sub, widget, last=False):
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 13, 0, 13)
        rl.setSpacing(12)
        txt_col = QVBoxLayout()
        txt_col.setSpacing(3)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size:13px; color:{C['text']}; font-weight:500;")
        txt_col.addWidget(lbl)
        if isinstance(sub, str):
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
            txt_col.addWidget(sub_lbl)
        rl.addLayout(txt_col, 1)
        rl.addWidget(widget)
        layout.addWidget(row)
        if not last:
            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet(f"background:rgba(255,255,255,0.05);")
            layout.addWidget(div)

    def _toggle_switch(self, checked):
        from PyQt6.QtWidgets import QAbstractButton
        class ToggleSwitch(QAbstractButton):
            def __init__(self, checked=False, parent=None):
                super().__init__(parent)
                self.setCheckable(True)
                self.setChecked(checked)
                self.setFixedSize(36, 20)
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            def paintEvent(self, e):
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                on = self.isChecked()
                bg = QColor(C['accent']) if on else QColor(C['border'])
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(bg)
                p.drawRoundedRect(0, 0, 36, 20, 10, 10)
                p.setBrush(QColor("#ffffff"))
                x = 18 if on else 3
                p.drawEllipse(QRectF(x, 3, 14, 14))
        sw = ToggleSwitch(checked)
        return sw

    def _get_drive_email(self):
        """Return account email. Reads cached value from token file first, then network."""
        import json as _json
        # Check for previously cached email in token file
        try:
            raw = _json.loads(ss.TOKEN_FILE.read_text(encoding="utf-8"))
            cached = raw.get("email")
            if cached:
                return cached
        except Exception:
            raw = {}

        # Fetch from userinfo endpoint, refreshing token if needed
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            import urllib.request
            creds = Credentials.from_authorized_user_file(str(ss.TOKEN_FILE), ss.SCOPES)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            req = urllib.request.Request(
                "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
                headers={"Authorization": f"Bearer {creds.token}"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = _json.loads(r.read())
            email = data.get("email") or data.get("name")
            if email:
                try:
                    raw2 = _json.loads(ss.TOKEN_FILE.read_text(encoding="utf-8"))
                    raw2["email"] = email
                    ss.TOKEN_FILE.write_text(_json.dumps(raw2), encoding="utf-8")
                except Exception:
                    pass
            return email
        except Exception as _e:
            return None

    def _check_existing_token(self):
        def _do():
            try:
                ss.get_drive_service()
            except Exception:
                pass
            return self._get_drive_email()
        w = Worker(_do)
        w.finished.connect(lambda email: self._on_drive_connected(email, silent=True))
        w.error.connect(lambda _: self._on_drive_connected(None, silent=True))
        self._drive_worker = w
        w.start()

    def _toggle_drive(self):
        if not ss.GDRIVE_AVAILABLE:
            show_toast("Install google-api-python-client to use Drive.", "error", self._main_win)
            return
        if self._drive_connected:
            # Disconnect — delete token
            if ss.TOKEN_FILE.exists():
                ss.TOKEN_FILE.unlink()
            self._drive_connected = False
            self._drive_btn.setText("Connect Drive")
            self._drive_acct_lbl.setText("Not connected")
            self._drive_acct_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
            self._drive_err_lbl.hide()
            self._drive_err_lbl.setText("")
            show_toast("Drive disconnected.", "info", self._main_win)
        else:
            # Clear any previous error and start a fresh attempt.
            self._drive_err_lbl.hide()
            self._drive_err_lbl.setText("")
            self._drive_acct_lbl.setText("Opening browser for Google sign-in…")
            self._drive_acct_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
            self._drive_btn.setEnabled(False)
            self._drive_btn.setText("Connecting…")
            def _do():
                svc = ss.get_drive_service()
                email = self._get_drive_email()
                return email
            w = Worker(_do)
            w.finished.connect(lambda email: self._on_drive_connected(email))
            w.error.connect(self._on_drive_error)
            self._drive_worker = w
            w.start()

    def _on_drive_connected(self, email, silent=False):
        self._drive_connected = True
        self._drive_btn.setEnabled(True)
        self._drive_btn.setText("Disconnect")
        self._drive_err_lbl.hide()
        self._drive_err_lbl.setText("")
        if email:
            self._drive_acct_lbl.setText(email)
            self._drive_acct_lbl.setStyleSheet(f"font-size:11px; color:{C['success']};")
            if not silent:
                show_toast(f"Google Drive connected: {email}", "success", self._main_win)
        else:
            self._drive_acct_lbl.setText("Connected")
            self._drive_acct_lbl.setStyleSheet(f"font-size:11px; color:{C['success']};")
            if not silent:
                show_toast("Google Drive connected", "success", self._main_win)

    def _on_drive_error(self, e):
        self._drive_connected = False
        self._drive_btn.setEnabled(True)
        self._drive_btn.setText("Retry Connect")
        self._drive_acct_lbl.setText("Not connected")
        self._drive_acct_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")

        msg = str(e) or "unknown error"
        low = msg.lower()
        if any(k in low for k in ("access_denied", "denied", "cancel", "user closed",
                                  "consent", "user did not")):
            friendly = "Sign-in was cancelled or denied. Click Retry to try again."
        elif any(k in low for k in ("timeout", "timed out")):
            friendly = "Sign-in timed out before completing. Click Retry to try again."
        elif "credentials" in low and "json" in low:
            friendly = "gdrive_credentials.json is missing or invalid."
        elif any(k in low for k in ("network", "connection", "resolve", "dns",
                                    "unreachable", "ssl")):
            friendly = f"Network error during sign-in: {msg}"
        else:
            friendly = f"Sign-in failed: {msg}"

        self._drive_err_lbl.setText(friendly)
        self._drive_err_lbl.show()
        show_toast(friendly, "error", self._main_win)

    def _refresh_db_status(self):
        st = ss.manifest_db_status()
        if not st["downloaded"]:
            line1 = f"<b>Database:</b> <span style='color:{C['warning']};'>not downloaded</span>"
        else:
            line1 = f"<b>Database:</b> downloaded ({st['age']})"
        if not st["indexed"]:
            line2 = f"<b>Index:</b> <span style='color:{C['warning']};'>not built</span>"
        else:
            line2 = f"<b>Index:</b> {st['game_count']:,} games"
        if st["update_available"]:
            line3 = (f"<span style='color:{C['warning']};'>"
                     f"⚠ Newer version available on GitHub.</span>")
        elif st["downloaded"] and st["checked_today"]:
            line3 = f"<span style='color:{C['success']};'>✓ Up to date</span>"
        elif st["downloaded"]:
            line3 = f"<span style='color:{C['textDim']};'>Update status not yet checked.</span>"
        else:
            line3 = ""
        html = "<br>".join(p for p in (line1, line2, line3) if p)
        self._db_status_lbl.setText(html)

    def _kick_db_update_check(self):
        def _run():
            try:
                ss.check_manifest_update_silently()
            except Exception:
                pass
            self._sig_db_status_refresh.emit()
        threading.Thread(target=_run, daemon=True).start()

    def _confirm(self, title: str, body: str) -> bool:
        reply = QMessageBox.question(
            self, title, body,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _update_db(self):
        st = ss.manifest_db_status()
        if st["downloaded"]:
            msg = (f"This will re-download the Ludusavi manifest from GitHub "
                   f"(several MB) and rebuild the search index "
                   f"(currently {st['game_count']:,} games).\n\n"
                   f"Continue?")
        else:
            msg = ("This will download the Ludusavi manifest from GitHub "
                   "(several MB) and build the search index.\n\n"
                   "Continue?")
        if not self._confirm("Download / Update Database", msg):
            return
        dlg = LudusaviDbDialog(mode="update", parent=self._main_win)
        dlg.exec()
        self._refresh_db_status()

    def _rebuild_index(self):
        if not ss.MANIFEST_FILE.exists():
            QMessageBox.warning(
                self, "No manifest",
                "No local manifest found. Use 'Download / Update' first."
            )
            return
        st = ss.manifest_db_status()
        msg = (f"This will re-parse the local manifest and rebuild the "
               f"search index"
               + (f" (currently {st['game_count']:,} games)" if st['indexed'] else "")
               + ".\n\nContinue?")
        if not self._confirm("Rebuild Index", msg):
            return
        dlg = LudusaviDbDialog(mode="rebuild", parent=self._main_win)
        dlg.exec()
        self._refresh_db_status()

    def _db_search_exec(self):
        q = self._db_search.text().strip()
        if not q:
            return
        dlg = DbSearchResultsDialog(q, parent=self._main_win)
        dlg.exec()

    def _clear_config(self):
        reply = QMessageBox.question(self, "Clear Config",
            "This will remove all game entries. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            CFG["games"] = []
            ss.save_config(CFG)
            show_toast("Config cleared.", "info", self._main_win)

    def _clear_thumb_cache(self):
        import shutil
        for f in THUMB_DIR.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        show_toast("Thumbnail cache cleared.", "success", self._main_win)


# ── Status Bar ────────────────────────────────────────────────────────────────
class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet(f"background:{C['bg']}; border-top:1px solid rgba(255,255,255,0.06);")
        l = QHBoxLayout(self)
        l.setContentsMargins(20, 0, 20, 0)
        l.setSpacing(12)
        self._last_lbl = QLabel("Last backup: never")
        self._last_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        l.addWidget(self._last_lbl)
        l.addStretch()

    def set_last_backup(self, ts):
        self._last_lbl.setText(f"Last backup: {relative_time(ts)}")

    def set_watcher(self, _running):
        pass


# ── Main Window ───────────────────────────────────────────────────────────────
class SaveSyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SaveSync")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedWidth(1220)
        self.setMinimumHeight(560)
        self.resize(1220, 720)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Custom title bar
        outer.addWidget(TitleBar(self))

        # Main row: sidebar + content
        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.nav_clicked.connect(self._navigate)
        main_row.addWidget(self.sidebar)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{C['bg']};")

        self._panel_games    = GamesPanel(self)
        self._panel_watcher  = WatcherPanel(self)
        self._panel_restore  = RestorePanel(self)
        self._panel_settings = SettingsPanel(self)

        self._stack.addWidget(self._panel_games)
        self._stack.addWidget(self._panel_watcher)
        self._stack.addWidget(self._panel_restore)
        self._stack.addWidget(self._panel_settings)
        main_row.addWidget(self._stack, 1)

        outer.addLayout(main_row, 1)

        # Status bar
        self._status_bar = StatusBar()
        outer.addWidget(self._status_bar)

        self._panel_map = {
            "games":    0,
            "watcher":  1,
            "restore":  2,
            "settings": 3,
        }

        self._setup_tray()
        self._update_status_bar()

        # Periodic status refresh
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start(30000)

    def _navigate(self, key):
        idx = self._panel_map.get(key, 0)
        self._stack.setCurrentIndex(idx)
        if key == "restore":
            self._panel_restore._scan_drive(silent=True)

    def _update_status_bar(self):
        games = CFG.get("games", [])
        ts = ""
        for g in games:
            t = g.get("backup_timestamp") or g.get("last_sync") or ""
            if t > ts:
                ts = t
        self._status_bar.set_last_backup(ts)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(QIcon(svg_icon("savesync", "#ffffff", 32)), self)
        menu = QMenu()
        open_act = QAction("Open SaveSync", self)
        open_act.triggered.connect(self.showNormal)
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(QApplication.quit)
        menu.addAction(open_act)
        menu.addSeparator()
        menu.addAction(quit_act)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def closeEvent(self, e):
        if self.tray.isVisible():
            e.ignore()
            self.hide()
            ss.notify("SaveSync", "Running in background.")
        else:
            e.accept()


# ── Entry Point ───────────────────────────────────────────────────────────────
def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("SaveSync")
    app.setStyleSheet(QSS)
    app.setWindowIcon(QIcon(svg_icon("savesync", C['accent'], 256)))
    _ensure_trap()  # install diagnostic trap early so it catches everything

    if not CFG.get("games"):
        CFG["games"] = []
        ss.save_config(CFG)

    win = SaveSyncApp()
    win.setWindowIcon(QIcon(svg_icon("savesync", C['accent'], 256)))

    if "--minimized" in sys.argv:
        win.hide()
    else:
        win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

