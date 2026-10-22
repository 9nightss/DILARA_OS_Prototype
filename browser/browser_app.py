from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from PyQt6.QtCore import QUrl, Qt, QSize
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QTabWidget, QToolButton, QVBoxLayout, QWidget,
    QMenu, QStatusBar, QFrame
)
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

APP_NAME = "DILARA Browser"
APP_VERSION = "0.1.0"
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("DILARA_BROWSER_DATA", str(ROOT_DIR / "data"))).expanduser()
PROFILE_DIR = DATA_DIR / "profile"
HISTORY_FILE = DATA_DIR / "history.json"
HOME_URL = "dilara://home"
SEARCH_ENGINE = "https://duckduckgo.com/?q="
MAX_HISTORY_ITEMS = 500

STYLE = """
QMainWindow, QWidget { background: #10141b; color: #dce6ef; font-family: 'Segoe UI'; font-size: 10pt; }
QToolBar { background: #131a23; border: 0; spacing: 5px; padding: 7px; }
QPushButton, QToolButton { background: #202a37; color: #dce6ef; border: 1px solid #2b3949; border-radius: 7px; padding: 6px 9px; }
QPushButton:hover, QToolButton:hover { background: #29394a; border-color: #4abfd2; }
QPushButton:pressed, QToolButton:pressed { background: #18232e; }
QLineEdit, QComboBox { background: #1b2430; color: #edf5fb; border: 1px solid #2b3949; border-radius: 9px; padding: 8px 11px; selection-background-color: #1b8294; }
QLineEdit:focus { border: 1px solid #58ccdf; }
QTabWidget::pane { border: 1px solid #222d39; top: -1px; }
QTabBar::tab { background: #151c25; color: #9eacbb; padding: 9px 14px; margin-right: 2px; border-top-left-radius: 7px; border-top-right-radius: 7px; min-width: 100px; }
QTabBar::tab:selected { background: #202a37; color: #eaf7fb; border-bottom: 2px solid #58ccdf; }
QTabBar::tab:hover { background: #202a37; }
QStatusBar { background: #131a23; color: #8192a4; border-top: 1px solid #202a37; }
QMenu { background: #19222d; color: #dce6ef; border: 1px solid #2b3949; }
QMenu::item:selected { background: #26394a; }
QFrame#NewTabCard { background: #171f29; border: 1px solid #273543; border-radius: 14px; }
QLabel#Accent { color: #63d7e8; }
"""

