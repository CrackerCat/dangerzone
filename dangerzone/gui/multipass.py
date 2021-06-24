import os
import stat
import requests
import subprocess
import platform
import tempfile
import appdirs
import json
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


class DangerzoneVM(QtWidgets.QDialog):
    def __init__(self, gui_common, global_common):
        super(DangerzoneVM, self).__init__()
        self.global_common = global_common

        self.setWindowTitle("Booting Dangerzone VM")
        self.setWindowIcon(gui_common.get_window_icon())
        self.setMinimumWidth(300)
        self.setMinimumHeight(100)

        self.output_label = QtWidgets.QLabel()
        self.output_label.setAlignment(QtCore.Qt.AlignLeft)
        self.output_label.setWordWrap(True)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setValue(0)
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)

        self.cancel_button = QtWidgets.QPushButton("Sorry")
        self.cancel_button.clicked.connect(self.cancel_clicked)
        self.cancel_button.hide()

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.output_label)
        layout.addWidget(self.progress)
        layout.addLayout(buttons_layout)
        layout.addStretch()
        self.setLayout(layout)

        # Threads
        self.vm_booter_t = None

    def cancel_clicked(self):
        self.reject()

    def vm_finished(self):
        self.accept()

    def vm_failed(self):
        self.setWindowTitle("Booting VM failed")
        self.output_label.hide()
        self.cancel_button.show()

    def update_progress(self, label, output):
        self.setWindowTitle(label)
        self.output_label.setText(output)

    def start(self):
        self.vm_booter_t = VmBooter(self.global_common)
        self.vm_booter_t.vm_finished.connect(self.vm_finished)
        self.vm_booter_t.vm_failed.connect(self.vm_failed)
        self.vm_booter_t.update_progress.connect(self.update_progress)
        self.vm_booter_t.start()
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
        subprocess.run(["/usr/bin/open", "-W", self.installer_filename])
        self.install_finished.emit()


class VmBooter(QtCore.QThread):
    vm_finished = QtCore.Signal()
    vm_failed = QtCore.Signal(str)
    update_progress = QtCore.Signal(str, str)

    def __init__(self, global_common):
        super(VmBooter, self).__init__()
        self.global_common = global_common
        self.task_title = ""

        self.tmp_dir = tempfile.TemporaryDirectory(
            prefix=os.path.join(appdirs.user_cache_dir("dangerzone"), "vm-booter-")
        )
        self.multipass_resource_path = self.global_common.get_resource_path("multipass")

    def update(self, output=""):
        self.update_progress.emit(self.task_title, output)

    def exec_multipass_interactive(self, args):
        p = subprocess.Popen(
            ["/usr/local/bin/multipass"] + args,
            startupinfo=self.global_common.get_subprocess_startupinfo(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        line = b""
        while p.poll() is None:
            chunk = p.stdout.read(1)
            if chunk == b"\x08":
                line = line[0:-1]
            elif chunk == b"\r":
                line = b""
            else:
                line += chunk

            self.update(line.decode())

    def exec_multipass_list(self):
        cmd = ["/usr/local/bin/multipass", "list", "--format", "json"]
        stdout = subprocess.check_output(cmd)
        try:
            multipass_list = json.loads(stdout)
            if "list" not in multipass_list:
                self.vm_failed.emit(f"Missing key 'list': {multipass_list}")
                return None
        except:
            self.vm_failed.emit(f"Invalid JSON: {stdout}")
            return None

        return multipass_list

    def run(self):
        # Open Multipass
        self.task_title = "Opening Multipass"
        self.update()
        subprocess.run(["/usr/bin/open", "-a", "Multipass.app"])

        # Make sure SSH key is there
        self.task_title = "Checking on encryption keys"
        self.update()
        ssh_seckey_filename = os.path.join(
            self.global_common.appdata_path, "id_ed25519"
        )
        ssh_pubkey_filename = os.path.join(
            self.global_common.appdata_path, "id_ed25519.pub"
        )
        if not (
            os.path.exists(ssh_seckey_filename) and os.path.exists(ssh_pubkey_filename)
        ):
            self.update("Generating SSH keys")
            subprocess.run(
                [
                    "/usr/bin/ssh-keygen",
                    "-t",
                    "ed25519",
                    "-N",
                    "",
                    "-C",
                    "dangerzone",
                    "-f",
                    ssh_seckey_filename,
                ]
            )
            if not (
                os.path.exists(ssh_seckey_filename)
                and os.path.exists(ssh_pubkey_filename)
            ):
                self.vm_failed.emit(f"Generating SSH key {ssh_seckey_filename} failed")
                return

        with open(ssh_pubkey_filename) as f:
            ssh_pubkey = f.read()

        # Make sure dangerzone VM exists
        self.task_title = "Setting up virtual machine"
        self.update("Initializing Dangerzone VM")
        multipass_list = self.exec_multipass_list()
        if not multipass_list:
            return

        exists = False
        for multipass_vm in multipass_list["list"]:
            if multipass_vm["name"] == "dangerzone":
                exists = True
                break

        if not exists:
            with open(
                os.path.join(self.multipass_resource_path, "cloud-config.yaml")
            ) as f:
                cloud_config_yaml = f.read().replace("PUT_SSH_PUBKEY_HERE", ssh_pubkey)

            cloud_config_filename = os.path.join(self.tmp_dir.name, "cloud-config.yaml")
            with open(cloud_config_filename, "w") as f:
                f.write(cloud_config_yaml)

            # Create new VM
            self.task_title = "Creating Dangerzone VM"
            self.update()
            self.exec_multipass_interactive(
                [
                    "launch",
                    "-c",
                    "2",
                    "-m",
                    "2G",
                    "-d",
                    "10G",
                    "-n",
                    "dangerzone",
                    "20.10",
                    "--cloud-init",
                    cloud_config_filename,
                ]
            )

            self.task_title = "Refreshing VMs list"
            multipass_list = self.exec_multipass_list()
            if not multipass_list:
                return

        # Make sure VM is started
        self.task_title = "Starting Dangerzone VM"
        self.update()

        vm = None
        for multipass_vm in multipass_list["list"]:
            if multipass_vm["name"] == "dangerzone":
                vm = multipass_vm
                break

        if vm["state"] != "Running":
            self.exec_multipass_interactive(["start", "dangerzone"])

        # TODO: Finish
        # - configure podman remote connection
        # - test it
        # - consider just using `multipass exec dangerzone -- podman` instead of ssh?

        self.vm_finished.emit()
