"""Detect installed programs without a generic shell."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def which(name: str) -> str | None:
    found = shutil.which(name)
    return found if found else None


def first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def run_version(executable: str, args: list[str], timeout: float) -> tuple[int, str]:
    """Run a fixed argv list (never a shell string)."""
    try:
        completed = subprocess.run(  # noqa: S603 - argv list, shell=False
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"{executable} timed out") from exc
    except OSError as exc:
        raise FileNotFoundError(str(exc)) from exc
    out = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, out.strip()[:2000]


def vscode_candidates() -> list[Path]:
    home = Path.home()
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        Path(p)
        for p in (
            which("code") or "",
            which("code.cmd") or "",
            f"{local}/Programs/Microsoft VS Code/bin/code.cmd" if local else "",
            f"{local}/Programs/Microsoft VS Code/Code.exe" if local else "",
            "/usr/bin/code",
            "/usr/local/bin/code",
            str(home / "AppData/Local/Programs/Microsoft VS Code/bin/code.cmd"),
            "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
        )
        if p
    ]


def blender_candidates() -> list[Path]:
    found: list[Path] = []
    w = which("blender")
    if w:
        found.append(Path(w))
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    foundation = Path(pf) / "Blender Foundation"
    if foundation.is_dir():
        for child in sorted(foundation.glob("Blender */blender.exe")):
            found.append(child)
    found.extend(
        [
            Path("/usr/bin/blender"),
            Path("/usr/local/bin/blender"),
            Path("/Applications/Blender.app/Contents/MacOS/Blender"),
        ]
    )
    return found


def godot_candidates() -> list[Path]:
    found: list[Path] = []
    for name in ("godot", "godot4", "Godot", "Godot_v4"):
        w = which(name)
        if w:
            found.append(Path(w))
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        found.extend(Path(local).glob("Godot*/Godot*.exe"))
    found.extend(
        [
            Path("/usr/bin/godot"),
            Path("/usr/local/bin/godot"),
            Path("/Applications/Godot.app/Contents/MacOS/Godot"),
        ]
    )
    return found
