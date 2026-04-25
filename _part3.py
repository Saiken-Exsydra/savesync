

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

        title = QLabel("My Games")
        title.setStyleSheet(f"font-size:17px; font-weight:700; letter-spacing:-0.3px; color:{C['text']};")
        tb.addWidget(title)

        self._count_lbl = QLabel(str(len(self._games)))
        self._count_lbl.setStyleSheet(
            f"font-size:11px; color:{C['textDim']}; background:{C['cardH']}; border-radius:99px; padding:2px 8px;"
        )
        tb.addWidget(self._count_lbl)

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
        add_from_drive = btn_ghost("Add from Drive", small=True)
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

        row, col = 0, 0
        cols = max(1, self._col_count)
        for game in filtered:
            card = GameCard(game)
            card.sig_sync.connect(lambda g: SyncDialog(g, self).exec())
            card.sig_backup.connect(lambda g: self._do_backup(g))
            card.sig_edit.connect(self._edit_game)
            card.sig_remove.connect(self._remove_game)
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

        self._count_lbl.setText(str(len(self._games)))

    def _show_empty(self):
        empty = QWidget()
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
        w = self._scroll.viewport().width() - 48
        card_w = GameCard.CARD_W + 16
        self._col_count = max(1, w // card_w)
        self._rebuild_grid(self._search.text())
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
        show_toast(f"{form['name']} added to SaveSync", "success", self._main_win)

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
        show_toast(f"{updated['name']} updated", "success", self._main_win)

    def _remove_game(self, game):
        name = game.get("name","")
        reply = QMessageBox.question(self, "Remove game",
            f"Remove \"{name}\" from SaveSync?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._games = [g for g in self._games if g.get("name") != name]
            CFG["games"] = self._games
            ss.save_config(CFG)
            self._rebuild_grid(self._search.text())
            show_toast(f"{name} removed", "info", self._main_win)

    def _do_backup(self, game):
        dlg = BackupDialog(game, self)
        dlg.exec()

    def _import_from_drive(self):
        show_toast("Scanning Drive for game folders…", "info", self._main_win)
        if not ss.GDRIVE_AVAILABLE:
            show_toast("Google Drive not available. Install google-api-python-client.", "error", self._main_win)
            return
        def _scan():
            svc = ss.get_drive_service()
            return ss.list_drive_game_folders(svc)
        w = Worker(_scan)
        w.finished.connect(self._on_drive_folders)
        w.error.connect(lambda e: show_toast(f"Drive error: {e}", "error", self._main_win))
        self._import_worker = w
        w.start()

    def _on_drive_folders(self, folders):
        existing = {g.get("name","") for g in self._games}
        new_names = [f["name"] for f in folders if f["name"] not in existing]
        if not new_names:
            show_toast("No new games found on Drive.", "info", self._main_win)
            return
        for name in new_names[:5]:
            game = {**ss.GAME_DEFAULTS, "name": name, "drive_folder": f"SaveSync/{name}"}
            self._games.append(game)
        CFG["games"] = self._games
        ss.save_config(CFG)
        self._rebuild_grid(self._search.text())
        show_toast(f"Imported {len(new_names)} game(s) from Drive.", "success", self._main_win)

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
        self._toggle_btn = btn_ghost("▶ Start Watcher", small=True)
        self._toggle_btn.clicked.connect(self._toggle)
        tb.addWidget(self._toggle_btn)
        root.addWidget(topbar)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C['bg']};")
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 16, 24, 24)
        il.setSpacing(16)

        # Hero status card
        hero = QFrame()
        hero.setStyleSheet(
            f"QFrame {{ background:{C['card']}; border:1px solid {C['border']}; border-radius:14px; }}"
        )
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(24, 20, 24, 20)
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

        actions_col = QVBoxLayout()
        actions_col.setSpacing(8)
        startup_btn = btn_ghost("Add to Startup", small=True)
        startup_btn.clicked.connect(self._add_to_startup)
        actions_col.addWidget(startup_btn)
        health_btn = btn_ghost("Health Check", small=True)
        health_btn.clicked.connect(self._health_check)
        actions_col.addWidget(health_btn)
        actions_col.addStretch()
        hl.addLayout(actions_col)
        il.addWidget(hero)

        # Process list
        il.addWidget(section_title("Watched Processes"))
        self._proc_container = QWidget()
        self._proc_layout = QVBoxLayout(self._proc_container)
        self._proc_layout.setContentsMargins(0, 0, 0, 0)
        self._proc_layout.setSpacing(6)
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
        if not watched:
            lbl = QLabel("No games with exe configured. Edit a game to add its exe name.")
            lbl.setStyleSheet(f"color:{C['textDim']}; font-size:12px;")
            self._proc_layout.addWidget(lbl)
            return

        for game in watched:
            row = QFrame()
            row.setStyleSheet(
                f"QFrame {{ background:{C['card']}; border:1px solid {C['border']}; border-radius:10px; }}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 10, 14, 10)
            rl.setSpacing(12)

            dot = QWidget()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background:{C['textDim']}; border-radius:4px;"
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
        self._running = True
        self._start_time = time.time()
        self._radar.set_running(True)
        self._toggle_btn.setText("⏹ Stop Watcher")
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background:rgba(240,80,96,0.12); color:{C['error']};"
            f" border:1px solid rgba(240,80,96,0.3); border-radius:8px; padding:6px 12px; font-size:12px; }}"
            f"QPushButton:hover {{ background:rgba(240,80,96,0.2); }}"
        )
        self._status_title.setText("Watcher is running")
        self._status_sub.setText(f"Monitoring {len(watched)} process(es)")
        self._stats_widget.show()
        self._stat_watching[1].setText(str(len(watched)))
        hero_frame = self._radar.parent()
        if isinstance(hero_frame, QFrame):
            hero_frame.setStyleSheet(
                f"QFrame {{ background:{C['card']}; border:1px solid rgba(61,214,140,0.2); border-radius:14px; }}"
            )
        self._main_win.sidebar.set_watcher(True)
        self._log_entry("Watcher started")
        show_toast("Watcher started", "success", self._main_win)

    def _stop_watcher(self):
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        self._running = False
        self._radar.set_running(False)
        self._toggle_btn.setText("▶ Start Watcher")
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
        show_toast("Startup shortcut feature coming soon.", "info", self._main_win)

    def refresh(self):
        self._rebuild_proc_list()


