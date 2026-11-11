"""Tests for reloading the project's modules after the code changes on disk."""

from __future__ import annotations

import importlib
import os
import sys

from ui.freshness import code_signature, refresh_changed_modules


def _write_package(root, value: int) -> None:
    pkg = root / "vdtmp_pkg"
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text(f"VALUE = {value}\n", encoding="utf-8")


def test_changed_files_are_loaded_fresh(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_package(tmp_path, 1)
    state: dict = {}
    try:
        assert refresh_changed_modules(tmp_path, state, ["vdtmp_pkg"])  # first call always refreshes
        assert importlib.import_module("vdtmp_pkg.mod").VALUE == 1
        assert not refresh_changed_modules(tmp_path, state, ["vdtmp_pkg"])  # nothing changed
        assert "vdtmp_pkg.mod" in sys.modules

        # A deploy rewrites the file: the old module would otherwise stay cached.
        _write_package(tmp_path, 2)
        mod = tmp_path / "vdtmp_pkg" / "mod.py"
        later = os.stat(mod).st_mtime_ns + 5_000_000_000
        os.utime(mod, ns=(later, later))
        importlib.invalidate_caches()
        assert refresh_changed_modules(tmp_path, state, ["vdtmp_pkg"])
        assert "vdtmp_pkg.mod" not in sys.modules and "vdtmp_pkg" not in sys.modules
        assert importlib.import_module("vdtmp_pkg.mod").VALUE == 2
    finally:
        for name in [n for n in sys.modules if n.startswith("vdtmp_pkg")]:
            del sys.modules[name]


def test_new_files_change_the_signature(tmp_path):
    _write_package(tmp_path, 1)
    before = code_signature(tmp_path, ["vdtmp_pkg"])
    (tmp_path / "vdtmp_pkg" / "extra.py").write_text("X = 1\n", encoding="utf-8")
    assert code_signature(tmp_path, ["vdtmp_pkg"])[1] == before[1] + 1


def test_other_packages_are_left_alone(tmp_path):
    import json

    _write_package(tmp_path, 1)
    refresh_changed_modules(tmp_path, {}, ["vdtmp_pkg"])
    assert sys.modules["json"] is json
