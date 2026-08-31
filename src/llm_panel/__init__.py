"""Packaged shell around the single-file tools.

The canonical source of each tool is the executable file at the repository root
(`llm-panel`, `panel-report`, `panel-triage`); the wheel carries verbatim copies under
``llm_panel/_scripts/`` and `llm_panel.cli` execs them, so a pip/uvx install and a
curl'd single file run identical code.
"""
