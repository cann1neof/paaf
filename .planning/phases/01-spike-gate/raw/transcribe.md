# SPIKE-04 — Whisper on the code-switched corpus: lock-on / transliterate / translate

> ## ⚠️ D-05 — the caveat that must travel with every number below
>
> **This measures Whisper on SYNTHETIC Chatterbox speech, not the user's real
> code-switched speech.** Every clip transcribed here was produced by Chatterbox
> Multilingual V3 (01-05), not recorded from a human (D-04). **Chatterbox failures and
> Whisper failures are NOT separable in this setup** (D-05): when a Russian word comes out
> garbled, this evidence cannot say whether Whisper misheard it or Chatterbox mis-said it —
> especially since all 9 Russian renders were synthesized **without stress labeling**
> (`russian_text_stresser` is permanently unavailable, 01-03 / Pitfall 2). **Under SC#4 no
> repo text — README included — may claim PAAF handles the user's real code-switched speech
> on this evidence.** This caveat is binding and is carried on every row of
> `corpus/transcripts.jsonl` (`d05_caveat`). It must reach `DECISIONS.md`.
>
> A second, structural caveat rides along: the faster-whisper `Segment` dataclass carries
> **no `.language` field**, so "per-segment language" below is INFERRED from
> `all_language_probs` + output script, never read from a direct per-segment label.

## What was run

`spike/voice/transcribe.py`, `WhisperModel("large-v3", device="cpu", compute_type="int8")`
(first-party Systran repo, not the community turbo — a measurement phase must not attribute
a conversion's flaws to Whisper). Every clip in `corpus/clips/` (46 WAVs = 20 sentences ×
{matrix, embedded} + 6 untagged `none` controls) under **three conditions**, one row each,
138 rows total in `corpus/transcripts.jsonl`:

| Condition | task | multilingual | Question it answers |
|---|---|---|---|
| `transcribe_ml_false` | transcribe | **False** | The production default — does it lock to one language and apply it globally? |
| `transcribe_ml_true` | transcribe | **True** | "Detect language on every segment" — does the instrument's best case unlock code-switching? |
| `translate_ml_true` | translate | True | The "translates the rest" half — English-only target. |

`language=None` always (SPIKE-04 must never pin the language), `vad_filter=False` set
explicitly, `info.all_language_probs` + a separate `model.detect_language()` posterior
captured per clip.

---

## Headline findings

### 1. Whisper LOCKS onto exactly one language per clip — and the `multilingual=True` flag does NOT unlock it.

`info.language` is a single language for every clip under both conditions. The instrument
the whole plan was built around — `multilingual=True`, "perform language detection on every
segment" — changed **nothing measurable here**:

- `all_language_probs` posterior identical under False vs True: **46/46 clips**.
- Full transcript identical under False vs True: **44/46 clips**. The two exceptions are
  trivial (`c05__he`: a hallucinated trailing "Here." trimmed; `c12__none`: one garbled
  mis-detection reshuffled to a different garble). Neither recovers the second language.

**So the answer to "does it lock onto one language" is YES, and turning on per-segment
detection did not change the lock.** (Caveat: with no `Segment.language` field, we observe
this through `info.language` + `all_language_probs`, which are clip-level.)

### 2. What the tag does: the Chatterbox `language_id` tag — not the Whisper flag — moves the detected language.

Whisper's detected language tracks the render's dominant *acoustic* language, which the
01-05 `language_id` tag sets. The tag flipped Whisper's detected language on **9 of 20**
sentences (e.g. `c04` en→ru, `c08` en→he, `c16` en→ru). This is a property of the synthetic
input, not of Whisper's language ID — a concrete instance of D-05: the "STT result" here is
partly a TTS result.

### 3. What it does with the *other* language: TRANSLITERATE when the matrix is Latin; PRESERVE the native script only when it locked to the non-Latin language.

- **Embedded language in an English/Latin matrix → transliterated or garbled into Latin,
  never preserved in native script:**
  - `c02` Hebrew `סופגניות` → **"Sifakonat"**; `c14` `רחוב דיזנגוף` → **"Rehuv'Dai's engulf"**.
  - `c03` Spanish `sobremesa` → **"Sober Misa"**.
  - `c07` Russian `а он всё равно перезвонил три раза` → **"…wrap it up here as when you'll tree raza"**.
- **When Whisper locked to Russian or Hebrew, it CAN keep both scripts** (code-switch
  preserved): `c04__ru` → `Я уже отправил отчет, but the attachment never went through`;
  `c12__ru` keeps Cyrillic + `Plaza Mayor`; `c18__ru` keeps `«Ресторан»` + `but my phone…`.
