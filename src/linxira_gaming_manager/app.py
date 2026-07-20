import os
from pathlib import Path
import sys

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .backup import backup_command
from .discovery import discover_steam
from .launch import launch_command, tool_status
from .paths import state_path, steam_roots
from .store import Store


class GamingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = Store(state_path())
        self.games = []
        self.setWindowTitle("Linxira Gaming Manager")
        self.setWindowIcon(QIcon.fromTheme("applications-games"))
        self.setMinimumSize(860, 560)
        self.resize(1080, 720)
        self._build_ui()
        self.refresh_library()

    def closeEvent(self, event):
        self.store.close()
        super().closeEvent(event)

    def _build_ui(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        refresh = QAction(QIcon.fromTheme("view-refresh"), "Refresh", self)
        refresh.triggered.connect(self.refresh_library)
        add = QAction(QIcon.fromTheme("list-add"), "Import game", self)
        add.triggered.connect(self.import_game)
        toolbar.addAction(refresh)
        toolbar.addAction(add)
        self.addToolBar(toolbar)

        tabs = QTabWidget()
        tabs.addTab(self._library_tab(), QIcon.fromTheme("applications-games"), "Library")
        tabs.addTab(self._compatibility_tab(), QIcon.fromTheme("applications-engineering"), "Compatibility")
        tabs.addTab(self._backups_tab(), QIcon.fromTheme("document-save"), "Backups")
        tabs.addTab(self._activity_tab(), QIcon.fromTheme("view-history"), "Activity")
        self.setCentralWidget(tabs)

    def _library_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.library = QTableWidget(0, 4)
        self.library.setHorizontalHeaderLabels(["Game", "Source", "Install path", "Prefix"])
        self.library.setSelectionBehavior(QTableWidget.SelectRows)
        self.library.setSelectionMode(QTableWidget.SingleSelection)
        self.library.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.library.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.library.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.library.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.library.verticalHeader().setVisible(False)
        layout.addWidget(self.library)
        row = QHBoxLayout()
        launch = QPushButton(QIcon.fromTheme("media-playback-start"), "Launch")
        launch.clicked.connect(self.launch_selected)
        row.addStretch()
        row.addWidget(launch)
        layout.addLayout(row)
        return page

    def _compatibility_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.tools = QTableWidget(0, 2)
        self.tools.setHorizontalHeaderLabels(["Tool", "Status"])
        self.tools.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tools.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tools.verticalHeader().setVisible(False)
        layout.addWidget(self.tools)
        note = QLabel("Install launchers in Package Center and compatibility foundations in Component Manager.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.refresh_tools()
        return page

    def _backups_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.backup_source = QLineEdit()
        self.backup_repository = QLineEdit()
        self.backup_password = QLineEdit()
        form.addRow("Prefix or save directory", self._path_field(self.backup_source, True))
        form.addRow("restic repository", self._path_field(self.backup_repository, True))
        form.addRow("Password file", self._path_field(self.backup_password, False))
        layout.addLayout(form)
        run = QPushButton(QIcon.fromTheme("document-save"), "Create backup")
        run.clicked.connect(self.create_backup)
        layout.addWidget(run, 0, Qt.AlignRight)
        self.backup_status = QLabel("No backup running")
        self.backup_status.setWordWrap(True)
        layout.addWidget(self.backup_status)
        layout.addStretch()
        return page

    def _activity_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.activity = QTableWidget(0, 4)
        self.activity.setHorizontalHeaderLabels(["Time", "Action", "Subject", "Status"])
        self.activity.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.activity.verticalHeader().setVisible(False)
        layout.addWidget(self.activity)
        return page

    def _path_field(self, field, directory):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(field)
        button = QPushButton(QIcon.fromTheme("document-open"), "Browse")
        button.clicked.connect(lambda: self.choose_path(field, directory))
        row.addWidget(button)
        return container

    def choose_path(self, field, directory):
        selected = QFileDialog.getExistingDirectory(self) if directory else QFileDialog.getOpenFileName(self)[0]
        if selected:
            field.setText(selected)

    def refresh_library(self):
        for game in discover_steam(steam_roots()):
            self.store.upsert_discovered(game)
        self.games = self.store.games()
        self.library.setRowCount(len(self.games))
        for row, game in enumerate(self.games):
            for column, value in enumerate((
                game["name"], game["source"], game["install_path"], game.get("prefix_path") or "-"
            )):
                self.library.setItem(row, column, QTableWidgetItem(value))
        self.refresh_activity()

    def import_game(self):
        executable = QFileDialog.getOpenFileName(self, "Select game executable")[0]
        if not executable:
            return
        self.store.add_imported(Path(executable).stem, executable)
        self.store.record("import", executable, "succeeded")
        self.refresh_library()

    def selected_game(self):
        row = self.library.currentRow()
        return self.games[row] if 0 <= row < len(self.games) else None

    def launch_selected(self):
        game = self.selected_game()
        if not game:
            return
        try:
            executable, arguments = launch_command(game)
        except (FileNotFoundError, ValueError) as error:
            QMessageBox.warning(self, "Linxira Gaming Manager", str(error))
            return
        started = QProcess.startDetached(executable, arguments)
        self.store.record("launch", game["name"], "succeeded" if started else "failed")
        self.refresh_activity()

    def refresh_tools(self):
        tools = tool_status()
        self.tools.setRowCount(len(tools))
        for row, (name, path) in enumerate(tools.items()):
            self.tools.setItem(row, 0, QTableWidgetItem(name))
            self.tools.setItem(row, 1, QTableWidgetItem(path or "Not installed"))

    def create_backup(self):
        try:
            executable, arguments, extra_environment = backup_command(
                self.backup_repository.text(),
                self.backup_password.text(),
                self.backup_source.text(),
            )
        except FileNotFoundError as error:
            QMessageBox.warning(self, "Linxira Gaming Manager", str(error))
            return
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        for key, value in extra_environment.items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)
        process.finished.connect(lambda code, status: self._backup_finished(code))
        process.start(executable, arguments)
        self.backup_status.setText("Backup running")
        self._backup_process = process

    def _backup_finished(self, exit_code):
        status = "succeeded" if exit_code == 0 else "failed"
        subject = self.backup_source.text()
        self.backup_status.setText(f"Backup {status}")
        self.store.record("backup", subject, status)
        self.refresh_activity()

    def refresh_activity(self):
        rows = self.store.activity()
        self.activity.setRowCount(len(rows))
        for row, item in enumerate(rows):
            for column, value in enumerate((
                item["created_at"], item["kind"], item["subject"], item["status"]
            )):
                self.activity.setItem(row, column, QTableWidgetItem(value))


def main():
    if os.geteuid() == 0:
        print("Linxira Gaming Manager must run as a regular user.", file=sys.stderr)
        return 1
    application = QApplication(sys.argv)
    application.setApplicationName("Linxira Gaming Manager")
    application.setOrganizationName("Linxira")
    window = GamingWindow()
    window.show()
    return application.exec()
