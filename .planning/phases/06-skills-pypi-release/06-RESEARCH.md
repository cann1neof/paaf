# Phase 6: Skills & PyPI Release — Research

## Executive Summary & User Intent

### Goal
Phase 06 enables users to install, manage, and execute skills from git repositories or local paths, publishes the framework to PyPI as a single monolithic `paaf` package, and builds a comprehensive public documentation site. A developer with no prior repo access can run `pip install paaf`, build an agent mesh, install a skill from a git URL, inspect verbatim prompts, and read complete documentation covering everything that exists at this phase.

### Core Value Alignment
- **Nothing Hidden:** Skill prompt additions are appended as inspectable, verbatim persona fragments (`--- Skill: <name> ---`) verified by `paaf prompt` and `PromptComposer`.
- **Honest Security Posture (SKILL-05):** Skills run in-process with no sandbox. Manifest permissions provide disclosure and transparency, not process isolation. MCP servers are explicitly recommended for untrusted code.
- **Developer Ownership:** Skills are stored locally inside the project (`.paaf/skills/<skill_name>/`), managed via monotonic `paaf.yaml` configuration, and support instant hot-reloading (enable/disable) without restarting the application or deleting code.

---

## Architecture & Technical Approaches

```
                     +----------------------------------+
                     |  paaf skill install <git-url>   |
                     +----------------------------------+
                                      |
                                      v
                     +----------------------------------+
                     | 1. Clone into .paaf/staging/<id> |
                     +----------------------------------+
                                      |
                                      v
                     +----------------------------------+
                     | 2. Validate skill.yaml Manifest |
                     +----------------------------------+
                                      |
                                      v
                     +----------------------------------+
                     | 3. Permission & Security Review  |
                     |    (Disclosure: No Sandbox)      |
                     +----------------------------------+
                                      |
                                      v
                     +----------------------------------+
                     | 4. Install Dependencies (uv/pip) |
                     +----------------------------------+
                                      |
                                      v
                     +----------------------------------+
                     | 5. Atomic Move -> .paaf/skills/  |
                     +----------------------------------+
                                      |
                                      v
                     +----------------------------------+
                     | 6. Hot-Reload Registry & Prompt  |
                     +----------------------------------+
```

### 1. Skill Manifest & Structure (`skill.yaml`)
A skill is a folder or git repository containing a root `skill.yaml` file, a persona fragment (e.g. `prompt.md`), and autodiscovered `@tool` Python functions.

**Manifest Specification (`SkillManifest`):**
```yaml
name: weather_skill
version: 0.1.0
description: Fetch current weather and forecasts for a given location.
persona_fragment: prompt.md
tools:
  - get_weather
permissions:
  get_weather: observe
dependencies:
  - httpx>=0.27.0
```

### 2. Skill Manager & Storage Layout
- **Storage Location (D-05):** `.paaf/skills/<skill_name>/` inside project root.
- **Staging Location (D-06):** `.paaf/staging/<tmp_id>/` used during installation. Retained on failure for debugging (D-08).
- **Configuration Persistence (D-10):** Registered in `paaf.yaml` under `skills: <skill_name>` key.

```python
class SkillConfig(BaseModel):
    """Configuration for an installed skill in paaf.yaml."""
    model_config = {"extra": "forbid"}

    enabled: bool = Field(
        True, json_schema_extra={"reload_tier": ReloadTier.HOT}
    )
    path: str = Field(
        ..., json_schema_extra={"reload_tier": ReloadTier.HOT}
    )
    permissions: dict[str, PermissionTier] = Field(
        default_factory=dict,
        json_schema_extra={"reload_tier": ReloadTier.HOT},
    )
```

### 3. Tool Discovery & Namespacing
- **Autodiscovery (D-02):** When an enabled skill is loaded, Python files inside `.paaf/skills/<skill_name>/` are scanned. Functions decorated with `@tool` (from `paaf_llm.tools.decorator`) are registered into the unified `ToolRegistry`.
- **Namespacing & Collision Handling (D-04):** Tools use flat names by default when unique (e.g. `get_weather`). If a tool name collides with an already registered tool in the registry, it is automatically prefixed with `skill_<skill_name>_<tool_name>`.

### 4. Persona Composition & Seam Integration
- **Persona Fragment (D-03):** Stored in `prompt.md` or `persona.md`.
- **Composition Seam:** Replaces the Phase 3 D-09 stub in `load_skill_fragments` inside `paaf_llm.cli`. Reads enabled skills from `AppConfig`, loads their declared persona fragment, and prefixes each fragment with a clear section header:
  `--- Skill: <name> ---`
