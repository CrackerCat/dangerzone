import os
import stat
import requests
import subprocess
import platform
import tempfile
import appdirs
from PySide2 import QtCore, QtGui, QtWidgets


def is_multipass_installed():
    if platform.system() != "Darwin":
        print("Multipass support is Mac-only")
        return

    # Do the multipass app binary exist?
    if os.path.isdir("/Applications/Multipass.app") and os.path.exists(
        "/usr/local/bin/multipass"
    ):
        # Is it executable?
        st = os.stat("/usr/local/bin/multipass")
        return bool(st.st_mode & stat.S_IXOTH)

    return False


class MultipassInstaller(QtWidgets.QDialog):
    def __init__(self, gui_common):
        super(MultipassInstaller, self).__init__()

        self.setWindowTitle("Dangerzone")
        self.setWindowIcon(gui_common.get_window_icon())

        label = QtWidgets.QLabel()
        label.setText("Dangerzone for macOS requires Multipass")
        label.setStyleSheet("QLabel { font-weight: bold; }")
        label.setAlignment(QtCore.Qt.AlignCenter)

        self.task_label = QtWidgets.QLabel()
        self.task_label.setAlignment(QtCore.Qt.AlignCenter)
        self.task_label.setWordWrap(True)
        self.task_label.setOpenExternalLinks(True)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setMinimum(0)

        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.clicked.connect(self.ok_clicked)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_clicked)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.task_label)
        layout.addWidget(self.progress)
        layout.addLayout(buttons_layout)
        layout.addStretch()
        self.setLayout(layout)

        # Download dir
        self.download_dir = tempfile.TemporaryDirectory(
            prefix=os.path.join(appdirs.user_cache_dir("dangerzone"), "download-")
        )
        self.installer_filename = os.path.join(self.download_dir.name, "multipass.pkg")

        # Threads
        self.download_t = None
        self.install_t = None

    def update_progress(self, value, maximum):
        self.progress.setMaximum(maximum)
        self.progress.setValue(value)

    def update_task_label(self, s):
        self.task_label.setText(s)

    def install_finished(self):
        self.install_t = None

        if is_multipass_installed():
            self.accept()
        else:
            self.task_label.setText("Installation failed")
            self.progress.hide()
            self.ok_button.hide()
            self.cancel_button.show()

    def download_finished(self):
        self.task_label.setText("Installing Multipass")
        self.download_t = None

        # Start installing Multipass
        self.cancel_button.hide()
        self.progress.setValue(0)
        self.progress.setMaximum(0)

        self.install_t = Installer(self.installer_filename)
        self.install_t.install_finished.connect(self.install_finished)
        self.install_t.start()

    def download_failed(self, status_code):
        print(f"Download failed: status code {status_code}")
        self.download_t = None

    def download(self):
        self.task_label.setText("Downloading Multipass")

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.start_download)
        self.timer.setSingleShot(True)
        self.timer.start(10)

    def start_download(self):
        self.download_t = Downloader(self.installer_filename)
        self.download_t.download_finished.connect(self.download_finished)
        self.download_t.download_failed.connect(self.download_failed)
        self.download_t.update_progress.connect(self.update_progress)
        self.download_t.start()

    def cancel_clicked(self):
        self.reject()

        if self.download_t:
            self.download_t.canceled = True
            self.download_t.quit()
            self.download_t.wait()

        if self.install_t:
            self.install_t.quit()

    def ok_clicked(self):
        self.accept()

    def start(self):
        self.ok_button.hide()
        self.download()
        return self.exec_() == QtWidgets.QDialog.Accepted


class Downloader(QtCore.QThread):
    download_finished = QtCore.Signal()
    download_failed = QtCore.Signal(int)
    update_progress = QtCore.Signal(int, int)

    def __init__(self, installer_filename):
        super(Downloader, self).__init__()
        self.installer_filename = installer_filename
        self.installer_url = "https://multipass.run/download/macos"
        self.canceled = False

    def run(self):
        print(f"Downloading multipass to {self.installer_filename}")
        with requests.get(self.installer_url, stream=True) as r:
            if r.status_code != 200:
                self.download_failed.emit(r.status_code)
                return
            total_bytes = int(r.headers.get("content-length"))
            downloaded_bytes = 0

            with open(self.installer_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        downloaded_bytes += f.write(chunk)

                        self.update_progress.emit(downloaded_bytes, total_bytes)

                    if self.canceled:
                        break

        self.download_finished.emit()


class Installer(QtCore.QThread):
    install_finished = QtCore.Signal()

    def __init__(self, installer_filename):
        super(Installer, self).__init__()
        self.installer_filename = installer_filename

    def run(self):
        print(f"Installing multipass")
        subprocess.run(["open", "-W", self.installer_filename])
        self.install_finished.emit()
