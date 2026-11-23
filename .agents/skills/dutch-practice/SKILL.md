---
name: dutch-practice
description: >-
  Use this skill when the user wants an interactive Dutch tutoring session,
  grammar drill, conversation practice, voice-note pronunciation coaching,
  live-voice debrief, or feedback on completed .docx worksheets in road_to_B1/.
---

# Interactive Dutch Practice & Tutoring

Use this skill to run focused, encouraging, high-retention Dutch practice sessions in chat, via voice notes, or by reviewing completed Google Docs worksheets.

## Preparation

1. Read the running curriculum index & watchlist:
   ```bash
   python3 scripts/docx_tools.py read road_to_B1/notes/index.docx
   ```
2. If AnkiConnect is available, optionally check struggling cards:
   ```bash
   python3 scripts/anki_sync.py inspect --struggling
   ```
   Weave 1–2 struggling structures naturally into the session.

## Session Modes

Ask or infer which mode Eduardo wants (or default to a balanced 5–8 prompt mix):
- **Targeted grammar drill** (e.g., Perfectum `hebben`/`zijn`, `SoFTKeTCHuP`, separable verbs, `want` vs `omdat`).
- **Mini-conversation** (short realistic Dutch chat about his weekend, work, family, daily plans, nudging him to use target structures).
- **Voice-note conversation & pronunciation coaching**:
  - When Eduardo drops an audio recording in `road_to_B1/audio/inbox/` (or shares a path), listen directly using `read_file`.
  - Give focused feedback on **pronunciation** (vowel length, `g`/`ch`, `ui`/`eu`/`ij`, word stress, natural rhythm) AND **grammar/word order**.
  - Generate a natural spoken Dutch reply or shadowing clip using `python3 scripts/dutch_tts.py "<Dutch reply>" --play` (saved to `road_to_B1/audio/tutor/` using neural `nl-NL-FennaNeural` / `Maarten`, falling back to macOS `Xander`).
- **Live Voice session debrief**: When Eduardo pastes a mistake summary or transcript from a Gemini Live / ChatGPT Voice session, log persistent patterns in `road_to_B1/notes/index.docx` and offer to push 3–5 targeted reinforcement Anki cards.
- **Worksheet review**: Read his completed Google-Drive-synced `.docx` worksheets directly via:
  ```bash
  python3 scripts/docx_tools.py read road_to_B1/exercises/<file>.docx
  ```
  (The hidden white-text Answer Key at the bottom is included in the extracted output for fast, accurate grading.)

## Coaching Rules

1. **One prompt or short batch at a time** — keep momentum conversational (1–3 prompts per turn).
2. **Correction format**:
   - Confirm what is already natural/correct.
   - Show the corrected natural Dutch sentence clearly.
   - Give a 1-sentence *why* (connect back to a lesson rule like `SoFTKeTCHuP`, `hebben`/`zijn`, V2 inversion, or `bijzin`).
   - Offer a quick follow-up variation so he actively produces the fixed pattern.
3. **Track learning over time**:
   - At the end of a session, if a clear recurring mistake or high-value new phrase came up, offer to:
     1. Update `road_to_B1/notes/index.docx` under **Recurring Mistakes & Watchlist**.
     2. Add 1–3 targeted reinforcement cards to a CSV in `road_to_B1/anki/` and sync via `scripts/anki_sync.py push`.
