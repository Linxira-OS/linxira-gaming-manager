import os
from datetime import datetime, timezone
from pathlib import Path
import sys

from PySide6.QtCore import QProcess, QProcessEnvironment, QThread, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
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
from .launch import launch_spec, tool_status
from .paths import (
    data_home, ensure_private_directory, game_log_path, game_prefix_path,
    state_home, state_path, steam_roots,
)
from .setup import SetupTransaction, apply_setup, discard_setup, plan_setup
from .store import Store


class SetupPlanThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.succeeded.emit(plan_setup())
        except Exception as error:
            self.failed.emit(str(error))


class SetupApplyThread(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, transaction, parent=None):
        super().__init__(parent)
        self.transaction = transaction

    def run(self):
        try:
            self.succeeded.emit(apply_setup(self.transaction))
        except Exception as error:
            self.failed.emit(str(error))


class GamingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = Store(state_path())
        self.games = []
        self.setup_plan_worker = None
        self.setup_apply_worker = None
        self.game_processes = {}
        self.process_buffers = {}
        self._backup_process = None
        self.setWindowTitle("Linxira Gaming Manager")
        self.setWindowIcon(QIcon.fromTheme("applications-games"))
        self.setMinimumSize(860, 560)
        self.resize(1080, 720)
        self._build_ui()
        self.refresh_library()

    def closeEvent(self, event):
        workers = (self.setup_plan_worker, self.setup_apply_worker)
        if (
            self.game_processes
            or self._backup_process is not None
            or any(worker is not None and worker.isRunning() for worker in workers)
        ):
            event.ignore()
            QMessageBox.information(
                self, "Linxira Gaming Manager",
                "Wait for running games and setup operations to finish before closing.",
            )
            return
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
        self.library = QTableWidget(0, 5)
        self.library.setHorizontalHeaderLabels(["Game", "Source", "Runner", "Install path", "Prefix"])
        self.library.setSelectionBehavior(QTableWidget.SelectRows)
        self.library.setSelectionMode(QTableWidget.SingleSelection)
        self.library.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.library.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.library.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.library.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.library.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
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
        controls = QHBoxLayout()
        self.setup_status = QLabel("Gaming setup has not been checked")
        self.setup_status.setWordWrap(True)
        self.setup_button = QPushButton(QIcon.fromTheme("applications-games"), "Deploy gaming environment")
        self.setup_button.clicked.connect(self.plan_gaming_setup)
        controls.addWidget(self.setup_status, 1)
        controls.addWidget(self.setup_button)
        layout.addLayout(controls)
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
                game["name"], game["source"], game.get("runner") or "auto",
                game["install_path"], game.get("prefix_path") or "-"
            )):
                self.library.setItem(row, column, QTableWidgetItem(value))
        self.refresh_activity()

    def import_game(self):
        executable = QFileDialog.getOpenFileName(
            self, "Select Windows game executable", filter="Windows executables (*.exe)"
        )[0]
        if not executable:
            return
        labels = ["UMU-Proton (recommended)", "System Wine"]
        selected, accepted = QInputDialog.getItem(
            self, "Compatibility runner", "Runner", labels, 0, False
        )
        if not accepted:
            return
        runner = "umu" if selected == labels[0] else "wine"
        try:
            self.store.add_imported(Path(executable).stem, executable, runner)
        except ValueError as error:
            QMessageBox.warning(self, "Import game", str(error))
            return
        self.store.record("import", executable, "succeeded")
        self.refresh_library()

    def selected_game(self):
        row = self.library.currentRow()
        return self.games[row] if 0 <= row < len(self.games) else None

    def launch_selected(self):
        game = self.selected_game()
        if not game:
            return
        if game["id"] in self.game_processes:
            QMessageBox.information(self, "Linxira Gaming Manager", "This game is already running.")
            return
        try:
            if game["source"] == "imported":
                prefix = game_prefix_path(game["id"])
                ensure_private_directory(
                    prefix, data_home() / "linxira/gaming-manager", data_home()
                )
            spec = launch_spec(game)
        except (FileNotFoundError, ValueError) as error:
            QMessageBox.warning(self, "Linxira Gaming Manager", str(error))
            return
        process = QProcess(self)
        environment = QProcessEnvironment()
        for key, value in spec.environment.items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)
        process.setWorkingDirectory(spec.working_directory)
        process.setProgram(spec.program)
        process.setArguments(list(spec.arguments))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        game_id = game["id"]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        log_path = game_log_path(game_id, timestamp)
        self.process_buffers[game_id] = bytearray()
        process.readyReadStandardOutput.connect(lambda game_id=game_id: self._capture_game_output(game_id))
        process.finished.connect(
            lambda code, status, game_id=game_id, name=game["name"], path=log_path:
            self._game_finished(game_id, name, path, code, status)
        )
        process.errorOccurred.connect(
            lambda error, game_id=game_id, name=game["name"], path=log_path:
            self._game_process_error(game_id, name, path, error)
        )
        self.game_processes[game_id] = process
        process.start()
        self.store.record("launch", game["name"], "running", f"runner={game.get('runner', 'steam')}")
        self.refresh_activity()

    def _capture_game_output(self, game_id):
        process = self.game_processes.get(game_id)
        if process is None:
            return
        output = bytes(process.readAllStandardOutput())
        buffer = self.process_buffers[game_id]
        remaining = 1024 * 1024 - len(buffer)
        if remaining > 0:
            buffer.extend(output[:remaining])

    def _write_game_log(self, log_path, output):
        ensure_private_directory(
            log_path.parent, state_home() / "linxira/gaming-manager", state_home()
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(log_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(output)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)

    def _game_finished(self, game_id, name, log_path, exit_code, exit_status):
        if game_id not in self.game_processes:
            return
        self._capture_game_output(game_id)
        output = bytes(self.process_buffers.pop(game_id, b""))
        process = self.game_processes.pop(game_id)
        process.deleteLater()
        try:
            self._write_game_log(log_path, output)
            log_detail = f"log={log_path}"
        except (OSError, ValueError) as error:
            log_detail = f"log-error={error}"
        normal = exit_status == QProcess.ExitStatus.NormalExit
        status = "succeeded" if normal and exit_code == 0 else "failed"
        self.store.record("launch", name, status, f"exit={exit_code}; {log_detail}")
        self.refresh_activity()

    def _game_process_error(self, game_id, name, log_path, error):
        if error != QProcess.ProcessError.FailedToStart:
            return
        process = self.game_processes.get(game_id)
        if process is None:
            return
        message = process.errorString()
        output = bytes(self.process_buffers.pop(game_id, b""))
        self.game_processes.pop(game_id, None)
        process.deleteLater()
        try:
            self._write_game_log(log_path, output)
            detail = f"{message}; log={log_path}"
        except (OSError, ValueError) as log_error:
            detail = f"{message}; log-error={log_error}"
        self.store.record("launch", name, "failed", detail)
        self.refresh_activity()
        QMessageBox.warning(self, "Game launch failed", message)

    def refresh_tools(self):
        tools = tool_status()
        self.tools.setRowCount(len(tools))
        for row, (name, path) in enumerate(tools.items()):
            self.tools.setItem(row, 0, QTableWidgetItem(name))
            self.tools.setItem(row, 1, QTableWidgetItem(path or "Not installed"))

    def plan_gaming_setup(self):
        answer = QMessageBox.question(
            self,
            "Deploy gaming environment",
            "This setup installs the official Arch Steam package, UMU-Proton, Wine, GameMode, "
            "MangoHud, Gamescope, Protontricks, VKD3D and Intel/AMD open Vulkan runtimes.\n\n"
            "Steam is proprietary. Continuing records your explicit acceptance to install Steam "
            "under Valve's Steam Subscriber Agreement. Steam may present additional terms at first start.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.setup_button.setEnabled(False)
        self.setup_status.setText("Creating an immutable gaming setup plan")
        self.setup_plan_worker = SetupPlanThread(self)
        self.setup_plan_worker.succeeded.connect(self._gaming_plan_ready)
        self.setup_plan_worker.failed.connect(self._gaming_setup_failed)
        self.setup_plan_worker.finished.connect(self._setup_plan_finished)
        self.setup_plan_worker.start()

    def _gaming_plan_ready(self, transaction: SetupTransaction):
        targets = transaction.plan["directPackageTargets"]
        answer = QMessageBox.question(
            self,
            "Confirm gaming setup plan",
            "Administrator authorization will install these fixed package targets:\n\n"
            + "\n".join(targets),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Ok:
            discard_setup(transaction)
            self.setup_button.setEnabled(True)
            self.setup_status.setText("Gaming setup cancelled")
            return
        self.setup_status.setText("Installing the confirmed gaming environment")
        self.setup_apply_worker = SetupApplyThread(transaction, self)
        self.setup_apply_worker.succeeded.connect(self._gaming_setup_finished)
        self.setup_apply_worker.failed.connect(self._gaming_setup_failed)
        self.setup_apply_worker.finished.connect(self._setup_apply_finished)
        self.setup_apply_worker.start()

    def _gaming_setup_finished(self, output):
        self.setup_button.setEnabled(True)
        self.setup_status.setText("Gaming environment installed")
        self.store.record("setup", "gaming environment", "succeeded")
        self.refresh_tools()
        self.refresh_activity()
        QMessageBox.information(self, "Gaming setup", output or "Gaming environment installed.")

    def _gaming_setup_failed(self, message):
        self.setup_button.setEnabled(True)
        self.setup_status.setText("Gaming setup failed")
        self.store.record("setup", "gaming environment", "failed")
        self.refresh_activity()
        QMessageBox.warning(self, "Gaming setup", message)

    def _setup_plan_finished(self):
        self.setup_plan_worker.deleteLater()
        self.setup_plan_worker = None

    def _setup_apply_finished(self):
        self.setup_apply_worker.deleteLater()
        self.setup_apply_worker = None

    def create_backup(self):
        if self._backup_process is not None:
            QMessageBox.information(self, "Linxira Gaming Manager", "A backup is already running.")
            return
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
        subject = self.backup_source.text()
        process.finished.connect(lambda code, status: self._backup_finished(code, subject))
        process.errorOccurred.connect(
            lambda error: self._backup_error(error, subject)
        )
        process.start(executable, arguments)
        self.backup_status.setText("Backup running")
        self._backup_process = process

    def _backup_finished(self, exit_code, subject):
        if self._backup_process is None:
            return
        process = self._backup_process
        self._backup_process = None
        process.deleteLater()
        status = "succeeded" if exit_code == 0 else "failed"
        self.backup_status.setText(f"Backup {status}")
        self.store.record("backup", subject, status)
        self.refresh_activity()

    def _backup_error(self, error, subject):
        if error != QProcess.ProcessError.FailedToStart or self._backup_process is None:
            return
        process = self._backup_process
        self._backup_process = None
        message = process.errorString()
        process.deleteLater()
        self.backup_status.setText("Backup failed")
        self.store.record("backup", subject, "failed", message)
        self.refresh_activity()
        QMessageBox.warning(self, "Backup failed", message)

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