# ── HealthCheckDialog ─────────────────────────────────────────────────────────
class HealthCheckDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Health Check")
        self.setFixedWidth(560)
        self.setMinimumHeight(400)
        self.setStyleSheet(f"QDialog {{ background:{C['bg']}; }} QLabel {{ color:{C['text']}; }}")
        self._phase = "idle"
        self._results = []
        self._timer = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Health Check")
        title.setStyleSheet("font-size:16px; font-weight:700;")
        title_col.addWidget(title)
        sub = QLabel("Verify save paths, Drive folders, and sync timestamps")
        sub.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        title_col.addWidget(sub)
        hdr.addLayout(title_col)
        hdr.addStretch()
        x = btn_ghost("✕", small=True)
        x.setFixedSize(28, 28)
        x.clicked.connect(self.reject)
        hdr.addWidget(x)
        root.addLayout(hdr)
        root.addSpacing(20)

        # Stacked: idle / scanning / done
        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # Idle page
        idle_w = QWidget()
        idle_l = QVBoxLayout(idle_w)
        idle_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idle_l.setSpacing(12)
        icon_lbl = QLabel("🔍")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size:36px;")
        idle_l.addWidget(icon_lbl)
        games = CFG.get("games", [])
        desc = QLabel(f"Scans all {len(games)} games — checks save paths, Drive folders, and compares timestamps.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size:13px; color:{C['textMid']}; max-width:320px;")
        idle_l.addWidget(desc)
        idle_l.addSpacing(8)
        run_btn = btn_primary("Run Health Check")
        run_btn.clicked.connect(self._run_check)
        idle_l.addWidget(run_btn, 0, Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(idle_w)

        # Scanning page
        scan_w = QWidget()
        scan_l = QVBoxLayout(scan_w)
        scan_l.setSpacing(10)
        self._scan_label = QLabel("Scanning…")
        self._scan_label.setStyleSheet(f"font-size:12px; color:{C['textMid']};")
        scan_l.addWidget(self._scan_label)
        self._scan_prog = QProgressBar()
        self._scan_prog.setRange(0, 100)
        scan_l.addWidget(self._scan_prog)
        self._scan_results = QWidget()
        self._scan_results_l = QVBoxLayout(self._scan_results)
        self._scan_results_l.setContentsMargins(0, 0, 0, 0)
        self._scan_results_l.setSpacing(4)
        scan_scroll = QScrollArea()
        scan_scroll.setWidgetResizable(True)
        scan_scroll.setFrameShape(QFrame.Shape.NoFrame)
        scan_scroll.setWidget(self._scan_results)
        scan_scroll.setMaximumHeight(280)
        scan_l.addWidget(scan_scroll)
        self._stack.addWidget(scan_w)

        # Done page (reuses scan layout, adds summary)
        done_w = QWidget()
        done_l = QVBoxLayout(done_w)
        done_l.setSpacing(10)
        self._summary_box = QFrame()
        self._summary_box.setStyleSheet(
            f"QFrame {{ background:rgba(61,214,140,0.07); border:1px solid rgba(61,214,140,0.2); border-radius:10px; }}"
        )
        sum_l = QHBoxLayout(self._summary_box)
        sum_l.setContentsMargins(16, 12, 16, 12)
        self._sum_icon = QLabel("✓")
        self._sum_icon.setStyleSheet(f"font-size:20px; color:{C['success']};")
        sum_l.addWidget(self._sum_icon)
        sum_text = QVBoxLayout()
        self._sum_title = QLabel("All games healthy")
        self._sum_title.setStyleSheet(f"font-size:13px; font-weight:600; color:{C['text']};")
        self._sum_sub   = QLabel("")
        self._sum_sub.setStyleSheet(f"font-size:11px; color:{C['textMid']};")
        sum_text.addWidget(self._sum_title)
        sum_text.addWidget(self._sum_sub)
        sum_l.addLayout(sum_text, 1)
        rescan_btn = btn_ghost("Re-scan", small=True)
        rescan_btn.clicked.connect(self._run_check)
        sum_l.addWidget(rescan_btn)
        done_l.addWidget(self._summary_box)
        self._done_results = QWidget()
        self._done_results_l = QVBoxLayout(self._done_results)
        self._done_results_l.setContentsMargins(0, 0, 0, 0)
        self._done_results_l.setSpacing(4)
        done_scroll = QScrollArea()
        done_scroll.setWidgetResizable(True)
        done_scroll.setFrameShape(QFrame.Shape.NoFrame)
        done_scroll.setWidget(self._done_results)
        done_scroll.setMaximumHeight(280)
        done_l.addWidget(done_scroll)
        foot = QHBoxLayout()
        foot.addStretch()
        close_btn = btn_primary("Close")
        close_btn.clicked.connect(self.accept)
        foot.addWidget(close_btn)
        done_l.addLayout(foot)
        self._stack.addWidget(done_w)

    def _run_check(self):
        self._results = []
        self._stack.setCurrentIndex(1)
        self._phase = "scanning"
        # Clear previous results
        for i in reversed(range(self._scan_results_l.count())):
            w = self._scan_results_l.itemAt(i).widget()
            if w: w.deleteLater()
        games = CFG.get("games", [])
        self._games_to_check = list(games)
        self._check_idx = 0
        self._scan_prog.setValue(0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_next)
        self._timer.start(300)

    def _check_next(self):
        games = self._games_to_check
        if self._check_idx >= len(games):
            self._timer.stop()
            self._finish()
            return
        g = games[self._check_idx]
        self._scan_label.setText(f"Scanning: {g.get('name','')}")
        self._scan_prog.setValue(int((self._check_idx + 1) / len(games) * 100))

        save_path_ok = bool(g.get("save_path")) and Path(g["save_path"]).exists()
        drive_ok     = bool(g.get("drive_folder")) or None
        ts           = g.get("backup_timestamp") or g.get("last_sync")
        sync_fresh   = False
        if ts:
            try:
                dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=datetime.timezone.utc)
                sync_fresh = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() < 7 * 86400
            except Exception:
                pass
        issues = (0 if save_path_ok else 1) + (1 if drive_ok is False else 0) + (0 if sync_fresh or not ts else 0)
        r = {
            "name": g.get("name",""),
            "save_path_ok": save_path_ok,
            "drive_ok": drive_ok,
            "sync_fresh": sync_fresh or not ts,
            "issues": issues,
        }
        self._results.append(r)
        self._add_result_row(self._scan_results_l, r)
        self._check_idx += 1

    def _add_result_row(self, layout, r):
        row = QFrame()
        has_issue = r["issues"] > 0
        row.setStyleSheet(
            f"QFrame {{ background:{'rgba(240,168,48,0.05)' if has_issue else C['bg2']};"
            f" border:1px solid {'rgba(240,168,48,0.2)' if has_issue else C['border']};"
            f" border-radius:8px; }}"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 9, 14, 9)
        rl.setSpacing(12)
        name_lbl = QLabel(r["name"])
        name_lbl.setStyleSheet(f"font-size:12px; font-weight:500; color:{C['text']};")
        rl.addWidget(name_lbl, 1)
        for label, ok in [("Path", r["save_path_ok"]), ("Sync", r["sync_fresh"])]:
            col = QVBoxLayout()
            col.setSpacing(1)
            dot = QLabel("✓" if ok else "✗")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(f"font-size:11px; font-weight:600; color:{C['success'] if ok else C['error']};")
            sub = QLabel(label)
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setStyleSheet(f"font-size:9px; color:{C['textDim']};")
            col.addWidget(dot)
            col.addWidget(sub)
            col_w = QWidget()
            col_w.setLayout(col)
            rl.addWidget(col_w)
        if has_issue:
            badge = QLabel(f"{r['issues']} issue{'s' if r['issues']>1 else ''}")
            badge.setStyleSheet(
                f"background:rgba(240,168,48,0.12); color:{C['warning']};"
                f" font-size:10px; font-weight:600; border-radius:99px; padding:2px 8px;"
            )
            rl.addWidget(badge)
        layout.addWidget(row)

    def _finish(self):
        self._phase = "done"
        total_issues = sum(r["issues"] for r in self._results)
        # Populate done results
        for i in reversed(range(self._done_results_l.count())):
            w = self._done_results_l.itemAt(i).widget()
            if w: w.deleteLater()
        for r in self._results:
            self._add_result_row(self._done_results_l, r)
        # Summary
        if total_issues == 0:
            self._sum_icon.setText("✓")
            self._sum_icon.setStyleSheet(f"font-size:20px; color:{C['success']};")
            self._sum_title.setText("All games healthy")
            self._summary_box.setStyleSheet(
                f"QFrame {{ background:rgba(61,214,140,0.07); border:1px solid rgba(61,214,140,0.2); border-radius:10px; }}"
            )
        else:
            self._sum_icon.setText("⚠")
            self._sum_icon.setStyleSheet(f"font-size:20px; color:{C['warning']};")
            self._sum_title.setText(f"{total_issues} issue{'s' if total_issues>1 else ''} found")
            self._summary_box.setStyleSheet(
                f"QFrame {{ background:rgba(240,168,48,0.07); border:1px solid rgba(240,168,48,0.2); border-radius:10px; }}"
            )
        ok_count = len([r for r in self._results if r["issues"] == 0])
        self._sum_sub.setText(f"{len(self._results)} games scanned · {ok_count} OK")
        self._stack.setCurrentIndex(2)


