"""Registers the markmark:// link so the website's Open button can start the app on this laptop."""
import shlex
import subprocess
import sys
from pathlib import Path


def _windows():
    import winreg
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else Path(sys.executable)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\markmark") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Markmark")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\markmark\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{runner}" -m markmark')


def _linux():
    folder = Path.home() / ".local/share/applications"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "markmark.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Markmark\n"
        f"Exec={shlex.quote(sys.executable)} -m markmark\n"
        "MimeType=x-scheme-handler/markmark;\nNoDisplay=true\n", encoding="utf-8")
    subprocess.run(["xdg-mime", "default", "markmark.desktop", "x-scheme-handler/markmark"], check=False)


def register():
    """Best effort: the app works without the link. macOS would need a signed app bundle, so it is skipped."""
    try:
        if sys.platform == "win32":
            _windows()
        elif sys.platform.startswith("linux"):
            _linux()
    except OSError:
        pass
