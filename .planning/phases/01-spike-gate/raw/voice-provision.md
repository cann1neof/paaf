# Voice venv provisioning record — Phase 1, plan 01-03

Machine: Apple M3 Pro, 18 GB unified memory, macOS 26.5.2, arm64.
Venv: `spike/voice/.venv` (Python 3.12, git-ignored, dies with `spike/` per SC#5).

This file is the durable record of **how the voice half of Phase 1 was assembled**. It survives
`spike/` deletion (D-07). Everything measured here is a property of the *as-installed* configuration,
not of the models in the abstract.

---

## Task 0 — dicta-onnx supply-chain evidence (human approval DEFERRED)

`01-03-PLAN.md` Task 0 is a `checkpoint:human-verify` with `gate="blocking-human"`: the
RESEARCH Package Legitimacy Audit singles out `dicta-onnx==1.0.9` as the one package in this
phase warranting a human gate — it is not named in the project's prior research, it was
discovered during the research session, and it is maintained by an individual.

**The human has NOT yet approved this package.** At the user's explicit direction
("ignore anything that a human needs to do — focus on code"), the verification was performed
**programmatically** and the install proceeded on that evidence. The evidence below is what a
human approval would rest on. **The yes/no is still owed.** See
`01-03-SUMMARY.md` § "Deferred — Human Action Required".

Evidence gathered 2026-07-23 (RESEARCH's own audit ran 2026-07-20; this is an independent re-check).

### 1. PyPI registry facts — `dicta-onnx`

Source: `GET https://pypi.org/pypi/dicta-onnx/json`

| Field | Value |
|---|---|
| Name | `dicta-onnx` |
| Latest version | **1.0.9** — matches the pin; version exists and is **published** |
| Yanked | **False** (checked on 1.0.9 specifically and on every file of that release) |
| Upload date (1.0.9) | **2025-05-31T13:01:10Z** (wheel), 2025-05-31T13:01:11Z (sdist) |
| Summary | "Add diacritics to Hebrew text using Dicta model" |
| Declared license | **none — no `license` and no `license_expression` field** (see finding L1 below) |
| `requires_python` | `>=3.11` — satisfied by the 3.12.13 venv |
| `requires_dist` | `onnxruntime==1.21.1`, `tokenizers>=0.21.1` — exactly the pins RESEARCH assumption **A2** flags |
| Author email | `61390950+thewh1teagle@users.noreply.github.com` (GitHub noreply, uid 61390950) |
| `project_urls.Repository` | **`https://github.com/thewh1teagle/dicta-onnx`** — matches RESEARCH exactly |
| `project_urls.Homepage` | `https://github.com/thewh1teagle/dicta-onnx` |
| `project_urls.Issues` | `https://github.com/thewh1teagle/dicta-onnx/issues` |

Full release history (10 releases, none yanked), which is *not* the shape of a freshly-minted
typosquat:

```
1.0.0  2025-04-01T22:36:47Z      1.0.5  2025-04-16T12:42:01Z
1.0.1  2025-04-02T00:02:40Z      1.0.6  2025-04-16T21:55:13Z
1.0.2  2025-04-16T12:20:36Z      1.0.7  2025-05-31T12:58:53Z
1.0.3  2025-04-16T12:26:09Z      1.0.8  2025-05-31T13:00:22Z
1.0.4  2025-04-16T12:27:43Z      1.0.9  2025-05-31T13:01:10Z
```

### 2. GitHub repo facts — `thewh1teagle/dicta-onnx`

Source: `GET https://api.github.com/repos/thewh1teagle/dicta-onnx` and `/users/thewh1teagle`

| Field | Value |
|---|---|
| Repo | **exists**, public, `thewh1teagle/dicta-onnx` |
| Description | "Add diacritics to Hebrew text using Dicta model" — matches the PyPI summary verbatim |
| Created | 2025-03-29T14:24:23Z (≈3 days before the first PyPI release — consistent ordering) |
| Last push | 2025-05-31T13:01:05Z — **5 seconds before** the 1.0.9 PyPI upload; the release is traceable to the repo |
| Archived / disabled / fork | **False / False / False** |
| Stars / forks / open issues | **9 / 3 / 4** (small — this is the real risk signal, see R1) |
| License | **none declared** (see L1) |
| Owner | `thewh1teagle`, **User** (individual), uid **61390950** — the uid matches the PyPI author email exactly |
| Owner account age | created 2020-02-23 (≈6 years), **78 public repos, 495 followers** |

The uid match between the PyPI author email (`61390950+thewh1teagle@…`) and the GitHub account
(`id: 61390950`) means the PyPI package and the GitHub repo are demonstrably the same identity —
not merely a package *claiming* an unrelated repo in its metadata.

### 3. Intent corroboration — the hard-coded import in chatterbox (strongest evidence)

The `chatterbox_tts-0.1.7` wheel was downloaded and unpacked **before installing anything**, and
grepped for `dicta`. RESEARCH claims the import is at `tokenizer.py:123`. **Confirmed — exact
file, exact line.**

Location found: `chatterbox/models/tokenizers/tokenizer.py`, **line 123**.

Verbatim context, lines 117–133 of the wheel source:

```python
117	def add_hebrew_diacritics(text: str) -> str:
118	    """Hebrew text normalization: adds diacritics to Hebrew text."""
119	    global _dicta
120	
121	    try:
122	        if _dicta is None:
123	            from dicta_onnx import Dicta
124	            _dicta = Dicta()
125
126	        return _dicta.add_diacritics(text)
127
128	    except ImportError:
129	        logger.warning("dicta_onnx not available - Hebrew text processing skipped")
130	        return text
131	    except Exception as e:
132	        logger.warning(f"Hebrew diacritization failed: {e}")
133	        return text
```

Every `dicta` hit in the entire wheel (there are no others):

```
chatterbox/models/tokenizers/tokenizer.py:61:_dicta = None
chatterbox/models/tokenizers/tokenizer.py:119:    global _dicta
chatterbox/models/tokenizers/tokenizer.py:122:        if _dicta is None:
chatterbox/models/tokenizers/tokenizer.py:123:            from dicta_onnx import Dicta
chatterbox/models/tokenizers/tokenizer.py:124:            _dicta = Dicta()
chatterbox/models/tokenizers/tokenizer.py:126:        return _dicta.add_diacritics(text)
chatterbox/models/tokenizers/tokenizer.py:129:    logger.warning("dicta_onnx not available - Hebrew text processing skipped")
```

This is decisive against typosquatting: the import name `dicta_onnx` and the method
`add_diacritics` are **dictated by a third party (Resemble AI) in a package with 100× the
provenance**, not chosen by us from a search result. A typosquat would have to have been
published *and* adopted by chatterbox upstream. It also confirms the exact API surface
Gate 0 must assert (`Dicta().add_diacritics(text)`).

Bonus finding from the same grep — **Pitfall 2 confirmed at source**, `tokenizer.py:237–253`:

```python
237	def add_russian_stress(text: str) -> str:
...
243	            from russian_text_stresser.text_stresser import RussianTextStresser
...
248	    except ImportError:
249	        logger.warning("russian_text_stresser not available - Russian stress labeling skipped")
250	        return text
```

Note the import is `russian_text_stresser.text_stresser`, i.e. a **submodule** — relevant to how
Gate 0 probes for its absence.

### 4. Auditable pins — exact artifacts and hashes

`dicta-onnx==1.0.9` (from the PyPI JSON API; the resolved install is recorded in Task 1 below):

| File | Type | Size | sha256 |
|---|---|---:|---|
| `dicta_onnx-1.0.9-py3-none-any.whl` | wheel | 4,152 B | `ddcb558b4d25731810ca4ed527f4f2655c3fccc5234538befd67b2f3e6cd8a58` |
| `dicta_onnx-1.0.9.tar.gz` | sdist | 23,544 B | `5998b777388111eb5ed4907d339a2b7fb3f8a35c006e56a4f70b26b66196f19d` |

`chatterbox-tts==0.1.7`, for completeness — the locally downloaded wheel was hashed and
**matched the PyPI-declared digest exactly**, so the source grepped above is provably the
published artifact:

| File | Type | Size | sha256 (PyPI == local) |
|---|---|---:|---|
| `chatterbox_tts-0.1.7-py3-none-any.whl` | wheel | 108,543 B | `83782500e3ad4e7c919132e9d7eb8755f29f57c5bde5ec48c655ca23a4eb113c` |
| `chatterbox_tts-0.1.7.tar.gz` | sdist | 84,802 B | `ed8afae83819b40a25927c2ef3bcc67f928bdfcf434c1376c972e6039252a187` |

### 5. Verdict on the evidence

| # | Finding | Reading |
|---|---|---|
| ✅ | Version 1.0.9 exists, published, not yanked, 10-release history since 2025-04 | Not a fresh typosquat |
| ✅ | Declared repo is `github.com/thewh1teagle/dicta-onnx`, exactly as RESEARCH says | Metadata matches audit |
| ✅ | Repo exists, is public, not archived, not a fork; last push 5 s before the release upload | Release is traceable to source |
| ✅ | PyPI author uid `61390950` == GitHub account uid `61390950` | Package and repo are the same identity |
| ✅ | Owner is a 6-year-old account with 78 repos and 495 followers | Not a throwaway publisher |
| ✅ | `from dicta_onnx import Dicta` hard-coded at `tokenizer.py:123` by Resemble AI | **Decisive** — the name is not ours to get wrong |
| ⚠️ **R1** | Repo has **9 stars, 3 forks, 4 open issues**; single individual maintainer; no release since 2025-05-31 | Real bus-factor/maintenance risk. Not a *malice* signal, but it is why the checkpoint exists. Mitigated for now by the exact pin + the throwaway venv. |
| ⚠️ **L1** | **No license declared on PyPI or GitHub.** No `license`, no `license_expression`, no repo license | "All rights reserved" by default. Harmless for a throwaway Phase-1 spike, but **this must be resolved before any shipping artifact depends on it** — the framework is Apache-2.0, and an unlicensed transitive dependency is a real distribution problem. Raised for Phase 6 / the packaging phase. |

Nothing alarming was found. The three conditions the dispatch defined as stop-conditions —
repo absent, version absent/yanked, or the chatterbox import path not referencing `dicta_onnx` —
**all came back negative**. The install proceeded.

**Still owed by the human:** an explicit yes/no on installing `dicta-onnx==1.0.9`, and a decision
on **L1** (the missing license) before anything shippable depends on it.

---
