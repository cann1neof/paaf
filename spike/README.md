# `spike/` — throwaway. Nothing here ships. Deleted at the end of Phase 1.

Everything under this directory is disposable measurement scaffolding for Phase 1
(spike-gate). **No code in this tree survives into any shipped package (roadmap SC#5),
and neither the code nor its interface signatures carry forward (D-18)** — Phase 3
designs its port fresh from the *findings*, not from anything written here.

SC#5 is therefore enforceable by one `ls`: when Phase 1 closes, `rm -rf spike/` is the
whole of it.

## What survives, and what does not

| Lives here (deleted) | Lives under `.planning/phases/01-spike-gate/` (survives) |
|---|---|
| `voice/` — TTS/STT harnesses (`gate_readiness.py`, `render_corpus.py`, `measure_ttfa.py`, `transcribe.py`, `shuffle_blind.py`, `roundtrip.py`) and their tests | `corpus/corpus.jsonl`, `corpus/clips/*.wav`, `corpus/clips_blind/*.wav`, `corpus/mapping.json`, `corpus/timings.jsonl`, `corpus/transcripts.jsonl` |
| `bakeoff/` — the framework bake-off port, both adapters, the stdio MCP target, and their tests | `raw/*.md` per-spike notes and `01-RESULTS.md` |
| `pytest.ini`, `conftest.py` — test config deliberately kept **inside** this directory so it is removed with it | `DECISIONS.md` (repo root) |

Corpus data lives under `.planning/` and **not** here on purpose (D-07): deleting
`spike/` must be an unambiguous, safe operation that never endangers the fixtures
Phase 7 needs in order to re-run and diff against these measurements.

## Running the tests

Run from the repository root. Because there is deliberately **no root `pyproject.toml`
and no root `.venv`** (that would leave a Phase-1 artifact outside `spike/` and weaken
the one-`ls` SC#5 check), a bare `uv run pytest` has nothing to resolve — point `uv` at
the venv explicitly:

```bash
V=spike/.venv/bin/python                          # base env: pytest + pytest-asyncio only
uv run --python $V pytest spike/ -x -q -m "not slow"   # quick: no model load, < 10s
uv run --python $V pytest spike/ -q                     # full: includes `slow` tests
```

Plans 01-03 and 01-04 create the two heavy venvs; swap `$V` for
`spike/.venv-voice/bin/python` or `spike/.venv-bakeoff/bin/python` to run that half's
tests. `spike/.venv` itself holds only the test framework, so the framework-free tests
(corpus grid, blind mapping, port conformance against the fakes) run there.

`pytest.ini` sits in this directory, so pytest's rootdir is `spike/` — that is
intentional. Phase 1 must not create a root `pyproject.toml` or `pytest.ini`: Phase 2
(FOUND-01) owns the real uv workspace, and Phase 1 must not anticipate that structure.

## Venvs

The voice half (`chatterbox-tts` hard-pins `torch==2.6.0` / `transformers==5.2.0` /
`numpy<2`) and the bake-off half (LangChain / Pydantic AI) get **separate venvs** — they
never import each other, so there is no reason to fight the resolver. Those venvs are
created by plans 01-03 and 01-04 and are git-ignored; nothing multi-gigabyte is ever
committed.
