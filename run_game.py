"""Launch the game.

Every run from source packages a new exe and starts it:
    .\\.venv\\Scripts\\python.exe run_game.py

The first development build writes versions\\0.0.1\\BeastboundArena.exe.
The next update writes versions\\0.0.2\\BeastboundArena.exe, then 0.0.3, and so on.
Alpha starts at 0.1.0. Open beta starts at 1.0.0.
Older versions stay in the versions folder.
"""

from __future__ import annotations

import subprocess
import sys
import traceback
from multiprocessing import freeze_support
from pathlib import Path


def _write_error(exc_text: str) -> None:
    if getattr(sys, "frozen", False):
        path = Path(sys.executable).resolve().parent / "error.log"
    else:
        path = Path("error.log")
    path.write_text(exc_text, encoding="utf-8")


def _explicit_version() -> str | None:
    if "--exe" not in sys.argv:
        return None
    index = sys.argv.index("--exe")
    if index + 1 < len(sys.argv) and not sys.argv[index + 1].startswith("-"):
        return sys.argv[index + 1]
    return None


def _launch_exe(exe_path: Path) -> None:
    print(f"Launching {exe_path}")
    subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))


def publish_and_launch() -> None:
    """Package the current game files as the next version, then start that exe."""
    from tools.packager import BuildError, build_version, find_root, next_version

    root = find_root()
    version = _explicit_version() or next_version(root)
    print(f"Updating the game as {version}...")
    try:
        built = build_version(version, print, force=True)
    except BuildError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    _launch_exe(built)


def _play() -> None:
    try:
        from game.main import main as game_main

        game_main()
    except Exception:
        _write_error(traceback.format_exc())
        raise


def main() -> None:
    if not getattr(sys, "frozen", False):
        root = Path(__file__).resolve().parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

    if "--smoke" in sys.argv:
        from game.arena_smoke import main as smoke_main

        raise SystemExit(smoke_main())
    if "--preview" in sys.argv:
        from game.preview import main as preview_main

        raise SystemExit(preview_main())

    if getattr(sys, "frozen", False):
        _play()
        return

    publish_and_launch()


if __name__ == "__main__":
    freeze_support()
    main()
