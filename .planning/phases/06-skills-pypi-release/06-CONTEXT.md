# Phase 6: Skills & PyPI Release - Context

**Gathered:** 2026-08-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 ships installable skills, skill lifecycle management, public PyPI release of the framework, and a comprehensive public documentation site before voice components exist.

A skill is a folder or git repository containing a `skill.yaml` manifest, a `prompt.md`/`persona.md` persona fragment file, autodiscovered `@tool` Python functions, and declared permissions/dependencies. Users can install skills via `paaf skill install <git-url>`, review requested permissions with explicit security disclosures, and enable/disable skills dynamically with instant hot-reloading in system prompts and the unified tool registry.

`paaf-llm` (along with `paaf-core` and `paaf-trace`) is published publicly to PyPI, allowing a stranger to `pip install paaf`, build an agent mesh, install a skill, and inspect verbatim prompts. A published MkDocs Material docs site covers installation, configuration, agent mesh, skill authoring, and API reference, while explicitly disclosing that voice and appliance features do not exist yet.
</domain>

<decisions>
## Implementation Decisions

### Skill Manifest Format & Tool Discovery
- **D-01 (Skill Manifest `skill.yaml`):** A skill is a folder or git repository containing a dedicated `skill.yaml` manifest in its root directory declaring `name`, `version`, `description`, `persona_fragment` (path to prompt file), `tools`, `permissions` (requested tool permission tiers), and `dependencies` (Python package requirements). — **Reversibility:** costly — core skill manifest schema contract.
- **D-02 (Autodiscovered `@tool` Functions):** Python functions inside a skill directory decorated with `@tool` (`from paaf_llm import tool`) are automatically discovered and registered into the unified tool registry when the skill is loaded. — **Reversibility:** costly — skill tool discovery architecture.
- **D-03 (Separate `prompt.md` / `persona.md` File):** Skill persona instructions are stored in a separate `prompt.md` or `persona.md` file in the root of the skill folder. During prompt composition (`compose.py`), the content is appended verbatim to the agent's base system prompt with a clear section header (`--- Skill: <name> ---`), ensuring it is completely unobscured and inspectable via `paaf prompt`. — **Reversibility:** costly — prompt composition contract.
- **D-04 (Tool Namespacing in Registry):** Skill tools use flat names by default when unique (e.g., `web_search`), and are automatically prefixed with `skill_<skill_name>_<tool_name>` if a name collision occurs in the unified registry (matching D-11 MCP namespacing rule). — **Reversibility:** reversible — internal registry composition logic.

### Skill Installation, Git Cloning & Dependency Rollback
- **D-05 (Project-Local Skill Storage):** Installed skills live strictly inside `.paaf/skills/<skill_name>/` within the project root directory. — **Reversibility:** costly — skill storage location & file path expectations.
- **D-06 (Temporary Staging Folder for Git Clone):** `paaf skill install <git-url>` clones into a temporary staging folder (`.paaf/staging/<tmp_id>`), validates the `skill.yaml` manifest, checks requirements, and only after validation and permission approval moves the directory to `.paaf/skills/<skill_name>/`. — **Reversibility:** reversible — installation workflow logic.
- **D-07 (Automatic Dependency Installation into Active Venv):** Python package dependencies declared by the skill are automatically installed into the active Python environment (via `uv pip install` or `pip install`) after the user approves the install and permission review. — **Reversibility:** costly — modifies active venv packages.
- **D-08 (Debug Staging Retention on Failure):** If cloning, manifest validation, or dependency installation fails, the installation process halts, displays a clear error message, and retains the staging directory (`.paaf/staging/...`) for user debugging rather than deleting it. — **Reversibility:** reversible — installer failure handling.

### Interactive Permission Review & Enable/Disable State
- **D-09 (Detailed Install-Time Permission Review):** Running `paaf skill install <git-url>` displays a detailed interactive permission review showing skill name/version, declared persona summary, provided tools with proposed permission tiers (`act`/`confirm`), requested dependencies, and the explicit SKILL-05 security disclosure: *"Skills run in-process with no sandbox; manifest permissions provide disclosure, not process isolation. For untrusted code, use MCP servers."* — **Reversibility:** costly — CLI user experience & security policy.
- **D-10 (`paaf.yaml` Skill Configuration Schema):** Skill state is persisted in `paaf.yaml` under a `skills:` section mapping `skill_name` -> `{ enabled: bool, path: str, permissions: { <tool>: <tier> } }`. — **Reversibility:** costly — config schema.
- **D-11 (Hot-Reloading Skill Enable/Disable):** Toggling a skill via `paaf skill enable/disable <skill-name>` updates `paaf.yaml` and immediately hot-reloads prompt composition (adding/removing `persona.md`) and the tool registry (registering/unregistering skill `@tool` functions) without needing to restart the process or uninstall skill files. — **Reversibility:** costly — runtime hot reload engine.
- **D-12 (Non-Interactive Approval Flag):** In non-interactive script/CI environments, `paaf skill install` requires the `--yes` or `--approve-permissions` flag to approve permissions automatically; attempting non-interactive install without the flag errors out cleanly. — **Reversibility:** reversible — CLI argument parsing.