- **Verbatim Prompt Contract:** Prompt fragments pass cleanly into `PromptComposer.compose(base_prompt, fragments, mesh_fragments)` without string rewriting or hidden defensive wrappers (PERS-04/05).

### 5. Monolithic PyPI Package (`paaf`)
- **Package Layout (D-13):** A top-level workspace package `packages/paaf` is published as the single `paaf` wheel on PyPI. It bundles `paaf_core`, `paaf_trace`, and `paaf_llm` into a single installable wheel, exposing the `paaf` CLI entry point.
- **Dependencies & Extras:** Base dependencies include `pydantic`, `pyyaml`, `click`, `rich`, `aiosqlite`. Heavy LLM engine dependencies (`langchain`, `langgraph`, provider adapters) sit behind the optional `[engine]` extra (`pip install 'paaf[engine]'`).

### 6. Documentation Site Toolchain & Architecture
- **Stack (D-14):** Built using `mkdocs-material` configured via root `mkdocs.yml` and docs source files in `docs/`.
- **Scope Disclosure (D-15, SKILL-05):** Explicitly documents existing features (mesh, prompt inspector, tools, MCP, skills, PyPI CLI) while stating plainly that voice, appliance, and desktop components do not exist yet (landing in Phase 13).

---

## Key Patterns & Code Examples

### 1. Skill Manifest Pydantic Model (`paaf_llm/skills/manifest.py`)
```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
from paaf_core.config import PermissionTier
import yaml

class SkillManifest(BaseModel):
    """Declarative specification for a PAAF skill (skill.yaml)."""
    model_config = {"extra": "forbid"}

    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    version: str
    description: str = ""
    persona_fragment: str = "prompt.md"
    tools: list[str] = Field(default_factory=list)
    permissions: dict[str, PermissionTier] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)

    @classmethod
    def load(cls, skill_dir: Path) -> SkillManifest:
        manifest_path = skill_dir / "skill.yaml"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Missing skill.yaml in {skill_dir}")
        with open(manifest_path, "rb") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)
```

### 2. Skill Tool Autodiscovery & Loading (`paaf_llm/skills/loader.py`)
```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from paaf_llm.registry import ToolRegistry
from paaf_llm.tools.decorator import TOOL_METADATA_ATTR

def load_skill_tools(skill_dir: Path, skill_name: str, registry: ToolRegistry) -> None:
    """Discover @tool decorated functions in skill Python files and register them."""
    py_files = sorted(skill_dir.glob("*.py"))
    for py_file in py_files:
        if py_file.name.startswith("_"):
            continue
        module_name = f"paaf_skill_{skill_name}_{py_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise RuntimeError(f"Failed to load skill file {py_file}: {exc}") from exc

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and hasattr(attr, TOOL_METADATA_ATTR):
                tool_spec = getattr(attr, TOOL_METADATA_ATTR)
                registry.register(
                    spec=tool_spec,
                    source=f"skill:{skill_name}",
                    func=attr,
                )
```

### 3. Interactive Permission Review & Disclosure (`paaf_llm/skills/installer.py`)
```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import click
from rich.console import Console
from paaf_llm.skills.manifest import SkillManifest

SECURITY_DISCLOSURE = (
    "SECURITY NOTICE: Skills run in-process with no sandbox; manifest permissions "
    "provide disclosure, not process isolation. For untrusted code, use MCP servers."
)

def render_permission_review(manifest: SkillManifest, console: Console) -> None:
    console.print(f"[bold]Skill:[/bold] {manifest.name} (v{manifest.version})")
    console.print(f"[bold]Description:[/bold] {manifest.description}")
    console.print("[bold]Provided Tools & Requested Permissions:[/bold]")
    for tool_name in manifest.tools:
        tier = manifest.permissions.get(tool_name, "act")
        console.print(f"  - {tool_name}: [cyan]{tier}[/cyan]")
    if manifest.dependencies:
        console.print(f"[bold]Python Dependencies:[/bold] {', '.join(manifest.dependencies)}")
    console.print(f"\n[yellow]{SECURITY_DISCLOSURE}[/yellow]\n")

def confirm_installation(manifest: SkillManifest, auto_approve: bool) -> bool:
    if auto_approve:
        return True
    if not click.get_text_stream("stdin").isatty():
        raise click.ClickException(
            "Non-interactive session requires --yes or --approve-permissions flag."
        )
    return click.confirm("Do you approve these permissions and wish to install?")
```

---

## Dependencies & Ecosystem Integration

