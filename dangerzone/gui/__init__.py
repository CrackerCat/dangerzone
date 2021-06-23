import os
import sys
import signal
import platform
import click
import uuid
import time
from PySide2 import QtCore, QtWidgets

from .common import GuiCommon
from .main_window import MainWindow
from .docker_installer import (
    is_docker_installed,
    is_docker_ready,
    DockerInstaller,
    AuthorizationFailed,
)
from .multipass import is_multipass_installed, MultipassInstaller
from ..global_common import GlobalCommon


# For some reason, Dangerzone segfaults if I inherit from QApplication directly, so instead
# this is a class whose job is to hold a QApplication object and customize it
class ApplicationWrapper(QtCore.QObject):
    document_selected = QtCore.Signal(str)
    application_activated = QtCore.Signal()

    def __init__(self):
        super(ApplicationWrapper, self).__init__()
        self.app = QtWidgets.QApplication()
        self.app.setQuitOnLastWindowClosed(False)

        self.original_event = self.app.event

        def monkeypatch_event(event):
            # In macOS, handle the file open event
            if event.type() == QtCore.QEvent.FileOpen:
                self.document_selected.emit(event.file())
                return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True

            return self.original_event(event)

        self.app.event = monkeypatch_event


@click.command()
@click.option("--custom-container")  # Use this container instead of flmcode/dangerzone
@click.argument("filename", required=False)
def gui_main(custom_container, filename):
    if platform.system() == "Darwin":
        # Required for macOS Big Sur: https://stackoverflow.com/a/64878899
        os.environ["QT_MAC_WANTS_LAYER"] = "1"

        # Strip ANSI colors from stdout output, to prevent terminal colors from breaking
        # the macOS GUI app
        from strip_ansi import strip_ansi

        class StdoutFilter:
            def __init__(self, stream):
                self.stream = stream

            def __getattr__(self, attr_name):
                return getattr(self.stream, attr_name)

            def write(self, data):
                self.stream.write(strip_ansi(data))

            def flush(self):
                self.stream.flush()

        sys.stdout = StdoutFilter(sys.stdout)
        sys.stderr = StdoutFilter(sys.stderr)

    # Create the Qt app
    app_wrapper = ApplicationWrapper()
    app = app_wrapper.app

    # Common objects
    global_common = GlobalCommon()
    gui_common = GuiCommon(app, global_common)

    if custom_container:
        success, error_message = global_common.container_exists(custom_container)
        if not success:
            click.echo(error_message)
            return

        global_common.custom_container = custom_container

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # See if we need to install Multipass
    if (platform.system() == "Darwin") and not is_multipass_installed():
        click.echo("Multipass is not installed")
        multipass_installer = MultipassInstaller(gui_common)
        if not multipass_installer.start():
            click.echo("Installing Multipass failed")
            return

    # See if we need to install Docker...
    if platform.system() == "Windows" and (
        not is_docker_installed() or not is_docker_ready(global_common)
    ):
        click.echo("Docker is either not installed or not running")
        docker_installer = DockerInstaller(gui_common)
        docker_installer.start()
        return

    closed_windows = {}
    windows = {}

    def delete_window(window_id):
        closed_windows[window_id] = windows[window_id]
        del windows[window_id]

    # Open a document in a window
    def select_document(filename=None):
        if (
            len(windows) == 1
            and windows[list(windows.keys())[0]].common.document_filename == None
        ):
            window = windows[list(windows.keys())[0]]
        else:
            window_id = uuid.uuid4().hex
            window = MainWindow(global_common, gui_common, window_id)
            window.delete_window.connect(delete_window)
            windows[window_id] = window

        if filename:
            # Validate filename
            filename = os.path.abspath(os.path.expanduser(filename))
            try:
                open(filename, "rb")
            except FileNotFoundError:
                click.echo("File not found")
                return False
            except PermissionError:
                click.echo("Permission denied")
                return False
            window.common.document_filename = filename
            window.doc_selection_widget.document_selected.emit()

        return True

    # Open a new window if not filename is passed
    if filename is None:
        select_document()
    else:
        # If filename is passed as an argument, open it
        if not select_document(filename):
            return True

    # Open a new window, if all windows are closed
    def application_activated():
        if len(windows) == 0:
            select_document()

    # If we get a file open event, open it
    app_wrapper.document_selected.connect(select_document)

    # If the application is activated and all windows are closed, open a new one
    app_wrapper.application_activated.connect(application_activated)

    sys.exit(app.exec_())