HOME_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#10141b;color:#dce6ef;font:16px 'Segoe UI',sans-serif;min-height:100vh;display:grid;place-items:center}
main{width:min(760px,90vw);padding:40px 20px;text-align:center}.mark{font-size:12px;letter-spacing:.32em;color:#63d7e8;text-transform:uppercase}.glyph{font-size:54px;color:#63d7e8;margin:18px 0 6px}h1{font-size:34px;letter-spacing:.12em;margin:0;font-weight:600}p{color:#8c9bad;margin:12px 0 28px}.search{display:flex;gap:8px;margin:0 auto;max-width:620px}.search input{flex:1;min-width:0;background:#1b2430;color:#edf5fb;border:1px solid #2b3949;border-radius:11px;padding:15px 17px;font-size:16px;outline:none}.search input:focus{border-color:#58ccdf}.search button{background:#203543;color:#b8f5ff;border:1px solid #315362;border-radius:11px;padding:0 20px;font-size:14px;cursor:pointer}.meta{margin-top:40px;color:#5d6f82;font-size:12px;letter-spacing:.08em}
</style></head><body><main><div class="mark">DILARA / NETWORK ACCESS</div><div class="glyph">⌁</div><h1>DILARA</h1><p>Your network. Your rules.</p><form class="search" action="https://duckduckgo.com/" method="get"><input name="q" autofocus placeholder="Search or enter an address" aria-label="Search or enter an address"><button type="submit">SEARCH ↗</button></form><div class="meta">LOCAL PROFILE · PRIVACY CONTROLS · NO BOOKMARKS · NO PASSWORD STORE</div></main></body></html>"""


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def normalize_input(text: str) -> QUrl:
    text = text.strip()
    if not text:
        return QUrl(HOME_URL)
    if text == HOME_URL:
        return QUrl(HOME_URL)
    if " " in text or ("." not in text and "://" not in text and text.lower() not in {"localhost"}):
        return QUrl(SEARCH_ENGINE + quote_plus(text))
    if "://" not in text:
        text = "https://" + text
    return QUrl.fromUserInput(text)


class BrowserPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, browser: "BrowserWindow", parent=None):
        super().__init__(profile, parent)
        self.browser = browser
        self.featurePermissionRequested.connect(self._deny_feature_permission)

    def _deny_feature_permission(self, origin, feature):
        # Conservative default: sites do not receive camera, microphone, geolocation,
        # notifications, or other feature permissions automatically.
        self.setFeaturePermission(
            origin, feature,
            QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        )
        self.browser.statusBar().showMessage("Site permission denied by default", 3500)

    def createWindow(self, window_type):
        return self.browser.create_web_tab().page()


class BrowserTab(QWidget):
    def __init__(self, profile: QWebEngineProfile, browser: "BrowserWindow"):
        super().__init__(browser.tabs)
        self.browser = browser
        # QWebEngineView has no isLoading() method in PyQt6. Track loading
        # from the documented loadStarted/loadFinished signals instead.
        self.is_loading = False
        self.view = QWebEngineView(self)
        self.page = BrowserPage(profile, browser, self.view)
        self.view.setPage(self.page)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.urlChanged.connect(lambda url: browser.on_url_changed(self, url))
        self.view.titleChanged.connect(lambda title: browser.on_title_changed(self, title))
        self.view.loadStarted.connect(lambda: browser.on_load_started(self))
        self.view.loadFinished.connect(lambda ok: browser.on_load_finished(self, ok))

    def navigate(self, url: QUrl) -> None:
        if url.toString() == HOME_URL:
            self.view.setHtml(HOME_HTML, QUrl("https://dilara.local/"))
        else:
            self.view.setUrl(url)


class BrowserWindow(QMainWindow):
    def __init__(self, initial_url: str | None = None):
        super().__init__()
        ensure_data_dirs()
        self.setWindowTitle(APP_NAME)
        self.resize(1320, 850)
        self.setMinimumSize(780, 520)
        self.setStyleSheet(STYLE)

        self.profile = QWebEngineProfile("DILARA", self)
        self.profile.setPersistentStoragePath(str(PROFILE_DIR / "storage"))
        self.profile.setCachePath(str(PROFILE_DIR / "cache"))
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.downloadRequested.connect(self._block_download)

        self._history = self._load_history()
        self._settings = self.profile.settings()
        self._settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self._settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        self._settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        self._settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        self._settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)

        self._build_ui()
        self._build_menus()
        self._bind_shortcuts()
        self.create_web_tab(initial_url or HOME_URL)

    def _build_ui(self):
        top = QWidget(self)
        root = QVBoxLayout(top)
        root.setContentsMargins(9, 8, 9, 5)
        root.setSpacing(7)
        brand_row = QHBoxLayout()
        brand = QLabel("◈  DILARA <span style='color:#63d7e8'>BROWSER</span>")
        brand.setTextFormat(Qt.TextFormat.RichText)
        brand.setStyleSheet("font-size:13px;font-weight:700;letter-spacing:2px;padding:2px 5px;")
        brand_row.addWidget(brand)
        brand_row.addStretch(1)
        self.profile_label = QLabel("● LOCAL PROFILE")
        self.profile_label.setStyleSheet("color:#63d7e8;font-size:9px;letter-spacing:1px;padding-right:8px;")
        brand_row.addWidget(self.profile_label)
        root.addLayout(brand_row)

        nav = QHBoxLayout()
        nav.setSpacing(5)
        self.back_button = self._tool_button("←", "Back", lambda: self.current_view().back())
        self.forward_button = self._tool_button("→", "Forward", lambda: self.current_view().forward())
        self.reload_button = self._tool_button("↻", "Reload", self.reload_or_stop)
        self.home_button = self._tool_button("⌂", "Home", lambda: self.navigate(HOME_URL))
        nav.addWidget(self.back_button)
        nav.addWidget(self.forward_button)
        nav.addWidget(self.reload_button)
        nav.addWidget(self.home_button)
        self.address = QLineEdit()
        self.address.setPlaceholderText("Search or enter address")
        self.address.setClearButtonEnabled(True)
        self.address.returnPressed.connect(self._navigate_from_bar)
        nav.addWidget(self.address, 1)
        self.go_button = QPushButton("GO  ↗")
        self.go_button.clicked.connect(self._navigate_from_bar)
        nav.addWidget(self.go_button)
        self.privacy_button = QToolButton()
        self.privacy_button.setText("◈ Privacy")
        self.privacy_button.setToolTip("Privacy and site controls")
        self.privacy_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.privacy_menu = QMenu(self.privacy_button)
        self.privacy_button.setMenu(self.privacy_menu)
        nav.addWidget(self.privacy_button)
        root.addLayout(nav)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._sync_controls)
        self.tabs.setUsesScrollButtons(True)
        root.addWidget(self.tabs, 1)

        self.setCentralWidget(top)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready · Downloads blocked · Site permissions denied by default")

    @staticmethod
    def _tool_button(text, tooltip, callback):
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(QSize(38, 36))
        button.clicked.connect(callback)
        return button

    def _build_menus(self):
        bar = self.menuBar()
        file_menu = bar.addMenu("Browser")
        new_tab = QAction("New tab", self, shortcut=QKeySequence.StandardKey.AddTab)
        new_tab.triggered.connect(lambda: self.create_web_tab(HOME_URL))
        file_menu.addAction(new_tab)
        close_tab = QAction("Close tab", self, shortcut=QKeySequence.StandardKey.Close)
        close_tab.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        file_menu.addAction(close_tab)
        file_menu.addSeparator()
        quit_action = QAction("Exit DILARA Browser", self, shortcut=QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        history_menu = bar.addMenu("History")
        self.history_menu = history_menu
        history_menu.aboutToShow.connect(self._populate_history_menu)
        clear_history = QAction("Clear history…", self)
        clear_history.triggered.connect(self.clear_history)
        history_menu.addSeparator()
        history_menu.addAction(clear_history)

        privacy_menu = self.privacy_menu
        self.js_action = QAction("JavaScript enabled", self, checkable=True)
        self.js_action.setChecked(True)
        self.js_action.triggered.connect(self._toggle_javascript)
        privacy_menu.addAction(self.js_action)
        self.images_action = QAction("Load images", self, checkable=True)
        self.images_action.setChecked(True)
        self.images_action.triggered.connect(self._toggle_images)
        privacy_menu.addAction(self.images_action)
        privacy_menu.addSeparator()
        clear_data = QAction("Clear cookies and cache…", self)
        clear_data.triggered.connect(self.clear_site_data)
        privacy_menu.addAction(clear_data)
        privacy_menu.addAction(clear_history)
        policy = QAction("Site permissions: deny by default", self)
        policy.setEnabled(False)
        privacy_menu.addAction(policy)
        downloads = QAction("Downloads: blocked", self)
        downloads.setEnabled(False)
        privacy_menu.addAction(downloads)

    def _bind_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self, activated=lambda: (self.address.setFocus(), self.address.selectAll()))
        QShortcut(QKeySequence("Ctrl+T"), self, activated=lambda: self.create_web_tab(HOME_URL))
        QShortcut(QKeySequence("Ctrl+W"), self, activated=lambda: self.close_tab(self.tabs.currentIndex()))
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.reload_or_stop)
        QShortcut(QKeySequence("F5"), self, activated=self.reload_or_stop)
        QShortcut(QKeySequence("Alt+Left"), self, activated=lambda: self.current_view().back())
        QShortcut(QKeySequence("Alt+Right"), self, activated=lambda: self.current_view().forward())

    def current_tab(self) -> BrowserTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, BrowserTab) else None

    def current_view(self) -> QWebEngineView:
        tab = self.current_tab()
        if tab is None:
            tab = self.create_web_tab(HOME_URL)
        return tab.view

    def create_web_tab(self, url: str | QUrl = HOME_URL) -> BrowserTab:
        tab = BrowserTab(self.profile, self)
        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)
        tab.navigate(url if isinstance(url, QUrl) else QUrl(url))
        self.address.setFocus()
        return tab

    def close_tab(self, index: int):
        if index < 0 or index >= self.tabs.count():
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()
        if self.tabs.count() == 0:
            self.create_web_tab(HOME_URL)

    def navigate(self, text: str):
        self.current_tab().navigate(normalize_input(text))

    def _navigate_from_bar(self):
        self.navigate(self.address.text())
        self.current_view().setFocus()

    def reload_or_stop(self):
        tab = self.current_tab()
        if tab is None:
            return
        if tab.is_loading:
            tab.view.stop()
        else:
            tab.view.reload()

    def on_url_changed(self, tab: BrowserTab, url: QUrl):
        if tab is self.current_tab():
            if url.host() != "dilara.local":
                self.address.setText(url.toString() if url.toString() != "about:blank" else "")
            self.back_button.setEnabled(tab.view.history().canGoBack())
            self.forward_button.setEnabled(tab.view.history().canGoForward())

    def on_title_changed(self, tab: BrowserTab, title: str):
        index = self.tabs.indexOf(tab)
        if index >= 0:
            title = title.strip() or "New Tab"
            self.tabs.setTabText(index, (title[:22] + "…") if len(title) > 23 else title)
            self.tabs.setTabToolTip(index, title)
            if tab is self.current_tab():
                self.setWindowTitle(f"{title} — {APP_NAME}")

    def on_load_started(self, tab: BrowserTab):
        tab.is_loading = True
        if tab is self.current_tab():
            self.reload_button.setText("×")
            self.statusBar().showMessage("Connecting…")

    def on_load_finished(self, tab: BrowserTab, ok: bool):
        tab.is_loading = False
        if tab is self.current_tab():
            self.reload_button.setText("↻")
            self._sync_controls()
            if ok:
                self.statusBar().showMessage("Page loaded", 2500)
                self._record_history(tab)
            else:
                self.statusBar().showMessage("Page load failed or was blocked", 4500)

    def _sync_controls(self, *_):
        tab = self.current_tab()
        if tab is None:
            return
        self.address.blockSignals(True)
        url = tab.view.url()
        self.address.setText("" if url.host() == "dilara.local" or url.toString() == "about:blank" else url.toString())
        self.address.blockSignals(False)
        self.back_button.setEnabled(tab.view.history().canGoBack())
        self.forward_button.setEnabled(tab.view.history().canGoForward())
        self.reload_button.setText("×" if tab.is_loading else "↻")

    def _block_download(self, download):
        try:
            download.cancel()
        except Exception:
            pass
        self.statusBar().showMessage("Download blocked by DILARA Browser policy", 5000)

    def _toggle_javascript(self, enabled: bool):
        self._settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, enabled)
        self.statusBar().showMessage(f"JavaScript {'enabled' if enabled else 'disabled'} for browser pages", 3500)

    def _toggle_images(self, enabled: bool):
        self._settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, enabled)
        self.statusBar().showMessage(f"Image loading {'enabled' if enabled else 'disabled'}", 3500)

    def _load_history(self) -> list[dict]:
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save_history(self):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(self._history[-MAX_HISTORY_ITEMS:], ensure_ascii=False, indent=2), encoding="utf-8")

    def _record_history(self, tab: BrowserTab):
        url = tab.view.url().toString()
        if not url or url.startswith(("about:", "https://dilara.local/")):
            return
        item = {
            "url": url,
            "title": tab.view.title() or url,
            "visited_at": datetime.now(timezone.utc).isoformat(timespec="seconds")
        }
        if self._history and self._history[-1].get("url") == url:
            self._history[-1] = item
        else:
            self._history.append(item)
        self._history = self._history[-MAX_HISTORY_ITEMS:]
        try:
            self._save_history()
        except OSError as exc:
            self.statusBar().showMessage(f"Could not save history: {exc}", 5000)

    def _populate_history_menu(self):
        # Preserve the static Clear History action at the bottom; rebuild the recent items.
        actions = self.history_menu.actions()
        static = actions[-2:] if len(actions) >= 2 else []
        for action in actions[:-2]:
            self.history_menu.removeAction(action)
            action.deleteLater()
        insert_before = static[0] if static else None
        for item in reversed(self._history[-15:]):
            title = item.get("title") or item.get("url") or "Page"
            action = QAction(title[:70], self)
            action.setToolTip(item.get("url", ""))
            action.triggered.connect(lambda checked=False, url=item.get("url", ""): self.create_web_tab(url))
            if insert_before:
                self.history_menu.insertAction(insert_before, action)
            else:
                self.history_menu.addAction(action)

    def clear_history(self):
        answer = QMessageBox.question(self, "Clear browsing history", "Delete DILARA Browser's local browsing history? This cannot be undone.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._history.clear()
        try:
            self._save_history()
        except OSError as exc:
            QMessageBox.warning(self, "History", f"History was cleared in memory but could not be saved: {exc}")
        self.statusBar().showMessage("Browsing history cleared", 3500)

    def clear_site_data(self):
        answer = QMessageBox.question(
            self, "Clear cookies and cache",
            "Clear stored cookies and the HTTP cache for this DILARA profile? This may sign you out of websites."
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.profile.cookieStore().deleteAllCookies()
        self.profile.clearHttpCache()
        self.statusBar().showMessage("Cookie deletion and cache clearing requested", 4500)

    def closeEvent(self, event):
        try:
            self._save_history()
        except OSError:
            pass
        super().closeEvent(event)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    url = None
    if len(argv) > 1:
        url = argv[1]
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("DILARA")
    app.setStyle("Fusion")
    window = BrowserWindow(url)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
