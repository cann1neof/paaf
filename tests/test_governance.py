# SPDX-License-Identifier: Apache-2.0
"""Governance rot-guard (FOUND-05 / FOUND-06 / FOUND-07).

This root-level test is the enforcement point that keeps the project's public
commitments from silently eroding:

  * The five governance docs must exist (FOUND-05 / FOUND-06).
  * DECISIONS.md must keep its required public-commitment sections (FOUND-05):
    the anti-feature list, the no-telemetry / no-accounts guarantee, the
    skills-security posture, the injection-defense constraint, and the open
    app-license question. Deleting a section turns CI red.
  * Every framework source file (``packages/*/src/**/*.py``) must carry the
    SPDX Apache-2.0 header as its first non-empty line (FOUND-07). This is the
    guard that keeps the Apache-2.0 provenance from rotting as later plans and
    phases add source files — a new unheadered file fails this test.

CI wiring note: ``pyproject.toml`` sets ``testpaths = ["packages"]``, so the
default ``uv run pytest`` run does NOT collect this root-level ``tests/`` file.
The Plan 02 ``suite`` CI job therefore invokes it EXPLICITLY
(``uv run pytest tests/test_governance.py ... --disable-socket``). Without that
explicit wiring the SPDX/FOUND-07 rot-guard would never fail the build. It runs
under ``--disable-socket`` — it touches only the local filesystem, no network.

Because the SPDX glob covers files created by sibling wave-2 plans, this test
becomes fully green only at the wave/phase gate once those files land — that is
expected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# tests/ lives at the repo root; the repo root is this file's parent's parent.
REPO_ROOT = Path(__file__).resolve().parents[1]

# The five governance docs an outsider must be able to find (FOUND-05/06/07).
REQUIRED_DOCS = ("LICENSE", "NOTICE", "CONTRIBUTING.md", "ARCHITECTURE.md", "DECISIONS.md")

# Substrings that prove each required DECISIONS.md public-commitment section is
# still present (FOUND-05). Matched case-insensitively so wording tweaks that
# preserve the commitment do not trip the guard, while deleting a section does.
DECISIONS_REQUIRED_MARKERS = (
    "anti-feature",              # the anti-feature list
    "no telemetry",             # PRIV-02 no-telemetry-ever commitment
    "no accounts",              # PRIV-01 no-accounts commitment
    "in-process",               # skills-security posture (in-process, no sandbox)
    "no sandbox",               # skills-security posture
    "injection",                # permission-model-as-only-injection-defense
    "agpl",                     # app-license open question (AGPL not chosen)
)

SPDX_HEADER = "# SPDX-License-Identifier: Apache-2.0"


def _source_files() -> list[Path]:
    """Every framework source file the SPDX header must cover."""
    return sorted(REPO_ROOT.glob("packages/*/src/**/*.py"))


def _first_nonempty_line(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return line
    return ""


@pytest.mark.parametrize("doc", REQUIRED_DOCS)
def test_required_governance_doc_exists(doc: str) -> None:
    """FOUND-05/06: each governance doc exists and is non-empty."""
    path = REPO_ROOT / doc
    assert path.is_file(), f"missing required governance doc: {doc}"
    assert path.stat().st_size > 0, f"governance doc is empty: {doc}"


def test_license_is_apache_2() -> None:
    """FOUND-07: LICENSE carries the Apache-2.0 text."""
    text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in text
    assert "Version 2.0" in text


@pytest.mark.parametrize("marker", DECISIONS_REQUIRED_MARKERS)
def test_decisions_has_required_section(marker: str) -> None:
    """FOUND-05: DECISIONS.md keeps each required public-commitment section."""
    text = (REPO_ROOT / "DECISIONS.md").read_text(encoding="utf-8").lower()
    assert marker in text, (
        f"DECISIONS.md is missing the required marker {marker!r} — a public "
        f"commitment section may have been dropped (FOUND-05)."
    )


def test_decisions_preserves_phase1_caveats() -> None:
    """DECISIONS.md is EXTENDED, not overwritten: Phase-1 caveats survive."""
    text = (REPO_ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    assert "D-05" in text and "D-12" in text, (
        "Phase-1 binding caveats (D-05 synthetic-speech, D-12 Apple-Silicon) "
        "must be preserved — DECISIONS.md is extended, never overwritten."
    )


def test_found_source_files_exist() -> None:
    """Sanity: there is at least one framework source file to guard."""
    assert _source_files(), "no packages/*/src/**/*.py files found to check"


@pytest.mark.parametrize(
    "src", _source_files(), ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_source_file_has_spdx_header(src: Path) -> None:
    """FOUND-07: every framework source file's first non-empty line is the SPDX id.

    This is the rot-guard: any new source file added by a later plan/phase
    without the Apache-2.0 header fails CI.
    """
    first = _first_nonempty_line(src)
    assert first == SPDX_HEADER, (
        f"{src.relative_to(REPO_ROOT)} is missing the SPDX Apache-2.0 header as "
        f"its first non-empty line (found: {first!r}). Add {SPDX_HEADER!r}."
    )
