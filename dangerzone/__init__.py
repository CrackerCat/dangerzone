import os
import sys

if "DANGERZONE_MODE" in os.environ:
    mode = os.environ["DANGERZONE_MODE"]
else:
    basename = os.path.basename(sys.argv[0])
    if basename == "dangerzone-container" or basename == "dangerzone-container.exe":
        mode = "container"
    elif basename == "dangerzone-cli" or basename == "dangerzone-cli.exe":
        mode = "cli"
    else:
        mode = "gui"

if mode == "container":
    from .container import container_main as main
elif mode == "cli":
    from .cli import cli_main as main
else:
    from .gui import gui_main as main