- **Same-script Russian/English pair (the hardest D-02 category) collapses:** `c19`
  `СОК`/`COK` → **"Sock"/"Cock"**; `c20` (ru tag) → **"OnWebRailPyroid torqued, and the form
  rejected data stopped"** — near-total loss. This is exactly where Chatterbox-vs-Whisper
  blame is inseparable (D-05): a Russian password word rendered without stress, then heard
  as English.

### 4. The translate probe TRANSLATES the rest into English — confirmed.

`task="translate"` renders the whole utterance in English when it had locked to a non-English
language: `c09` he → **"Remind me to take the ball at 8.45 tomorrow morning"**; `c13` es →
**"Alejandro said that Dmitry arrives on Tuesday morning"**; `c16` ru → English. When the
clip already detected English, translate ≈ transcribe (a near no-op). So the "translates the
rest" half of SPIKE-04 is real: the translate task does not preserve the source languages —
it flattens everything to English.

### 5. Untagged (`none`) controls: default to English, and fail loudly only when no English is present.

The corpus is English-dominant, so 5/6 untagged controls detect `en` with high confidence.
The one exception is `c12__none` (Russian + Spanish, **no** English): it fell to `fr(0.29)`
— a low-confidence misdetection, the honest signature of "no tag, no anchor language."

---

## Per-language-pair summary (matrix render shown; full grid in `transcripts.jsonl`)

| Pair (matrix→embedded) | Locked to | Embedded handled as | Example |
|---|---|---|---|
| en→ru (`c01`) | en | transliterated (`кефир`→"kefir") | clean matrix, foreign noun anglicized |
| en→he (`c02`,`c14`) | en | transliterated/garbled (`סופגניות`→"Sifakonat") | native script lost |
| en→es (`c03`,`c17`) | en | transliterated (`sobremesa`→"Sober Misa"); `y medio` kept | Latin embedded partly survives |
| ru→en (`c04`) | ru | **preserved** (Cyrillic + Latin both kept) | best case — true code-switch retained |
| he→en (`c05`,`c08`,`c09`) | he/en | Hebrew kept when locked to he; digits mangled (`15:00`→"15.0") | RTL+digits lossy |
| es→en (`c06`,`c15`) | es | English embedded kept in Latin | numbers drift (`500`→"50") |
| en→ru mid-clause (`c07`) | en | Russian garbled to Latin nonsense | hardest for an English lock |
| proper nouns ru/es (`c12`,`c13`) | ru/es | other name transliterated (`Алехандро`↔"Alejandro"/"Dmitri") | names mostly survive |
| same-script ru/en (`c18`,`c19`,`c20`) | mixed | **collapses** (`СОК`→"Sock", `ТОРТ`→garble) | worst category; D-05 blame inseparable |

Numbers and units drifted on several clips (`c11` `1.5`→"5", `c15` `500`→"50", `c16` `20`→"8"),
but per D-05 this is as likely a Chatterbox synthesis artifact as a Whisper error and the two
cannot be separated here.

---

## Correction to the old "STT is a non-issue" claim (SC#4)

The prior project note that STT is a non-issue is **not supported** by this evidence, and
must not reach a README unqualified. On synthetic code-switched input Whisper **locks to one
language and either transliterates, garbles, or (under `task=translate`) flattens the other
to English**; the per-segment `multilingual=True` flag did not change this. What this does
*not* establish — and what SC#4 forbids claiming — is how Whisper behaves on the **user's
real** code-switched speech: that requires real-voice data (deferred to Phase 7), because
D-05 makes Chatterbox and Whisper failures inseparable in everything above.

---

## Instrument notes / honest limitations

- **`multilingual` gave no lift on this corpus.** That is a finding, not a harness bug — the
  flag was exercised (both conditions ran on all 46 clips, verified by
  `test_transcribe_harness.py`), the posteriors were simply identical. On genuinely
  segmented multi-language audio it may matter; these clips are short and single-locked.
- **`Segment` has no `.language`.** Per-segment language above is inferred from script +
  `all_language_probs`, never a direct label.
- **CPU-only** (CTranslate2 has no Metal backend): ~13 s/clip across 3 conditions, ~30 min
  for the corpus. Not a latency measurement (SPIKE-03 owns that).
- **All numbers inherit D-05.** Repeated because it is the single most important sentence in
  this file.
