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

## Task 1 — voice venv provisioning

**Network activity was announced before it happened (PRIV-06 rehearsal, RESEARCH §Security V12).**
Two announced network steps in this task: (a) PyPI wheel downloads (~1.3 GB installed, dominated by
`torch`/`torchaudio`), (b) nothing else — model weights are a *separate* announced fetch in Task 2.
`HF_TOKEN` was deliberately **not** set; all models used are public.

### Venv identity

| Property | Value |
|---|---|
| Path | `spike/voice/.venv` |
| Interpreter | **CPython 3.12.13**, `arm64`, `macOS-26.5.2-arm64-arm-64bit` |
| Created by | `uv venv --python 3.12 spike/voice/.venv` (uv 0.11.31) |
| Installed size | **1.3 GB** |
| Git status | **ignored** — `git check-ignore -v` → `.gitignore:11:spike/**/.venv/`; `git status --porcelain` shows no venv path |
| Separate from | `spike/.venv` (base test env, 01-01) and the future `spike/bakeoff/.venv` (01-04) |

The SEPARATE-venv rule was honoured for the reason RESEARCH gives: `chatterbox-tts` hard-pins
`torch==2.6.0`, `transformers==5.2.0`, `diffusers==0.29.0`, `numpy<2.0.0`, `safetensors==0.5.3`,
`gradio==6.8.0`, and `dicta-onnx` pins `onnxruntime==1.21.1`. Resolving that against the
LangChain / Pydantic-AI trees is a resolver fight with no upside — the two halves never import
each other.

### Install commands, in the order RESEARCH specifies

```bash
uv venv --python 3.12 spike/voice/.venv
# 1. TTS + the two undeclared language deps -- ONE resolve, deliberately (see A2 below)
uv pip install "chatterbox-tts==0.1.7" "dicta-onnx==1.0.9"
# 2. STT
uv pip install "faster-whisper==1.2.1" soundfile
# 3. test runner
uv pip install pytest pytest-asyncio
```

Steps 2 and 3 installed **only** their own new packages and downgraded/changed nothing from
step 1 — so the TTS pin set survived the STT install intact.

### Version re-verification at install time

RESEARCH carries `valid-until: 2026-08-03`. Every pin was independently re-checked against the
PyPI JSON API on **2026-07-23** before installing. All three primary pins are still the **latest**
release of their project, so no pin is holding back a newer version:

| Package | RESEARCH pin | Latest on PyPI 2026-07-23 | Drift |
|---|---|---|---|
| `chatterbox-tts` | 0.1.7 | **0.1.7** (2026-03-26) | none |
| `dicta-onnx` | 1.0.9 | **1.0.9** (2025-05-31) | none |
| `faster-whisper` | 1.2.1 | **1.2.1** (2025-10-31) | none |
| `soundfile` | 0.14.0 (unpinned in the install) | resolved to **0.14.0** | none |

### Assumption A2 — dicta-onnx pins vs chatterbox's transformers ✅ RESOLVED, NO CONFLICT

> *A2: `dicta-onnx`'s `onnxruntime==1.21.1` and `tokenizers>=0.21.1` pins co-resolve with
> chatterbox's `transformers==5.2.0`. Risk: Medium — this is the first thing likely to break.*

`chatterbox-tts==0.1.7` and `dicta-onnx==1.0.9` were installed in a **single `uv pip install`
invocation** specifically so the resolver had to satisfy both constraint sets simultaneously.
Installing them sequentially would have let a later install silently clobber an earlier pin and
would not have tested the assumption at all.

**Result: resolved cleanly, first attempt, no backtracking error, no workaround needed.**

| Constraint | Source | Resolved |
|---|---|---|
| `onnxruntime==1.21.1` | dicta-onnx (exact) | **1.21.1** ✅ |
| `tokenizers>=0.21.1` | dicta-onnx (floor) | **0.22.2** ✅ |
| `transformers==5.2.0` | chatterbox (exact) | **5.2.0** ✅ |
| `torch==2.6.0` | chatterbox (exact, py<3.14) | **2.6.0** ✅ |
| `numpy<2.0.0,>=1.24.0` | chatterbox (py<3.13) | **1.26.4** ✅ |
| `safetensors==0.5.3` | chatterbox (exact) | **0.5.3** ✅ |
| `diffusers==0.29.0` | chatterbox (exact) | **0.29.0** ✅ |
| `gradio==6.8.0` | chatterbox (exact) | **6.8.0** ✅ |

