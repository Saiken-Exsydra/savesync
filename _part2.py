
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
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{C['textDim']}; font-size:11px; font-weight:600; letter-spacing:0.8px;"
    )
    return lbl


# ── BackupDialog ──────────────────────────────────────────────────────────────
class BackupDialog(QDialog):
    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self._worker = None
        self._fake_timer = None
        self._step = 0
        self._steps = []
        self.setWindowTitle(f"Backup — {game['name']}")
        self.setFixedWidth(480)
        self.setStyleSheet(f"QDialog {{ background:{C['bg']}; }} QLabel {{ color:{C['text']}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        title = QLabel(f"Backup — {game['name']}")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = btn_ghost("✕", small=True)
        x.setFixedSize(28, 28)
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(18)

        stats = QGridLayout()
        stats.setSpacing(10)
        ts = game.get("backup_timestamp") or game.get("last_sync")
        items = [
            ("Save files", str(game.get("save_count", "—"))),
            ("Last backup", relative_time(ts)),
            ("Drive folder", game.get("drive_folder") or "—"),
            ("Archive path", game.get("archive_path") or "—"),
        ]
        for i, (k, v) in enumerate(items):
            cell = QFrame()
            cell.setStyleSheet(
                f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;"
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(12, 10, 12, 10)
            kl = QLabel(k.upper())
            kl.setStyleSheet(f"font-size:10px; color:{C['textDim']}; letter-spacing:0.5px;")
            vl = QLabel(v)
            vl.setStyleSheet(f"font-size:14px; font-weight:600; color:{C['text']};")
            vl.setWordWrap(True)
            cl.addWidget(kl)
            cl.addWidget(vl)
            stats.addWidget(cell, i // 2, i % 2)
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
            b = btn_primary("↑ Backup to Drive")
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
        self._done_btn.show()

    def _on_err(self, msg):
        if self._fake_timer:
            self._fake_timer.stop()
        self._log.append_line(f"✗ {msg}", ok=False)
        self._done_btn.show()


# ── SyncDialog ────────────────────────────────────────────────────────────────
class SyncDialog(QDialog):
    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self._worker = None
        self._fake_t = None
        self._step = 0
        self._steps = []
        self.setWindowTitle(f"Sync — {game['name']}")
        self.setFixedWidth(480)
        self.setStyleSheet(f"QDialog {{ background:{C['bg']}; }} QLabel {{ color:{C['text']}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        title = QLabel(f"Sync — {game['name']}")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = btn_ghost("✕", small=True)
        x.setFixedSize(28, 28)
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(18)

        ts_row = QHBoxLayout()
        ts_row.setSpacing(10)
        ts = game.get("backup_timestamp") or game.get("last_sync")
        for lbl_text, val in [("Local", relative_time(ts)), ("Drive", "checking…")]:
            cell = QFrame()
            cell.setStyleSheet(
                f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;"
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(14, 10, 14, 10)
            kl = QLabel(lbl_text.upper())
            kl.setStyleSheet(f"font-size:10px; color:{C['textDim']}; letter-spacing:0.5px;")
            vl = QLabel(val)
            vl.setStyleSheet("font-size:14px; font-weight:600;")
            cl.addWidget(kl)
            cl.addWidget(vl)
            ts_row.addWidget(cell, 1)
        root.addLayout(ts_row)
        root.addSpacing(14)

        dir_box = QFrame()
        dir_box.setStyleSheet(
            "background:rgba(124,111,255,0.08); border:1px solid rgba(124,111,255,0.2);"
            " border-radius:10px;"
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
        self.setFixedWidth(500)
        self.setMinimumHeight(500)
        self.setStyleSheet(f"QDialog {{ background:{C['bg']}; }} QLabel {{ color:{C['text']}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        title = QLabel(f"Edit — {game['name']}")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = btn_ghost("✕", small=True)
        x.setFixedSize(28, 28)
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        form = QVBoxLayout(inner)
        form.setSpacing(14)
        form.setContentsMargins(0, 0, 0, 0)

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
        self.setFixedWidth(520)
        self.setMinimumHeight(420)
        self.setStyleSheet(f"QDialog {{ background:{C['bg']}; }} QLabel {{ color:{C['text']}; }}")
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
        self._title_lbl = QLabel("Add Game")
        self._title_lbl.setStyleSheet("font-size:16px; font-weight:700;")
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        self._step_lbl = QLabel("Step 1 of 6")
        self._step_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        hdr.addWidget(self._step_lbl)
        x = btn_ghost("✕", small=True)
        x.setFixedSize(28, 28)
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
        for c in (candidates or [])[:3]:
            name = c if isinstance(c, str) else (c.get("name", "") if isinstance(c, dict) else "")
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
        if exact and isinstance(exact, dict):
            for p in list(exact.get("files", {}).keys())[:3]:
                paths.append(p)
        if not paths and candidates:
            for c in (candidates or [])[:2]:
                if isinstance(c, dict):
                    for p in list(c.get("files", {}).keys())[:1]:
                        paths.append(p)
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