### 1. PyPI Packaging & Monolithic Package Layout
To publish `paaf` as a single monolithic package bundling core, trace, and llm:
```toml
# packages/paaf/pyproject.toml
[project]
name = "paaf"
version = "0.1.0"
description = "Personalized Agentic Assistant Framework"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.13",
    "pyyaml>=6.0.3",
    "click>=8.4",
    "rich>=15",
    "aiosqlite>=0.20",
]

[project.optional-dependencies]
engine = [
    "langchain==1.3.14",
    "langgraph==1.2.10",
    "langchain-ollama==1.1.0",
    "langchain-anthropic==1.4.8",
    "langchain-openai==1.4.1",
]

[project.scripts]
paaf = "paaf_llm.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = [
    "../paaf-core/src/paaf_core",
    "../paaf-trace/src/paaf_trace",
    "../paaf-llm/src/paaf_llm",
]
```

### 2. Documentation Stack Configuration (`mkdocs.yml`)
```yaml
site_name: PAAF Documentation
site_description: Personalized Agentic Assistant Framework
theme:
  name: material
  palette:
    scheme: slate
    primary: indigo
  features:
    - navigation.sections
    - navigation.expand
    - content.code.copy
nav:
  - Getting Started:
    - Overview: index.md
    - Quickstart: getting-started/quickstart.md
  - Configuration:
    - YAML Schema: configuration/paaf-yaml.md
  - Architecture:
    - Agent Mesh: architecture/agent-mesh.md
  - Skills:
    - Authoring & Security: skills/authoring.md
  - API Reference: api/reference.md
  - Roadmap: roadmap/scope.md
plugins:
  - search
```

---

## Validation & Testing Strategy

### Validation Architecture (Nyquist Framework)

The validation strategy enforces complete test coverage across unit, integration, packaging, and documentation builds.

```
+-----------------------------------------------------------------------+
|                              CI Pipeline                              |
+-----------------------------------------------------------------------+
|  1. Unit Tests (pytest)                                               |
|     - Manifest validation, tool autodiscovery, namespacing          |
|     - Prompt composition, enable/disable toggle                       |
+-----------------------------------------------------------------------+
|  2. Integration Tests                                                 |
|     - paaf skill install staging & failure rollback                   |
|     - Hot-reloading in ToolRegistry and PromptComposer                |
+-----------------------------------------------------------------------+
|  3. Monolithic Wheel Clean-Venv Gate (check_release_venv.sh)          |
|     - Build paaf monolithic wheel                                     |
|     - Install into isolated clean venv outside repo                   |
|     - Run end-to-end smoke tests (CLI prompt, agent mesh, skills)     |
+-----------------------------------------------------------------------+
|  4. Documentation Strict Build (mkdocs build --strict)                |
|     - Verify zero dead links, valid markdown syntax                   |
+-----------------------------------------------------------------------+
```

#### Test Matrix & Verification Commands
1. **Unit & Integration Tests:**
   `uv run pytest packages/paaf-llm/tests/test_skills.py`
2. **Clean-Venv Monolithic Wheel Verification (D-16):**
   `./scripts/check_release_venv.sh`
3. **Documentation Site Validation (D-14):**
   `uv run mkdocs build --strict`

---

## Risks, Edge Cases & Landmines

| Risk / Edge Case | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Dynamic Python Import Pollution** | Importing skill `.py` files from `.paaf/skills/` could pollute `sys.modules` or clobber framework names. | Prefix dynamically loaded module names with `paaf_skill_<skill_name>_` and load explicitly via `importlib.util.spec_from_file_location`. |
| **Dependency Install Failures** | `uv pip install` / `pip install` failing mid-installation leaves venv or skill directory corrupt. | Perform dependency installation in staging directory (`.paaf/staging/<id>`) before atomic rename to `.paaf/skills/<skill_name>/`. Retain staging folder on failure for debugging (D-08). |
| **Non-Interactive Install Freeze** | CLI `paaf skill install` without `--yes` hanging indefinitely in non-interactive CI environments. | Check `click.get_text_stream("stdin").isatty()`. Require `--yes` or `--approve-permissions` flag when non-interactive (D-12). |
| **Prompt Inspection Byte Drift** | Skill persona headers or newline formats causing `paaf prompt` output to mismatch actual system prompt sent to model. | Route all skill persona loading through `load_skill_fragments` seam feeding `PromptComposer`, asserting `compose` output matches segment list byte-for-byte. |
| **Unstated Scope Expectations** | Users assuming voice or desktop capabilities are present in Phase 6. | Maintain an explicit "Roadmap & What Exists" page in MkDocs and clear CLI messages stating voice/appliance components land in Phase 13 (D-15). |

---

## RESEARCH COMPLETE