The one thing worth noting: `transformers==5.2.0` is satisfied alongside `tokenizers==0.22.2`,
i.e. transformers 5.x's tokenizers floor is *above* dicta's `>=0.21.1` floor, so the two
constraints are compatible rather than merely coincidentally satisfiable. **A2 is closed.**

### Assumption A3 — transformers 5.2.0 + diffusers 0.29.0 at runtime ✅ RESOLVED, NO CONFLICT

> *A3: `transformers==5.2.0` and `diffusers==0.29.0` (a mid-2024 release) actually work together
> at runtime. Risk: Medium — an import error here blocks all voice spikes.*

Resolver success is not the same as runtime success, so both were imported in the same process
and a symbol was touched in each (a bare `import` can succeed while lazy submodule loading fails
later):

```
transformers 5.2.0
diffusers 0.29.0
OK    transformers.AutoTokenizer: AutoTokenizer
OK    diffusers.DDPMScheduler: DDPMScheduler
OK    chatterbox import: 0.1.7          <- imports BOTH transitively
```

`import chatterbox` is itself the strongest A3 evidence available: `chatterbox/__init__.py`
pulls `ChatterboxTTS`, `ChatterboxVC` and `ChatterboxMultilingualTTS`, which between them import
the transformers and diffusers surfaces the model actually uses. It succeeded. **A3 is closed.**

### Import verification — every required package imports

```
python: 3.12.13 arm64 macOS-26.5.2-arm64-arm-64bit
torch 2.6.0  torchaudio 2.6.0  numpy 1.26.4
torch.backends.mps.is_built() = True   torch.backends.mps.is_available() = True
chatterbox 0.1.7   SUPPORTED_LANGUAGES n=23   {en,ru,he,es} present = True
onnxruntime 1.21.1  tokenizers 0.22.2
dicta_onnx -> Dicta  (class resolves)
faster_whisper 1.2.1  soundfile 0.14.0  ctranslate2 4.8.1  av 18.0.0
russian_text_stresser -> ImportError: No module named 'russian_text_stresser'   (EXPECTED, Pitfall 2)
```

Two incidental confirmations of RESEARCH claims:

- **`ctranslate2==4.8.1` installed from a macOS arm64 cp312 wheel** — no source build. This
  confirms RESEARCH's correction to CLAUDE.md: arm64 wheels do exist (they are still CPU-only;
  CTranslate2 has no Metal backend).
- **MPS is both built and available** on this machine, so the Task 2 device probe is a real test
  of chatterbox-on-MPS rather than a test of "does this Mac have MPS".

### Full resolved freeze — 121 packages

This is the provisioning baseline of record for `01-RESULTS.md`. Any later voice measurement in
this phase is a property of *this exact* set.

