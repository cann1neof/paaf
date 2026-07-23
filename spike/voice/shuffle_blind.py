"""Blind-shuffle harness for the SPIKE-02 listening pass (D-14).

THROWAWAY (SC#5 / D-18). Stdlib only — this module must import in *both* spike venvs and
must never grow a torch/chatterbox dependency, because it does no synthesis: it moves
files and records where they went.

What problem this solves
------------------------
D-13 says the Hebrew verdict is captured as **verbatim impressions**, and D-14 says those
impressions must be taken **blind to ``language_id``**. That second constraint is not
ceremony. SPIKE-01's actual question is whether the ``language_id`` tag changes how a
mixed-script sentence renders; a judge who can see ``c08__he.wav`` in the filename has
been told the answer before pressing play, and will hear the tag as much as the audio.

So: rename every clip to an opaque ``blind_NNN`` before listening, record the truth in a
``mapping.json`` that lives **outside** the listening directory, judge, then join the tags
back afterwards.

Naming convention (shared with the 01-05 render)
------------------------------------------------
Rendered clips are named ``{clip_id}__{language_id}{suffix}`` — e.g. ``c08__he.wav``.
D-06 renders each corpus sentence twice, once tagged with its matrix language and once
with its embedded language, so ``c08`` yields ``c08__he.wav`` and ``c08__en.wav`` and the
corpus's 20 sentences yield ~40 clips. A labeled subset gets a third, *untagged* render
(``language_id=None``, RESEARCH Open Q5) written as ``c08__none.wav`` — see
``UNTAGGED_TAG``.

Reproducibility
---------------
``shuffle_blind`` takes an explicit integer ``seed``; there is no implicit default and no
call to the global ``random`` state. 01-RESEARCH's pitfall list is emphatic that every
knob of this phase must be recorded so Phase 7 can mechanically re-run and diff (D-07),
and an unseeded shuffle would make the listening order unreproducible — which matters the
moment a verbatim impression says "the third one was much worse than the second".
The seed is written into ``mapping.json`` as well, so the record survives the shell
history.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

__all__ = [
    "LANGUAGES",
    "UNTAGGED_TAG",
    "JUDGABLE_TAGS",
    "ClipTag",
    "clip_filename",
    "parse_clip_name",
    "shuffle_blind",
    "load_mapping",
    "join_back",
    "judgment_template",
]

#: The four languages this phase measures. A clip tagged anything else is a typo, and a
#: typo'd tag that is silently accepted would be judged as if it were real.
LANGUAGES: frozenset[str] = frozenset({"en", "ru", "he", "es"})

#: The untagged control condition (RESEARCH Open Q5): ``generate()`` guards with
#: ``if language_id and ...``, so ``language_id=None`` skips both the language-token
#: prepend and the per-language normalization. That third condition is what separates
#: "the tag did nothing" from "the tag did the wrong thing", so it has to be renderable,
#: nameable and judgeable — which means the shared filename convention must carry it.
#: ``None`` is not expressible in a filename, so it is spelled ``none`` on disk.
UNTAGGED_TAG = "none"

#: Every tag a rendered clip may legitimately carry. ``LANGUAGES`` alone is deliberately
#: kept as the set of *languages*; this is the set of *conditions*.
JUDGABLE_TAGS: frozenset[str] = LANGUAGES | {UNTAGGED_TAG}

#: ``{clip_id}__{language_id}``. The double underscore keeps clip ids free to contain a
#: single underscore without making the split ambiguous.
_SEPARATOR = "__"
_CLIP_NAME_RE = re.compile(r"^(?P<clip_id>.+?)__(?P<language_id>[A-Za-z-]+)$")

#: Opaque listening name. Zero-padded so lexical order == listening order for any N < 1000.
_BLIND_TEMPLATE = "blind_{index:03d}{suffix}"
_BLIND_NAME_RE = re.compile(r"^blind_(?P<index>\d{3,})")

MAPPING_FILENAME = "mapping.json"
MAPPING_VERSION = 1


class ClipTag(NamedTuple):
    """The two facts a blind name must hide and ``join_back`` must restore."""

    clip_id: str
    language_id: str


# --------------------------------------------------------------------------------------
# Naming
# --------------------------------------------------------------------------------------


def clip_filename(clip_id: str, language_id: str | None, suffix: str = ".wav") -> str:
    """Build the tagged clip filename the renderer should write.

    Exposed so the 01-05 render and this harness cannot drift apart: there is exactly one
    definition of the convention and both sides call it.

    ``language_id=None`` — the untagged control condition Chatterbox accepts — is written
    as ``{clip_id}__none.wav``. Passing the string ``"none"`` is equivalent, so a renderer
    that has already stringified its condition does not have to convert back.
    """
    if _SEPARATOR in clip_id:
        raise ValueError(
            f"clip_id {clip_id!r} contains {_SEPARATOR!r}, which is the field separator; "
            "the name could not be parsed back unambiguously."
        )
    if not clip_id.strip():
        raise ValueError("clip_id must be a non-empty string")
    tag = UNTAGGED_TAG if language_id is None else language_id
    if tag not in JUDGABLE_TAGS:
        raise ValueError(
            f"language_id {language_id!r} is not one of {sorted(JUDGABLE_TAGS)}; refusing "
            "to name a clip after a tag this phase does not measure."
        )
    return f"{clip_id}{_SEPARATOR}{tag}{suffix}"


def parse_clip_name(
    name: str | Path, *, allowed_languages: frozenset[str] = JUDGABLE_TAGS
) -> ClipTag:
    """Recover ``(clip_id, language_id)`` from a rendered clip filename.

    Raises ``ValueError`` on anything that does not conform. This is deliberately strict:
    a clip that cannot be parsed is a clip whose tag would be *guessed* at join-back time,
    and a guessed tag silently corrupts the one measurement SPIKE-01 exists to take.
    """
    stem = Path(name).stem
    match = _CLIP_NAME_RE.match(stem)
    if match is None:
        raise ValueError(
            f"Clip name {Path(name).name!r} does not match the "
            f"'{{clip_id}}{_SEPARATOR}{{language_id}}' convention (e.g. 'c08__he.wav')."
        )
    clip_id = match.group("clip_id")
    language_id = match.group("language_id")
    if language_id not in allowed_languages:
        raise ValueError(
            f"Clip {Path(name).name!r} carries language tag {language_id!r}, which is not "
            f"one of {sorted(allowed_languages)}. Refusing to judge a clip whose tag is a typo."
        )
    return ClipTag(clip_id=clip_id, language_id=language_id)


# --------------------------------------------------------------------------------------
# Shuffle
# --------------------------------------------------------------------------------------


def shuffle_blind(
    src_dir: str | Path,
    blind_dir: str | Path | None = None,
    *,
    seed: int,
    pattern: str = "*.wav",
    mapping_path: str | Path | None = None,
    allowed_languages: frozenset[str] = JUDGABLE_TAGS,
    overwrite: bool = False,
) -> Path:
    """Copy every clip in ``src_dir`` to an opaque name in ``blind_dir`` and record the map.

    Args:
        src_dir: directory of tagged clips named ``{clip_id}__{language_id}{suffix}``.
        blind_dir: destination for the opaque copies. Defaults to a sibling ``clips_blind/``.
        seed: explicit integer seed. Required, keyword-only, no default — an unrecorded
            listening order is not a measurement.
        pattern: glob for source clips. ``*.wav`` by default; the function itself is
            format-agnostic and works on any directory of files.
        mapping_path: where to write ``mapping.json``. Defaults to a sibling of
            ``blind_dir``, never inside it (see below).
        allowed_languages: tag whitelist; an unknown tag raises.
        overwrite: allow writing into a non-empty ``blind_dir``.

    Returns:
        Path to the written ``mapping.json``.

    The source files are **copied, not moved** — the tagged render stays intact as the
    committed evidence (D-07), and a botched listening pass costs a re-shuffle rather than
    a re-render.
    """
    src = Path(src_dir)
    if not src.is_dir():
        raise ValueError(f"src_dir {src} is not a directory")

    dest = Path(blind_dir) if blind_dir is not None else src.parent / "clips_blind"
    mapping_file = (
        Path(mapping_path) if mapping_path is not None else dest.parent / MAPPING_FILENAME
    )

    # The whole point of D-14 is that the listening directory reveals nothing. A mapping
    # sitting next to the clips being judged defeats it in the most banal possible way.
    if mapping_file.resolve().parent == dest.resolve():
        raise ValueError(
            f"mapping_path {mapping_file} is inside the blind directory {dest}. The mapping "
            "is exactly what the judge must not see (D-14); write it to a sibling directory."
        )

    sources = sorted(p for p in src.glob(pattern) if p.is_file())
    if not sources:
        raise ValueError(f"No files matching {pattern!r} in {src} — nothing to shuffle.")

    # Parse first, copy nothing until every name is known good.
    tags: list[ClipTag] = [
        parse_clip_name(p.name, allowed_languages=allowed_languages) for p in sources
    ]
    duplicates = sorted({t for t in tags if tags.count(t) > 1})
    if duplicates:
        raise ValueError(
            f"Duplicate (clip_id, language_id) pairs in {src}: {duplicates}. Two files "
            "claiming the same tag means one render silently overwrote the other."
        )

    if dest.exists() and any(dest.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Blind directory {dest} is not empty. Pass overwrite=True only if you are sure — "
            "mixing clips from two renders into one listening pass invalidates the pass."
        )
    dest.mkdir(parents=True, exist_ok=True)

    # Deterministic: the base order is the sorted source list, then one seeded shuffle.
    order = list(range(len(sources)))
    random.Random(seed).shuffle(order)

    clips: dict[str, dict[str, str]] = {}
    for blind_index, source_index in enumerate(order):
        source = sources[source_index]
        tag = tags[source_index]
        blind_name = _BLIND_TEMPLATE.format(index=blind_index, suffix=source.suffix)
        shutil.copy2(source, dest / blind_name)
        clips[blind_name] = {
            "clip_id": tag.clip_id,
            "language_id": tag.language_id,
            "source_name": source.name,
        }

    if len(clips) != len(sources):  # pragma: no cover - defensive
        raise AssertionError("blind name collision — refusing to write a lossy mapping")

    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.write_text(
        json.dumps(
            {
                "version": MAPPING_VERSION,
                "seed": seed,
                "pattern": pattern,
                "source_dir": str(src),
                "blind_dir": str(dest),
                "count": len(clips),
                "clips": clips,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return mapping_file


# --------------------------------------------------------------------------------------
# Join back
# --------------------------------------------------------------------------------------


def load_mapping(mapping_path: str | Path) -> dict[str, Any]:
    """Read ``mapping.json`` and verify it is still a bijection before anyone trusts it."""
    path = Path(mapping_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    clips = data.get("clips")
    if not isinstance(clips, dict) or not clips:
        raise ValueError(f"{path} has no 'clips' object")

    tags = [ClipTag(v["clip_id"], v["language_id"]) for v in clips.values()]
    if len(set(tags)) != len(tags):
        duplicates = sorted({t for t in tags if tags.count(t) > 1})
        raise ValueError(f"{path} maps two blind names to the same clip: {duplicates}")
    if data.get("count") is not None and data["count"] != len(clips):
        raise ValueError(
            f"{path} declares count={data['count']} but carries {len(clips)} clips — "
            "the mapping was truncated or hand-edited."
        )
    return data


def judgment_template(mapping_path: str | Path, out_path: str | Path) -> Path:
    """Write a blank judgment file keyed by blind name, in the shape ``join_back`` reads.

    D-13 wants verbatim impressions with no rating scale, which is easy to record badly.
    This gives the listening pass a file to type into whose keys already line up with the
    mapping, so no clip is silently skipped and no impression is orphaned at join time.
    Contains **no** tags — it is safe to keep open while judging.
    """
    data = load_mapping(mapping_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({name: "" for name in sorted(data["clips"])}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return out


def join_back(
    mapping_path: str | Path,
    judgments: Mapping[str, Any] | str | Path | None = None,
    *,
    require_complete: bool = False,
) -> list[dict[str, Any]]:
    """Restore ``clip_id`` and ``language_id`` for every blind clip, after judging.

    Args:
        mapping_path: the ``mapping.json`` written by :func:`shuffle_blind`.
        judgments: optional blind-name -> verbatim impression, either inline or as a path
            to a JSON file in :func:`judgment_template` shape.
        require_complete: raise if any blind clip has no judgment. Off by default because
            a partial listening pass is a legitimate intermediate state (D-19's stopping
            rule is about verdicts, not exhaustiveness).

    Returns:
        One record per clip, sorted by ``clip_id`` then ``language_id`` so matrix/embedded
        pairs of the same sentence land next to each other — which is the comparison
        SPIKE-01 actually wants to read.
    """
    data = load_mapping(mapping_path)

    if judgments is None:
        notes: dict[str, Any] = {}
    elif isinstance(judgments, (str, Path)):
        notes = json.loads(Path(judgments).read_text(encoding="utf-8"))
    else:
        notes = dict(judgments)

    unknown = sorted(set(notes) - set(data["clips"]))
    if unknown:
        raise ValueError(
            f"Judgments reference blind names absent from the mapping: {unknown}. "
            "The judgment file and the mapping came from different shuffles."
        )

    records: list[dict[str, Any]] = []
    for blind_name, info in data["clips"].items():
        judgment = notes.get(blind_name)
        if require_complete and not (isinstance(judgment, str) and judgment.strip()):
            raise ValueError(f"No judgment recorded for {blind_name}")
        records.append(
            {
                "blind_name": blind_name,
                "clip_id": info["clip_id"],
                "language_id": info["language_id"],
                "source_name": info["source_name"],
                "judgment": judgment,
            }
        )

    records.sort(key=lambda r: (r["clip_id"], r["language_id"]))
    return records


# --------------------------------------------------------------------------------------
# CLI — convenience only; every entry point above is importable and tested directly.
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin wrapper
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_shuffle = sub.add_parser("shuffle", help="copy clips to opaque names + write mapping.json")
    p_shuffle.add_argument("src_dir")
    p_shuffle.add_argument("blind_dir", nargs="?", default=None)
    p_shuffle.add_argument("--seed", type=int, required=True)
    p_shuffle.add_argument("--pattern", default="*.wav")
    p_shuffle.add_argument("--mapping", default=None)
    p_shuffle.add_argument("--overwrite", action="store_true")
    p_shuffle.add_argument("--template", default=None, help="also write a blank judgment file here")

    p_join = sub.add_parser("join", help="restore tags after judging")
    p_join.add_argument("mapping")
    p_join.add_argument("--judgments", default=None)
    p_join.add_argument("--require-complete", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "shuffle":
        mapping = shuffle_blind(
            args.src_dir,
            args.blind_dir,
            seed=args.seed,
            pattern=args.pattern,
            mapping_path=args.mapping,
            overwrite=args.overwrite,
        )
        print(mapping)
        if args.template:
            print(judgment_template(mapping, args.template))
        return 0

    records = join_back(args.mapping, args.judgments, require_complete=args.require_complete)
    json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
