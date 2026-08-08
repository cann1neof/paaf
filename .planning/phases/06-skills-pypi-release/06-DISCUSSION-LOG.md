# Phase 6: Skills & PyPI Release - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-08
**Phase:** 06-skills-pypi-release
**Areas discussed:** Skill Manifest Format & Tool Discovery, Skill Installation & Dependency Rollback, Interactive Permission Review & Enable/Disable State, PyPI Packaging & Documentation Site Stack

---

## Skill Manifest Format & Tool Discovery

| Option | Description | Selected |
|--------|-------------|----------|
| `skill.yaml` in root | Dedicated YAML manifest with name, version, persona_fragment, tools, permissions, deps | ✓ |
| `pyproject.toml` | Integrated standard Python packaging configuration | |
| You decide | Clean dedicated manifest | |

**User's choice:** `skill.yaml` in root — dedicated YAML manifest with name, version, persona_fragment, tools, permissions, deps

| Option | Description | Selected |
|--------|-------------|----------|
| Explicitly listed in `skill.yaml` | Explicit module/function path listing under `tools:` | |
| Autodiscovered `@tool` functions | All Python files inside skill folder scanned for `@tool` | ✓ |
| You decide | Explicit tools list in manifest | |

**User's choice:** Autodiscovered `@tool` functions in all Python files inside the skill directory

| Option | Description | Selected |
|--------|-------------|----------|
| Inlined in `skill.yaml` | Inlined persona fragment string in manifest | |
| Separate `prompt.md`/`persona.md` file | Dedicated file in skill folder root | ✓ |
| You decide | Inline in `skill.yaml` | |

**User's choice:** Separate file `prompt.md` / `persona.md` in the skill folder root

| Option | Description | Selected |
|--------|-------------|----------|
| Flat names by default | Auto-prefixed with `skill_<skill_name>_<tool>` on collision | ✓ |
| Always prefixed | Always prefixed with `skill_<skill_name>_<tool_name>` | |
| You decide | Flat by default, prefix on collision | |

**User's choice:** Flat names by default, auto-prefixed with `skill_<skill_name>_<tool>` on name collision (matches D-11)

---

## Skill Installation, Git Cloning & Dependency Rollback

| Option | Description | Selected |
|--------|-------------|----------|
| Global `~/.paaf/skills/` | Global user installs with project-local override | |
| Strictly project-local `.paaf/skills/` | Installed in project root `.paaf/skills/<skill_name>/` | ✓ |
| You decide | Global with project-local override | |

**User's choice:** Strictly project-local `.paaf/skills/<skill_name>/` in project root

| Option | Description | Selected |
|--------|-------------|----------|
| Clone to temporary staging folder | Validate manifest & requirements, then move | ✓ |
| Clone directly into `.paaf/skills/` | Direct clone, delete on error | |
| You decide | Staging folder with atomic move | |

**User's choice:** Clone to a temporary staging folder, validate manifest & requirements, then atomically move

| Option | Description | Selected |
|--------|-------------|----------|
| Automatically install dependencies | Install into active venv via uv/pip after user approval | ✓ |
| Check availability only | Refuse install if missing and prompt manual install | |
| You decide | Auto-install into venv after user approval | |

**User's choice:** Automatically install dependencies into active venv via uv/pip after user approves install

| Option | Description | Selected |
|--------|-------------|----------|
| Atomic rollback | Wipe staging folder on error | |
| Keep staging directory for debugging | Retain staging directory on failure for user inspection | ✓ |
| You decide | Atomic rollback | |

**User's choice:** Keep staging directory for debugging and display error message

---

## Interactive Permission Review & Enable/Disable State

| Option | Description | Selected |
|--------|-------------|----------|
| Detailed review | Skill info, tools + permission tiers, persona summary, deps, SKILL-05 disclosure | ✓ |
| Compact summary | Tool names, permission tiers, and SKILL-05 disclosure | |
| You decide | Detailed review with all manifest details | |

**User's choice:** Detailed review — skill info, tools + permission tiers, persona fragment, deps, and SKILL-05 disclaimer

| Option | Description | Selected |
|--------|-------------|----------|
| Section `skills:` in `paaf.yaml` | Mapping `skill_name` -> `{ enabled: bool, path: str, permissions: dict }` | ✓ |
| Lists under `skills.installed`/`enabled` | Separate lists for installed vs enabled | |
| You decide | Mapping under `skills:` section | |

**User's choice:** Section `skills:` in `paaf.yaml` mapping `skill_name` -> `{ enabled: bool, path: str, permissions: dict }`

| Option | Description | Selected |
|--------|-------------|----------|
| Hot-reload | Immediately add/remove `persona.md` from compose and tools from registry | ✓ |
| Cold update | Require app reload | |
| You decide | Hot-reload prompt composition & tool registry | |

**User's choice:** Hot-reload — update `paaf.yaml`, immediately add/remove `persona.md` from compose and tools from registry

| Option | Description | Selected |
|--------|-------------|----------|
| Require `--yes` / `--approve-permissions` | Require flag in non-interactive script mode, error if missing | ✓ |
| Fail non-interactive mode | Fail non-interactive mode unconditionally | |
| You decide | Require flag in non-interactive mode | |

**User's choice:** Require `--yes` / `--approve-permissions` flag in non-interactive script mode, error if missing

---

## PyPI Packaging & Documentation Site Stack

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone `paaf-llm` | Separate `paaf-llm` package with dependencies | |
| Single monolithic `paaf` PyPI package | Single PyPI package bundling all framework packages | ✓ |
| You decide | Standalone package with optional `[engine]` extra | |

**User's choice:** Single monolithic `paaf` PyPI package bundling all framework packages

| Option | Description | Selected |
|--------|-------------|----------|
| MkDocs Material | `mkdocs.yml` in root, `docs/` folder — dark mode, search, API docs | ✓ |
| Sphinx with Furo | Sphinx documentation toolchain | |
| Starlight / Astro | Starlight docs site | |
| You decide | MkDocs Material | |

**User's choice:** MkDocs Material (`mkdocs.yml` in root, `docs/` folder) — sleek dark mode, search, API docs

| Option | Description | Selected |
|--------|-------------|----------|
| Structured sections | Quickstart, Config, Mesh, Skills, API Ref, and explicit 'Roadmap & What Exists' page | ✓ |
| Simplified guide | Quickstart, Config, Skills, API Ref | |
| You decide | Structured sections with scope disclosure | |

**User's choice:** Structured sections: Quickstart, Config, Mesh, Skills, API Ref, and explicit 'Roadmap & What Exists' page

| Option | Description | Selected |
|--------|-------------|----------|
| Automated CI workflow | Build wheel, install into isolated clean venv, run smoke suite | ✓ |
| Local validation script | Manual script prior to publishing | |
| You decide | Automated CI workflow | |

**User's choice:** Automated CI workflow building wheel, installing into isolated clean venv, and running smoke suite

---

## Agent Discretion

None — all decisions explicitly chosen by user.

## Deferred Ideas

None — discussion stayed within phase scope.
