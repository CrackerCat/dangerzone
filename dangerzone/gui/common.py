import os
import platform
import subprocess
import shlex
import pipes
from PySide2 import QtCore, QtGui, QtWidgets
from colorama import Fore

if platform.system() == "Darwin":
    import CoreServices
    import LaunchServices
    import plistlib

elif platform.system() == "Linux":
    import grp
    import getpass
    from xdg.DesktopEntry import DesktopEntry

from .docker_installer import is_docker_ready
from ..settings import Settings


class GuiCommon(object):
    """
    The GuiCommon class is a singleton of shared functionality for the GUI
    """

    def __init__(self, app, global_common):
        # Qt app
        self.app = app

        # Global common singleton
        self.global_common = global_common

        # Preload font
        self.fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

        # Preload list of PDF viewers on computer
        self.pdf_viewers = self._find_pdf_viewers()

    def get_window_icon(self):
        if platform.system() == "Windows":
            path = self.global_common.get_resource_path("dangerzone.ico")
        else:
            path = self.global_common.get_resource_path("icon.png")
        return QtGui.QIcon(path)

    def open_pdf_viewer(self, filename):
        if self.global_common.settings.get("open_app") in self.pdf_viewers:
            if platform.system() == "Darwin":
                # Get the PDF reader bundle command
                bundle_identifier = self.pdf_viewers[
                    self.global_common.settings.get("open_app")
                ]
                args = ["open", "-b", bundle_identifier, filename]

                # Run
                args_str = " ".join(pipes.quote(s) for s in args)
                print(Fore.YELLOW + "> " + Fore.CYAN + args_str)
                subprocess.run(args)

            elif platform.system() == "Linux":
                # Get the PDF reader command
                args = shlex.split(
                    self.pdf_viewers[self.global_common.settings.get("open_app")]
                )
                # %f, %F, %u, and %U are filenames or URLS -- so replace with the file to open
                for i in range(len(args)):
                    if (
                        args[i] == "%f"
                        or args[i] == "%F"
                        or args[i] == "%u"
                        or args[i] == "%U"
                    ):
                        args[i] = filename

                # Open as a background process
                args_str = " ".join(pipes.quote(s) for s in args)
                print(Fore.YELLOW + "> " + Fore.CYAN + args_str)
                subprocess.Popen(args)

    def _find_pdf_viewers(self):
        pdf_viewers = {}

        if platform.system() == "Darwin":
            # Get all installed apps that can open PDFs
            bundle_identifiers = LaunchServices.LSCopyAllRoleHandlersForContentType(
                "com.adobe.pdf", CoreServices.kLSRolesAll
            )
            for bundle_identifier in bundle_identifiers:
                # Get the filesystem path of the app
                res = LaunchServices.LSCopyApplicationURLsForBundleIdentifier(
                    bundle_identifier, None
                )
                if res[0] is None:
                    continue
                app_url = res[0][0]
                app_path = str(app_url.path())

                # Load its plist file
                plist_path = os.path.join(app_path, "Contents/Info.plist")

                # Skip if there's not an Info.plist
                if not os.path.exists(plist_path):
                    continue

                with open(plist_path, "rb") as f:
                    plist_data = f.read()

                plist_dict = plistlib.loads(plist_data)

                if (
                    plist_dict.get("CFBundleName")
                    and plist_dict["CFBundleName"] != "Dangerzone"
                ):
                    pdf_viewers[plist_dict["CFBundleName"]] = bundle_identifier

        elif platform.system() == "Linux":
            # Find all .desktop files
            for search_path in [
                "/usr/share/applications",
                "/usr/local/share/applications",
                os.path.expanduser("~/.local/share/applications"),
            ]:
                try:
                    for filename in os.listdir(search_path):
                        full_filename = os.path.join(search_path, filename)
                        if os.path.splitext(filename)[1] == ".desktop":

                            # See which ones can open PDFs
                            desktop_entry = DesktopEntry(full_filename)
                            if (
                                "application/pdf" in desktop_entry.getMimeTypes()
                                and desktop_entry.getName() != "dangerzone"
                            ):
                                pdf_viewers[
                                    desktop_entry.getName()
                                ] = desktop_entry.getExec()

                except FileNotFoundError:
                    pass

        return pdf_viewers