```
aiofiles==24.1.0
annotated-doc==0.0.4
annotated-types==0.7.0
antlr4-python3-runtime==4.9.3
anyio==4.14.2
audioread==3.1.0
av==18.0.0
brotli==1.2.0
catalogue==2.0.10
certifi==2026.7.22
cffi==2.1.0
cfgv==3.5.0
charset-normalizer==3.4.9
chatterbox-tts==0.1.7
click==8.4.2
coloredlogs==15.0.1
conformer==0.3.2
ctranslate2==4.8.1
decorator==5.3.1
deprecated==1.3.1
dicta-onnx==1.0.9
diffusers==0.29.0
distlib==0.4.3
einops==0.8.2
fastapi==0.139.2
faster-whisper==1.2.1
ffmpy==1.0.0
filelock==3.32.0
flatbuffers==25.12.19
fsspec==2026.6.0
gradio-client==2.2.0
gradio==6.8.0
groovy==0.1.2
h11==0.16.0
hf-xet==1.5.2
httpcore==1.0.9
httpx==0.28.1
huggingface-hub==1.24.0
humanfriendly==10.0
identify==2.6.19
idna==3.18
importlib-metadata==9.0.0
iniconfig==2.3.0
jaconv==0.5.0
jinja2==3.1.6
joblib==1.5.3
lazy-loader==0.5
librosa==0.11.0
llvmlite==0.48.0
markdown-it-py==4.2.0
markupsafe==3.0.3
mdurl==0.1.2
ml-dtypes==0.5.4
mpmath==1.3.0
msgpack==1.2.1
narwhals==2.24.0
networkx==3.6.1
nodeenv==1.10.0
numba==0.66.0
numpy==1.26.4
omegaconf==2.3.1
onnx==1.22.0
onnxruntime==1.21.1
orjson==3.11.9
packaging==26.2
pandas==3.0.5
pillow==12.3.0
platformdirs==4.11.0
pluggy==1.6.0
pooch==1.9.0
pre-commit==4.6.1
protobuf==7.35.1
pycparser==3.0
pydantic-core==2.46.4
pydantic==2.13.4
pydub==0.25.1
pygments==2.20.0
pykakasi==2.3.0
pyloudnorm==0.2.0
pytest-asyncio==1.4.0
pytest==9.1.1
python-dateutil==2.9.0.post0
python-discovery==1.5.0
python-multipart==0.0.32
pytz==2026.2
pyyaml==6.0.3
regex==2026.7.19
requests==2.34.2
resemble-perth==1.0.1
rich==15.0.0
s3tokenizer==0.3.0
safehttpx==0.1.7
safetensors==0.5.3
scikit-learn==1.9.0
scipy==1.17.1
semantic-version==2.10.0
setuptools==83.0.0
shellingham==1.5.4
six==1.17.0
soundfile==0.14.0
soxr==1.1.0
spacy-pkuseg==1.0.1
srsly==2.5.3
starlette==0.52.1
sympy==1.13.1
threadpoolctl==3.6.0
tokenizers==0.22.2
tomlkit==0.13.3
torch==2.6.0
torchaudio==2.6.0
tqdm==4.69.0
transformers==5.2.0
typer-slim==0.24.0
typer==0.27.0
typing-extensions==4.16.0
typing-inspection==0.4.2
urllib3==2.7.0
uvicorn==0.51.0
virtualenv==21.7.0
wrapt==2.2.2
zipp==4.1.0
```

---

## Task 2 — GATE 0 readiness outcomes

**GATE 0: GREEN** (configuration: `repaired`)

| Environment | Value |
|---|---|
| `python` | `3.12.13` |
| `platform` | `macOS-26.5.2-arm64-arm-64bit` |
| `machine` | `arm64` |
| `torch` | `2.6.0` |
| `mps_is_built` | `True` |
| `mps_is_available` | `True` |
| `chatterbox` | `0.1.7` |
| `hf_token_set` | `False` |

### Upstream defect — chatterbox's own `Dicta()` call

- chatterbox's zero-arg `Dicta()` works: **False**
- exception (verbatim): `TypeError: Dicta.__init__() missing 1 required positional argument: 'model_path'`

### Check 1 — Hebrew diacritics MUTATE the input (hard assert)

- input : `שלום עולם`
- output: `שְׁלוֹם עוֹלָם`
- mutated: **True**
- dicta model: `/Users/alexanderikonnikov/Documents/repos/paaf/spike/voice/.models/dicta-1.0.onnx`

### Check 2 — no degradation warning during a real Hebrew probe render

- probe text: `שלום, מה שלומך היום` (`language_id=he`)
- generate: **41.105 s**, 269760 samples
- chatterbox degradation warnings: **[]**
- non-blocking warning (recorded, not a gate failure): `chatterbox.models.t3.inference.alignment_stream_analyzer: forcing EOS token, long_tail=tensor(False), alignment_repetition=tensor(False), token_repetition=True`
- non-blocking warning (recorded, not a gate failure): `chatterbox.models.t3.inference.alignment_stream_analyzer: 🚨 Detected 2x repetition of token 6486`

### Check 3 — Russian stress labeling

- `russian_text_stresser` present: **False**
- exception (verbatim): `ModuleNotFoundError: No module named 'russian_text_stresser'`
- consequence: Russian is measured WITHOUT stress labeling. This is what a user gets from a default install; it is not fixable by pip (permanent PyPI 404). Carry this caveat into any D-20 Russian spot-check.

### Check 4 — usable inference device

- **usable device: `mps`**

- `mps`: constructed=True generated=True in 60.933 s

### Check 5 — seed reproducibility (Open Question 2)

- seed `1234` on `mps`, same sentence rendered twice
- shapes: `(1, 269760)` vs `(1, 269760)` (same_shape=True)
- **bitwise identical: True**
- allclose(atol=1e-6): True; max |diff|: 0.0
- generate times: [19.89, 19.984] s
- consequence: D-07's re-run-and-diff promise holds on this backend.

