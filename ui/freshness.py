"""Keep a long-running server on the latest code after a deploy.

Streamlit Community Cloud pulls new commits into the running server. Page
scripts are re-read on every run, but modules they import (``core.samples``,
``ui.theme`` and so on) stay in ``sys.modules`` from before the update, so a
new page can import a name that the old module does not have yet.

:func:`refresh_changed_modules` runs at the top of ``app.py`` on every rerun.
It fingerprints the project's source files (modification times and count) and,
when the fingerprint changes, removes the project's modules from
``sys.modules`` so the imports that follow load the current files.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterable
from pathlib import Path

PACKAGES = ("core", "ai", "ui", "exports", "bench", "data")


def code_signature(root: Path, packages: Iterable[str] = PACKAGES) -> tuple[int, int]:
    """Newest modification time and number of .py files under the project packages."""
    files = [p for pkg in packages for p in (root / pkg).rglob("*.py")]
    return max((p.stat().st_mtime_ns for p in files), default=0), len(files)


def refresh_changed_modules(root: Path, state: dict, packages: Iterable[str] = PACKAGES) -> bool:
    """Forget the project's imported modules if its source files changed. Returns True if it did.

    ``state`` must persist for the life of the process (``app.py`` passes a
    ``st.cache_resource`` dict). The first call in a process always refreshes,
    because modules imported before it may be older than the files on disk.
    """
    packages = tuple(packages)
    signature = code_signature(root, packages)
    if state.get("signature") == signature:
        return False
    lock = state.setdefault("lock", threading.Lock())
    with lock:
        if state.get("signature") == signature:
            return False
        for name in [n for n in sys.modules if n.split(".")[0] in packages]:
            del sys.modules[name]
        state["signature"] = signature
    return True