### PyPI Packaging & Documentation Site Stack
- **D-13 (Single Monolithic `paaf` PyPI Package):** The framework is packaged and published to PyPI as a single monolithic `paaf` PyPI package (bundling `paaf-core`, `paaf-trace`, and `paaf-llm`), providing a single `pip install paaf` entry point with the agent mesh, verbatim prompt inspector, and skill installer working out of the box, with optional `[engine]` extra for heavy dependencies (LangChain). — **Reversibility:** one-way — published package name and layout on PyPI.
- **D-14 (MkDocs Material Documentation Generator):** The public documentation site (OSS-02) is built using `mkdocs-material` (`mkdocs.yml` in project root, docs in `docs/`), providing dark mode, fast client-side search, code syntax highlighting, and API reference pages. — **Reversibility:** costly — documentation toolchain and site structure.
- **D-15 (Structured Docs Navigation & Scope Disclosure):** The docs site structure includes: Getting Started & Quickstart, Configuration Guide, Agent Mesh Architecture, Skill Authoring & Security Model, API Reference, and an explicit *"Roadmap & What Exists"* page that clearly states voice, appliance, and desktop features do NOT exist yet (added in Phase 13). — **Reversibility:** costly — published documentation content.
- **D-16 (Automated Clean-Venv Release Verification CI Job):** A GitHub Actions CI workflow validates releases by building the package wheel, installing it into an isolated clean venv without repository access, and executing end-to-end smoke tests verifying `paaf chat`, agent mesh handoffs, `paaf prompt`, and skill loading. — **Reversibility:** reversible — CI workflow configuration.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — SKILL-01..05 (skill manifest, git install, permission review, enable/disable, no-sandbox disclosure), OSS-01..02 (PyPI release, documentation site).
- `.planning/ROADMAP.md` §"Phase 6: Skills & PyPI Release".
- `.planning/PROJECT.md` — Core value, solo maintainer burnout mitigation, framework public API.

### Prior Phase Decisions & Core Constraints
- `.planning/phases/05-tools-mcp-permissions/05-CONTEXT.md` — Unified tool registry, `@tool` decorator, permission tiers, namespacing (D-06, D-11, D-14..D-18).
- `.planning/phases/04-agent-mesh/04-CONTEXT.md` — Agent mesh handoff loop, prompt explainer, verbatim prompt inspector (PERS-05).
- `.planning/phases/03-paaf-llm-core/03-CONTEXT.md` — Single agent turn, prompt composer (`compose.py`), profiles, wheel independence.
- `.planning/phases/02-foundation/02-CONTEXT.md` — Wheel independence CI job, atomic config store, secret store.
- `.claude/CLAUDE.md` — Wheel independence, no-network-in-CI, architectural contracts.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `paaf_llm.tools.decorator`: `@tool` decorator interface for discovering and decorating skill functions.
- `paaf_llm.registry`: `ToolRegistry` for registering skill-contributed tools with permission tiers and namespacing support.
- `paaf_llm.compose`: `PromptComposer` for appending skill `prompt.md`/`persona.md` fragments into the agent system prompt.
- `paaf_core.config`: Atomic config store (`paaf.yaml`) for persisting skill enable/disable state and granted permission overrides.
- `packages/paaf-llm/pyproject.toml` & `.github/workflows`: wheel build and clean-venv test patterns established in Phase 2/3.

### Established Patterns
- Hot-reloading config and registry components without restarting process.
- Flat tool naming by default with `skill_<name>_<tool>` prefix on collision.
- Verbatim prompt composition (`join == compose` invariant).

### Integration Points
- `paaf-llm/src/paaf_llm/cli.py`: add `paaf skill install`, `paaf skill list`, `paaf skill enable`, `paaf skill disable`.
- `paaf-llm/src/paaf_llm/compose.py`: load active skill persona fragments into system prompt.
- `paaf-llm/src/paaf_llm/registry.py`: autodiscover skill `@tool` functions and bind into registry.
</code_context>

<specifics>
## Specific Ideas

- Install CLI: `paaf skill install <git-url>` with interactive permission review screen.
- Security disclosure text on install: *"Skills run in-process with no sandbox; manifest permissions provide disclosure, not process isolation. For untrusted code, use MCP servers."*
- Non-interactive flag: `--yes` or `--approve-permissions`.
- PyPI package: `paaf` (or `paaf-llm` bundling dependencies) with `pip install paaf`.
- Docs engine: `mkdocs-material` with site navigation, quickstart, API docs, and explicit roadmap scope disclosure.
</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.
</deferred>

---

*Phase: 6-Skills & PyPI Release*
*Context gathered: 2026-08-08*