---

## Announced model downloads (PRIV-06 rehearsal, RESEARCH §Security V12)

Every weight fetch in this plan is listed here as an **explicit, announced step**, which is
the whole point of the rehearsal: a user of the shipped product must be told when their
machine reaches the network, and the framework's offline claim has to be *verifiable*, not
asserted. `HF_TOKEN` was deliberately **never** set — all three artifacts are public, and the
HF Hub's own `You are sending unauthenticated requests` notice is the standing proof of it.

| # | Artifact | Source | Size | When |
|---|---|---|---:|---|
| 1 | Chatterbox Multilingual V3 checkpoint | HF `ResembleAI/chatterbox` | ~3.0 GB (HF cache) | Task 2, first `from_pretrained` |
| 2 | `dicta-1.0.onnx` (fp32 diacritizer) | GitHub release `thewh1teagle/dicta-onnx@model-files-v1.0` | **1,222,572,597 B (1.22 GB)** | Task 2, Gate 0 repair |
| 3 | Whisper `large-v3` | HF `Systran/faster-whisper-large-v3` | **3,090,839,273 B (3.09 GB)** | Task 1 completion (below) |

Total on-disk weights for the voice half: **≈7.3 GB**. None of it is in git — `.gitignore`
covers `*.onnx` and `**/huggingface/hub/`, verified with `git check-ignore`.

Note on artifact 2: `dicta-onnx` **ships no weights**, and chatterbox has no way to supply the
path (that is the defect above). The fp32 export was chosen over the int8 one deliberately, so
that quantization artifacts in *diacritization* can never be misread as a Chatterbox Hebrew
failure — the same reasoning RESEARCH uses to prefer `large-v3` over the community turbo build.

### Task 1 completion — Whisper `large-v3` fetch

Task 1's action requires the Whisper fetch to be an announced download; it was not performed
in the original Task 1 pass, so it was completed here and is recorded as part of Task 1's
baseline rather than as new scope.

```
Fetching 7 files: 100%|██████████| 7/7 [00:31<00:00,  4.56s/it]
Warning: You are sending unauthenticated requests to the HF Hub.   <- no HF_TOKEN, as intended
PATH .../hub/models--Systran--faster-whisper-large-v3/snapshots/edaa852ec7e145841d8ffdb056a99866b5f0a478
SECONDS 32.3
```

| File | Bytes |
|---|---:|
| `model.bin` | 3,087,284,237 |
| `tokenizer.json` | 2,480,617 |
| `vocabulary.json` | 1,068,114 |
| `config.json` | 2,394 |
| `preprocessor_config.json` | 340 |
| `README.md` / `.gitattributes` | 2,052 / 1,519 |
| **total** | **3,090,839,273** |

Load verified (the fetch is usable, not merely present):

```
faster_whisper 1.2.1   ctranslate2 4.8.1
large-v3 resolves to: Systran/faster-whisper-large-v3      <- FIRST-PARTY, per RESEARCH's preference
WhisperModel('large-v3', device='cpu', compute_type='int8') loaded OK in 1.8 s
```

`large-v3` was chosen over `large-v3-turbo` because turbo resolves to the community conversion
`mobiuslabsgmbh/faster-whisper-large-v3-turbo`; in a *measurement* phase that would risk
attributing a conversion's flaws to Whisper itself (RESEARCH §Alternatives Considered).

### ⚠️ Correction to RESEARCH §Pitfall 7 — `vad_filter` default

RESEARCH states: *"`vad_filter` defaults to **`True`** in 1.2.1 — on short synthetic clips this
can trim audio and be misread as transcription failure."* Checked against the installed wheel,
that is true for only one of the two transcribe APIs:

| API | `vad_filter` default | `multilingual` default |
|---|---|---|
| `WhisperModel.transcribe` (the API RESEARCH's own code example uses) | **`False`** | `False` |
| `BatchedInferencePipeline.transcribe` | `True` | `False` |

So the SPIKE-04 harness (01-06) does **not** need `vad_filter=False` defensively if it uses
`WhisperModel.transcribe` — it is already off — but it **must** pass it explicitly if it ever
switches to the batched pipeline. The `multilingual=True` half of Pitfall 7 is confirmed on both
APIs: it defaults to `False`, so the per-segment language-detection instrument must be turned on
deliberately or SPIKE-04 measures the wrong thing.

