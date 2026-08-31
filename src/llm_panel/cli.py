"""Console entry points: exec the packaged copy of the corresponding single-file tool."""

import runpy
import sys
from importlib.resources import files


def _run(name: str) -> None:
    script = files("llm_panel") / "_scripts" / name
    sys.argv[0] = name
    runpy.run_path(str(script), run_name="__main__")


def llm_panel() -> None:
    _run("llm-panel")


def panel_report() -> None:
    _run("panel-report")


def panel_triage() -> None:
    _run("panel-triage")
