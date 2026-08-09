<!-- SPDX-License-Identifier: Apache-2.0 -->

# Contributing to PAAF

PAAF is an open-source personal voice-assistant framework you can run and
**verify**. Contributions are welcome from self-hosters, privacy-minded
users, and developers building a different assistant on the framework.

This document tells an outsider how to build the project, run the tests,
and get a change accepted. For the shape of the codebase, read
[`ARCHITECTURE.md`](ARCHITECTURE.md). For the project's hard commitments
(no accounts, no telemetry ever, the anti-feature list, the
permission-model-as-only-injection-defense constraint), read
[`DECISIONS.md`](DECISIONS.md) — those are non-negotiable and a PR that
erodes them will not be merged.

## License and the DCO sign-off (no CLA)

The framework is licensed under **Apache-2.0** (see [`LICENSE`](LICENSE)).
Your contribution is accepted under that same license.

We use the **Developer Certificate of Origin (DCO) — not a CLA.** You keep
your copyright; there is no separate agreement to sign and no rights
assignment. Instead, you certify the [DCO 1.1](https://developercertificate.org/)
on **every commit** by signing it off:

```bash
git commit -s -m "feat(core): add the thing"
```

The `-s` appends a trailer to your commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

By adding that line you assert the DCO: that you wrote the patch (or have
the right to submit it under Apache-2.0). Configure `git config user.name`
and `git config user.email` to match a real identity. **A DCO check runs on
every pull request** (`.github/workflows/dco.yml`); a commit missing a valid
`Signed-off-by` trailer fails the check. If you forgot, amend with
`git commit --amend -s` (or rebase-and-sign for multiple commits) and
force-push your branch.

## Conventional Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <summary>
```

Common types: `feat`, `fix`, `test`, `refactor`, `perf`, `docs`, `style`,
`chore`, `ci`. The `scope` is usually the package or subsystem you touched
(`core`, `trace`, `llm`, `voice`, `session`, `ci`). Examples:

- `feat(core): atomic YAML config writes`
- `test(trace): time-to-first-audio regression guard`
- `docs(architecture): document the import boundaries`

## Semantic Versioning

Each of the five framework packages is **independently versioned** under
[SemVer 2.0.0](https://semver.org/): `MAJOR.MINOR.PATCH`.

- **MAJOR** — a breaking change to a package's public API.
- **MINOR** — backwards-compatible new functionality.
- **PATCH** — backwards-compatible bug fixes.

The **public API must never leak the underlying agent-framework types**
(LangChain/LangGraph stay confined to `paaf_llm._engine`; see
`ARCHITECTURE.md`). Changing a public signature to expose a framework type
is a breaking change *and* a boundary violation — CI will reject it.

## Building and running the tests

PAAF is a [uv](https://docs.astral.sh/uv/) workspace targeting **Python
3.12**. From the repo root:

```bash
# 1. Resolve the whole workspace (all five packages + dev tooling).
uv sync --all-packages

# 2. Run the full test suite OFFLINE. --disable-socket makes any network
#    socket open fail the build — the offline guarantee is enforced, not
#    trusted (FOUND-03 / PRIV-02). This is the default in pyproject.toml.
uv run pytest --disable-socket

# 3. Check the architectural import boundaries (FOUND-04): voice<->llm
#    independence, langchain confined to its adapter, no network client
#    anywhere in the framework graph. A forbidden import fails this.
uv run lint-imports
```

CI runs exactly these steps (`.github/workflows/ci.yml`) plus the
root-level governance rot-guard:

```bash
# Root-level tests are NOT auto-collected (testpaths = ["packages"]), so
# they are named explicitly. This is the guard that fails CI on a source
# file missing its SPDX header or a dropped DECISIONS.md section (FOUND-07).
uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket
```

Run all of the above locally before opening a PR; they must be green.

## License headers

Every framework **source file** (`packages/*/src/**/*.py`) must begin with
the SPDX identifier as its first non-empty line:

```python
# SPDX-License-Identifier: Apache-2.0
```

`tests/test_governance.py` globs every source file and fails CI if any
lacks it. Documentation and config files carry a short license note (e.g.
an HTML/`#` comment) rather than a code header.

## Pull request checklist

- [ ] Commits are signed off (`git commit -s`) — DCO, not a CLA.
- [ ] Commit messages follow Conventional Commits.
- [ ] New source files carry the `# SPDX-License-Identifier: Apache-2.0` header.
- [ ] `uv run pytest --disable-socket` is green.
- [ ] `uv run lint-imports` is green (no boundary violations).
- [ ] The change does not weaken a commitment recorded in `DECISIONS.md`
      (no telemetry, no accounts, no hidden injection defenses).

## Code of Conduct

PAAF is committed to providing a welcoming, inclusive, and harassment-free experience for all contributors regardless of background. Please maintain respectful, constructive, and professional communication in all issue discussions and pull requests.

## Coding Standards

- **Formatting & Linting**: Code formatting is managed by `ruff`. Run `uv run ruff check .` and `uv run ruff format --check .` before committing.
- **Type Checking**: Static typing is enforced by `mypy` across all packages (`uv run mypy packages/`).
- **Import Boundaries**: Architecture isolation contracts are enforced via `import-linter` (`uv run lint-imports`).

## Issue Reporting

When reporting bugs or feature requests:
1. Search existing GitHub Issues to ensure the problem has not already been reported.
2. Provide environment details: OS, Python version (`python --version`), and PAAF version.
3. Include a minimal, reproducible code example or clear steps to reproduce.
4. Describe the expected behavior versus the actual behavior observed.