# ── RestorePanel ──────────────────────────────────────────────────────────────
class RestorePanel(QWidget):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._main_win = main_win
        self._drive_games = []
        self._worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        topbar = QWidget()
        topbar.setStyleSheet(f"background:{C['bg']};")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(24, 18, 24, 0)
        tb.setSpacing(12)
        title = QLabel("Restore from Drive")
        title.setStyleSheet(f"font-size:17px; font-weight:700; letter-spacing:-0.3px;")
        tb.addWidget(title)
        tb.addStretch()
        scan_btn = btn_ghost("Scan Drive", small=True)
        scan_btn.clicked.connect(self._scan_drive)
        tb.addWidget(scan_btn)
        root.addWidget(topbar)

        # Content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C['bg']};")
        self._il = QVBoxLayout(inner)
        self._il.setContentsMargins(24, 16, 24, 24)
        self._il.setSpacing(10)

        self._placeholder = QLabel("Click 'Scan Drive' to list game backups.")
        self._placeholder.setStyleSheet(f"color:{C['textDim']}; font-size:13px;")
        self._il.addWidget(self._placeholder)
        self._il.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def _scan_drive(self):
        if not ss.GDRIVE_AVAILABLE:
            show_toast("Google Drive not available.", "error", self._main_win)
            return
        show_toast("Scanning Drive…", "info", self._main_win)
        def _do():
            svc = ss.get_drive_service()
            return ss.list_drive_game_folders(svc)
        self._worker = Worker(_do)
        self._worker.finished.connect(self._on_scan)
        self._worker.error.connect(lambda e: show_toast(f"Drive error: {e}", "error", self._main_win))
        self._worker.start()

    def _on_scan(self, folders):
        for i in reversed(range(self._il.count())):
            item = self._il.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        self._drive_games = folders
        existing = {g.get("name","") for g in CFG.get("games", [])}

        not_local = [f for f in folders if f.get("name") not in existing]
        all_games = folders

        if not_local:
            self._il.addWidget(section_title(f"Not in local list ({len(not_local)})"))
            for g in not_local:
                self._il.addWidget(self._restore_row(g, local=False))

        self._il.addWidget(section_title(f"All Drive games ({len(all_games)})"))
        for g in all_games:
            self._il.addWidget(self._restore_row(g, local=g.get("name") in existing))

        self._il.addStretch()

    def _restore_row(self, folder, local):
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background:{C['card']}; border:1px solid {C['border']}; border-radius:10px; }}"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(14)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(folder.get("name",""))
        name_lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{C['text']};")
        info.addWidget(name_lbl)
        rl.addLayout(info, 1)

        if not local:
            badge = QLabel("Not local")
            badge.setStyleSheet(
                f"background:rgba(240,168,48,0.1); color:{C['warning']};"
                f" font-size:10px; font-weight:600; border-radius:99px; padding:2px 8px;"
            )
            rl.addWidget(badge)

        restore_btn = btn_ghost("↩ Restore", small=True)
        restore_btn.clicked.connect(lambda _, f=folder: self._restore(f))
        rl.addWidget(restore_btn)

        if not local:
            add_btn = btn_primary("+ Add", small=True)
            add_btn.clicked.connect(lambda _, f=folder: self._add_from_drive(f))
            rl.addWidget(add_btn)

        return row

    def _restore(self, folder):
        show_toast(f"Restoring {folder.get('name','')}…", "info", self._main_win)
        def _do():
            svc = ss.get_drive_service()
            files = ss.list_drive_save_files(svc, folder["id"])
            for f in files[:3]:
                dest = ss.BASE_DIR / "restored" / folder.get("name","") / f["name"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                ss.download_file_from_drive(svc, f["id"], dest)
            return True
        w = Worker(_do)
        w.finished.connect(lambda _: show_toast(f"{folder.get('name','')} restored", "success", self._main_win))
        w.error.connect(lambda e: show_toast(f"Restore error: {e}", "error", self._main_win))
        self._restore_worker = w
        w.start()

    def _add_from_drive(self, folder):
        name = folder.get("name","")
        game = {**ss.GAME_DEFAULTS, "name": name, "drive_folder": f"SaveSync/{name}"}
        CFG.setdefault("games", []).append(game)
        ss.save_config(CFG)
        show_toast(f"{name} added from Drive", "success", self._main_win)


# ── SettingsPanel ─────────────────────────────────────────────────────────────
class SettingsPanel(QWidget):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._main_win = main_win

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
        il.setContentsMargins(24, 16, 24, 32)
        il.setSpacing(24)

        # Google Drive section
        il.addWidget(section_title("Google Drive"))
        drive_card = QFrame()
        drive_card.setStyleSheet(
            f"QFrame {{ background:{C['card']}; border:1px solid {C['border']}; border-radius:12px; }}"
        )
        dcl = QVBoxLayout(drive_card)
        dcl.setContentsMargins(0, 0, 0, 0)
        dcl.setSpacing(0)

        # Account row
        self._drive_connected = False
        self._drive_btn = btn_primary("Connect Drive", small=True)
        self._drive_btn.clicked.connect(self._toggle_drive)
        self._add_row(dcl, "Account", "Not connected", self._drive_btn)

        drive_folder_edit = QLineEdit(CFG.get("drive_root_folder", "SaveSync"))
        drive_folder_edit.setFixedWidth(160)
        drive_folder_edit.setStyleSheet(
            f"QLineEdit {{ background:{C['bg2']}; border:1px solid {C['border']}; border-radius:7px;"
            f" padding:5px 8px; font-size:12px; font-family:'Inter','Segoe UI',sans-serif; }}"
        )
        drive_folder_edit.textChanged.connect(
            lambda t: CFG.update({"drive_root_folder": t})
        )
        self._add_row(dcl, "Root folder", "All backups stored under this folder", drive_folder_edit)
        il.addWidget(drive_card)

        # Notifications section
        il.addWidget(section_title("Notifications"))
        notif_card = QFrame()
        notif_card.setStyleSheet(
            f"QFrame {{ background:{C['card']}; border:1px solid {C['border']}; border-radius:12px; }}"
        )
        ncl = QVBoxLayout(notif_card)
        ncl.setContentsMargins(0, 0, 0, 0)
        ncl.setSpacing(0)
        for label, key, sub in [
            ("Backup complete",      "notif_backup",  "Toast when a backup finishes"),
            ("Sync events",          "notif_sync",    "Toast when Drive sync runs"),
            ("Startup health check", "notif_health",  "Notification on Windows login"),
        ]:
            toggle = self._toggle_switch(CFG.get(key, True))
            toggle.toggled.connect(lambda v, k=key: CFG.update({k: v}))
            self._add_row(ncl, label, sub, toggle)
        il.addWidget(notif_card)

        # Startup section
        il.addWidget(section_title("Startup"))
        startup_card = QFrame()
        startup_card.setStyleSheet(
            f"QFrame {{ background:{C['card']}; border:1px solid {C['border']}; border-radius:12px; }}"
        )
        scl = QVBoxLayout(startup_card)
        scl.setContentsMargins(0, 0, 0, 0)
        scl.setSpacing(0)
        startup_toggle = self._toggle_switch(CFG.get("start_with_windows", False))
        startup_toggle.toggled.connect(lambda v: CFG.update({"start_with_windows": v}))
        self._add_row(scl, "Start with Windows", "Launches minimized to tray", startup_toggle)
        il.addWidget(startup_card)

        # Ludusavi Database section
        il.addWidget(section_title("Ludusavi Database"))
        db_card = QFrame()
        db_card.setStyleSheet(
            f"QFrame {{ background:{C['card']}; border:1px solid {C['border']}; border-radius:12px; }}"
        )
        dbl = QVBoxLayout(db_card)
        dbl.setContentsMargins(16, 12, 16, 12)
        dbl.setSpacing(10)

        age = ss.manifest_db_age()
        age_txt = f"{int(age)} days old" if age is not None else "not downloaded"
        db_info_row = QHBoxLayout()
        db_info_row.addWidget(QLabel(f"Status: {age_txt}"))
        db_info_row.addStretch()
        update_btn = btn_ghost("Download / Update", small=True)
        update_btn.clicked.connect(self._update_db)
        db_info_row.addWidget(update_btn)
        rebuild_btn = btn_ghost("Rebuild Index", small=True)
        rebuild_btn.clicked.connect(self._rebuild_index)
        db_info_row.addWidget(rebuild_btn)
        dbl.addLayout(db_info_row)

        # Search
        search_row = QHBoxLayout()
        self._db_search = QLineEdit()
        self._db_search.setPlaceholderText("Search save location database…")
        search_row.addWidget(self._db_search, 1)
        search_exec = btn_ghost("Search", small=True)
        search_exec.clicked.connect(self._db_search_exec)
        search_row.addWidget(search_exec)
        dbl.addLayout(search_row)

        self._db_results = QWidget()
        self._db_results_l = QVBoxLayout(self._db_results)
        self._db_results_l.setContentsMargins(0, 0, 0, 0)
        self._db_results_l.setSpacing(4)
        dbl.addWidget(self._db_results)
        il.addWidget(db_card)

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

    def _add_row(self, layout, label, sub, widget):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(12)
        txt_col = QVBoxLayout()
        txt_col.setSpacing(2)
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
        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:#111827;")
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

    def _toggle_drive(self):
        if not ss.GDRIVE_AVAILABLE:
            show_toast("Install google-api-python-client to use Drive.", "error", self._main_win)
            return
        if self._drive_connected:
            self._drive_connected = False
            self._drive_btn.setText("Connect Drive")
            show_toast("Drive disconnected.", "info", self._main_win)
        else:
            def _do():
                return ss.get_drive_service()
            w = Worker(_do)
            w.finished.connect(lambda _: self._on_drive_connected())
            w.error.connect(lambda e: show_toast(f"Drive auth error: {e}", "error", self._main_win))
            self._drive_worker = w
            w.start()

    def _on_drive_connected(self):
        self._drive_connected = True
        self._drive_btn.setText("Disconnect")
        show_toast("Google Drive connected.", "success", self._main_win)

    def _update_db(self):
        show_toast("Downloading Ludusavi manifest…", "info", self._main_win)
        def _do():
            ss.download_manifest()
            ss.build_manifest_index()
            return True
        w = Worker(_do)
        w.finished.connect(lambda _: show_toast("Database updated.", "success", self._main_win))
        w.error.connect(lambda e: show_toast(f"DB error: {e}", "error", self._main_win))
        self._db_worker = w
        w.start()

    def _rebuild_index(self):
        show_toast("Rebuilding index…", "info", self._main_win)
        def _do():
            ss.build_manifest_index()
            return True
        w = Worker(_do)
        w.finished.connect(lambda _: show_toast("Index rebuilt.", "success", self._main_win))
        w.error.connect(lambda e: show_toast(f"Index error: {e}", "error", self._main_win))
        self._idx_worker = w
        w.start()

    def _db_search_exec(self):
        q = self._db_search.text().strip()
        if not q:
            return
        for i in reversed(range(self._db_results_l.count())):
            w = self._db_results_l.itemAt(i).widget()
            if w: w.deleteLater()
        def _do():
            return ss.search_manifest_split(q)
        w = Worker(_do)
        w.finished.connect(self._on_db_search_results)
        w.error.connect(lambda e: show_toast(f"Search error: {e}", "error", self._main_win))
        self._search_worker = w
        w.start()

    def _on_db_search_results(self, result):
        for i in reversed(range(self._db_results_l.count())):
            w = self._db_results_l.itemAt(i).widget()
            if w: w.deleteLater()
        exact, candidates = result if isinstance(result, tuple) else (None, [])
        items = []
        if exact and isinstance(exact, dict):
            for path in list(exact.get("files", {}).keys())[:3]:
                items.append((exact.get("name",""), path))
        for c in (candidates or [])[:3]:
            if isinstance(c, dict):
                for path in list(c.get("files", {}).keys())[:1]:
                    items.append((c.get("name",""), path))
        if not items:
            lbl = QLabel("No results found.")
            lbl.setStyleSheet(f"color:{C['textDim']}; font-size:12px;")
            self._db_results_l.addWidget(lbl)
            return
        for name, path in items[:6]:
            cell = QFrame()
            cell.setStyleSheet(
                f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;"
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(12, 8, 12, 8)
            nl = QLabel(name)
            nl.setStyleSheet(f"font-size:11px; font-weight:500; color:{C['text']};")
            pl = QLabel(path)
            pl.setStyleSheet(
                f"font-size:10px; color:{C['driveFg']}; font-family:'JetBrains Mono','Consolas',monospace;"
            )
            cl.addWidget(nl)
            cl.addWidget(pl)
            self._db_results_l.addWidget(cell)

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
        self.setFixedHeight(30)
        self.setStyleSheet(f"background:{C['bg2']}; border-top:1px solid {C['border']};")
        l = QHBoxLayout(self)
        l.setContentsMargins(20, 0, 20, 0)
        l.setSpacing(12)
        self._last_lbl = QLabel("Last backup: never")
        self._last_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        l.addWidget(self._last_lbl)
        l.addStretch()
        self._watcher_lbl = QLabel("● Watcher stopped")
        self._watcher_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")
        l.addWidget(self._watcher_lbl)

    def set_last_backup(self, ts):
        self._last_lbl.setText(f"Last backup: {relative_time(ts)}")

    def set_watcher(self, running):
        if running:
            self._watcher_lbl.setText("● Watcher running")
            self._watcher_lbl.setStyleSheet(f"font-size:11px; color:{C['success']};")
        else:
            self._watcher_lbl.setText("● Watcher stopped")
            self._watcher_lbl.setStyleSheet(f"font-size:11px; color:{C['textDim']};")


# ── Main Window ───────────────────────────────────────────────────────────────
class SaveSyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SaveSync")
        self.resize(1100, 720)
        self.setMinimumSize(800, 560)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

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

    def _update_status_bar(self):
        games = CFG.get("games", [])
        ts = ""
        for g in games:
            t = g.get("backup_timestamp") or g.get("last_sync") or ""
            if t > ts:
                ts = t
        self._status_bar.set_last_backup(ts)

    def _setup_tray(self):
        px = QPixmap(32, 32)
        px.fill(QColor(C['accent']))
        self.tray = QSystemTrayIcon(QIcon(px), self)
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
            self.tray.showMessage("SaveSync", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 2000)
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

    if not CFG.get("games"):
        CFG["games"] = []
        ss.save_config(CFG)

    win = SaveSyncApp()

    if "--minimized" in sys.argv:
        win.hide()
    else:
        win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
