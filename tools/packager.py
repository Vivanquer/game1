"""Build a standalone game exe, or build this tool into BuildGame.exe.

Each version is written to versions/<name>/ and older versions are left in place.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,40}$")


class BuildError(RuntimeError):
    pass


def find_root() -> Path:
    starts: list[Path] = []
    if getattr(sys, "frozen", False):
        starts.append(Path(sys.executable).resolve().parent)
    else:
        starts.append(Path(__file__).resolve().parent.parent)
    starts.append(Path.cwd())
    seen: set[Path] = set()
    for start in starts:
        for candidate in [start, *list(start.parents)[:4]]:
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "run_game.py").is_file() and (candidate / "game" / "data" / "actions.json").is_file():
                return candidate
    raise BuildError("Could not find the game project. Keep BuildGame.exe next to run_game.py.")


def find_python(root: Path) -> str:
    venv = root / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        return str(venv)
    attempts = (["py", "-3"], ["python"], ["python3"])
    for command in attempts:
        try:
            result = subprocess.run(
                command + ["-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise BuildError("Python was not found. Install Python, or keep the .venv folder in the project.")


def exe_stem(root: Path) -> str:
    hero = json.loads((root / "game" / "data" / "hero.json").read_text(encoding="utf-8"))
    raw = str(hero.get("title") or "Beastbound Arena")
    safe = re.sub(r"[^A-Za-z0-9]+", "", raw)
    return safe or "BeastboundArena"


def next_version(root: Path) -> str:
    """Next label for the current stage.

    Development counts 0.0.1, 0.0.2, 0.0.3, and so on.
    Alpha starts at 0.1.0. Open beta starts at 1.0.0.
    Later updates in those stages add one to the last number.
    """
    stage = _version_stage(root)
    major, minor, first = _STAGE_LINES[stage]
    highest = first - 1
    pattern = re.compile(rf"^{major}\.{minor}\.(\d+)$")
    versions_dir = root / "versions"
    if versions_dir.is_dir():
        for child in versions_dir.iterdir():
            match = pattern.fullmatch(child.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"{major}.{minor}.{highest + 1}"


_STAGE_LINES = {
    "development": (0, 0, 1),
    "alpha": (0, 1, 0),
    "beta": (1, 0, 0),
}


def _version_stage(root: Path) -> str:
    path = root / "game" / "data" / "version.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return "development"
    if not isinstance(data, dict):
        return "development"
    stage = str(data.get("stage", "development")).strip().lower().replace("_", " ")
    if stage in ("open beta", "open-beta"):
        return "beta"
    return stage if stage in _STAGE_LINES else "development"


def remember_version(root: Path, version: str) -> None:
    path = root / "game" / "data" / "version.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data["name"] = version
    stage = str(data.get("stage", "")).strip()
    data["stage"] = stage or "development"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def ensure_build_tools(python: str, root: Path, log) -> None:
    probe = subprocess.run([python, "-c", "import pygame, PyInstaller"], capture_output=True, text=True)
    if probe.returncode == 0:
        return
    log("Installing pygame-ce and pyinstaller into the project environment...")
    result = subprocess.run(
        [python, "-m", "pip", "install", "-r", str(root / "requirements.txt")],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        log(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            log(result.stderr.rstrip())
        raise BuildError("Could not install pygame-ce and pyinstaller.")


def run_smoke(python: str, root: Path, log) -> None:
    log("Checking actions, monsters, and arena rules...")
    result = subprocess.run(
        [python, "run_game.py", "--smoke"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        log(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            log(result.stderr.rstrip())
        raise BuildError("The game failed its checks, so no exe was built.")


def stage_data(root: Path, version: str) -> Path:
    staging = root / "build" / "staging" / version / "data"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(root / "game" / "data", staging)
    try:
        current = json.loads((root / "game" / "data" / "version.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        current = {}
    if not isinstance(current, dict):
        current = {}
    payload = {
        "name": version,
        "stage": current.get("stage", "development"),
        "built": datetime.now().isoformat(timespec="seconds"),
    }
    (staging / "version.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return staging


def stream_command(command: list[str], cwd: Path, log) -> None:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        log(line.rstrip())
    code = process.wait()
    if code != 0:
        raise BuildError(f"Command exited with {code}.")


def build_version(version: str, log, force: bool = False) -> Path:
    version = version.strip()
    if not VERSION_RE.match(version):
        raise BuildError("Version names use letters, numbers, dots, dashes, and underscores.")
    root = find_root()
    python = find_python(root)
    log(f"Project: {root}")
    log(f"Python: {python}")
    ensure_build_tools(python, root, log)
    run_smoke(python, root, log)

    stem = exe_stem(root)
    out_dir = root / "versions" / version
    out_dir.mkdir(parents=True, exist_ok=True)
    exe_path = out_dir / f"{stem}.exe"
    if exe_path.exists() and not force:
        raise BuildError(f"{exe_path} already exists. Choose another name, or overwrite it.")

    staging = stage_data(root, version)
    work = root / "build" / "pyi" / version
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    spec_dir = root / "build" / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    assets = root / "game" / "assets"
    log(f"Packaging {stem}.exe ...")
    stream_command(
        [
            python,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onefile",
            "--name",
            stem,
            "--distpath",
            str(out_dir),
            "--workpath",
            str(work),
            "--specpath",
            str(spec_dir),
            "--paths",
            str(root),
            "--add-data",
            f"{staging}{os.pathsep}data",
            "--add-data",
            f"{assets}{os.pathsep}assets",
            "--collect-all",
            "pygame",
            str(root / "run_game.py"),
        ],
        root,
        log,
    )
    if not exe_path.is_file():
        raise BuildError(f"PyInstaller finished without writing {exe_path}.")
    note = out_dir / "VERSION.txt"
    note.write_text(
        f"version: {version}\nexe: {stem}.exe\nbuilt: {datetime.now().isoformat(timespec='seconds')}\n",
        encoding="utf-8",
    )
    log(f"Built {exe_path}")
    remember_version(root, version)
    return exe_path


def build_self(log) -> Path:
    root = find_root()
    python = find_python(root)
    log(f"Project: {root}")
    log(f"Python: {python}")
    ensure_build_tools(python, root, log)
    work = root / "build" / "pyi-packager"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    spec_dir = root / "build" / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    log("Packaging BuildGame.exe ...")
    stream_command(
        [
            python,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onefile",
            "--name",
            "BuildGame",
            "--distpath",
            str(root),
            "--workpath",
            str(work),
            "--specpath",
            str(spec_dir),
            str(root / "tools" / "packager.py"),
        ],
        root,
        log,
    )
    exe_path = root / "BuildGame.exe"
    if not exe_path.is_file():
        raise BuildError("PyInstaller finished without writing BuildGame.exe.")
    log(f"Built {exe_path}")
    return exe_path


def launch_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    root_dir = find_root()
    window = tk.Tk()
    window.title("Beastbound Arena version builder")
    window.geometry("720x520")
    window.minsize(640, 420)

    header = ttk.Frame(window, padding=12)
    header.pack(fill="x")
    ttk.Label(header, text="Build a standalone game exe", font=("Segoe UI", 16, "bold")).pack(anchor="w")
    ttk.Label(
        header,
        text="Each update gets the next number under versions\\. Development is 0.0.1, 0.0.2, and so on.",
        wraplength=680,
    ).pack(anchor="w", pady=(4, 0))

    form = ttk.Frame(window, padding=(12, 0, 12, 8))
    form.pack(fill="x")
    ttk.Label(form, text="Version").pack(side="left")
    version_var = tk.StringVar(value=next_version(root_dir))
    entry = ttk.Entry(form, textvariable=version_var, width=24)
    entry.pack(side="left", padx=8)

    buttons = ttk.Frame(window, padding=(12, 0, 12, 8))
    buttons.pack(fill="x")
    build_button = ttk.Button(buttons, text="Build exe")
    play_button = ttk.Button(buttons, text="Play this version")
    folder_button = ttk.Button(buttons, text="Open versions folder")
    build_button.pack(side="left")
    play_button.pack(side="left", padx=8)
    folder_button.pack(side="left")

    log_widget = scrolledtext.ScrolledText(window, height=18, font=("Consolas", 10), state="disabled")
    log_widget.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    messages: queue.Queue[tuple[str, str]] = queue.Queue()
    building = {"value": False}

    def write(line: str) -> None:
        log_widget.configure(state="normal")
        log_widget.insert("end", line + "\n")
        log_widget.see("end")
        log_widget.configure(state="disabled")

    def finish_ok(path: str) -> None:
        building["value"] = False
        build_button.configure(state="normal")
        write(f"Ready: {path}")
        messagebox.showinfo("Build finished", f"Created\n{path}")

    def finish_error(message: str) -> None:
        building["value"] = False
        build_button.configure(state="normal")
        write(message)
        messagebox.showerror("Build failed", message)

    def poll() -> None:
        try:
            while True:
                kind, payload = messages.get_nowait()
                if kind == "line":
                    write(payload)
                elif kind == "done":
                    finish_ok(payload)
                elif kind == "error":
                    finish_error(payload)
        except queue.Empty:
            pass
        window.after(100, poll)

    def start_build() -> None:
        if building["value"]:
            return
        version = version_var.get().strip()
        if not VERSION_RE.match(version):
            messagebox.showerror(
                "Version name",
                "Use letters, numbers, dots, dashes, or underscores. For example 0.0.2.",
            )
            return
        exe_path = root_dir / "versions" / version / f"{exe_stem(root_dir)}.exe"
        force = False
        if exe_path.exists():
            force = messagebox.askyesno("Overwrite", f"{exe_path.name} already exists for {version}. Replace it?")
            if not force:
                return
        building["value"] = True
        build_button.configure(state="disabled")
        write(f"Building {version}...")

        def worker() -> None:
            try:
                path = build_version(version, lambda line: messages.put(("line", line)), force=force)
            except Exception as exc:
                messages.put(("error", str(exc)))
            else:
                messages.put(("done", str(path)))

        threading.Thread(target=worker, daemon=True).start()

    def play() -> None:
        version = version_var.get().strip()
        exe_path = root_dir / "versions" / version / f"{exe_stem(root_dir)}.exe"
        if not exe_path.is_file():
            messagebox.showerror("Not built yet", f"There is no {exe_path.name} for {version}.")
            return
        subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))

    def open_folder() -> None:
        folder = root_dir / "versions"
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)  # type: ignore[attr-defined]

    build_button.configure(command=start_build)
    play_button.configure(command=play)
    folder_button.configure(command=open_folder)
    window.after(100, poll)
    entry.focus_set()
    window.mainloop()


def main() -> int:
    try:
        if "--build-self" in sys.argv:
            build_self(print)
            return 0
        if "--version" in sys.argv:
            index = sys.argv.index("--version")
            if index + 1 >= len(sys.argv):
                raise BuildError("Pass a version name after --version.")
            build_version(sys.argv[index + 1], print, force="--force" in sys.argv)
            return 0
    except BuildError as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1
    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
