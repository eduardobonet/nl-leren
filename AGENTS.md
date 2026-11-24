# Dutch Tutoring Companion — Agent Rules

This repository is Eduardo's personal Dutch tutoring companion. It turns weekly Dutch lesson PDFs into structured `.docx` notes, Google-Docs-editable practice worksheets, live voice conversation briefs, voice-note practice, and Anki Cloze flashcards managed via AnkiConnect.

## Project Structure

### Synced to Google Drive ONLY (gitignored): `road_to_B1/`
All personal study records and generated content live inside `road_to_B1/` (notes & exercises in **`.docx`** format only — no `.md` files in `road_to_B1/`):
- `road_to_B1/lessons/` — Original weekly lesson PDFs from Eduardo's tutor (read-only source records).
- `road_to_B1/notes/` — Structured lesson summaries (`lesXX_YYYY-MM-DD.docx`) plus `index.docx` (running curriculum log, grammar tracker, and recurring mistakes watchlist).
- `road_to_B1/exercises/` — Weekly practice worksheets (`lesXX_<topic>.docx`, with hidden white-text Answer Keys for agent grading) and live voice conversation briefs (`lesXX_live_voice_prompt.docx`).
- `road_to_B1/audio/` — Voice note practice: `inbox/` for Eduardo's Dutch recordings (`.m4a`/`.mp3`/`.wav`, listened to via `read_file`) and `tutor/` for spoken Dutch audio replies & shadowing clips generated via `scripts/dutch_tts.py`.
- `road_to_B1/anki/` — Anki Cloze CSV files (source of truth), `config.json` (deck & AnkiConnect settings), and `manifest.json` (tracks synced CSVs and Anki note IDs to prevent duplicates).

### Tracked in Git (reusable tooling & agent configuration)
- `AGENTS.md`, `README.md`, `.gitignore`, `.agents/skills/` — Agent rules and reusable tutoring workflows.
- `scripts/anki_sync.py` — Stdlib-only Python CLI to validate CSVs, push/update/tag cards via AnkiConnect, adopt manually imported CSVs, and inspect deck/card review stats.
- `scripts/docx_tools.py` — Stdlib-only Python CLI to write formatted `.docx` documents directly from Markdown input (`write <out.docx>`, rendering `<details>` Answer Keys in invisible white text) and read `.docx` documents back (`read <in.docx>`).
- `scripts/dutch_tts.py` — Spoken Dutch TTS CLI using neural `edge-tts` (`nl-NL-FennaNeural` / `nl-NL-MaartenNeural`) with automatic offline fallback to macOS `Xander` (`nl_NL`).

## Core Workflows & Skills

- **New weekly lesson PDF**: Use the `process-lesson` skill (`.agents/skills/process-lesson/SKILL.md`).
- **Interactive practice / speaking / grammar drills / worksheet review**: Use the `dutch-practice` skill (`.agents/skills/dutch-practice/SKILL.md`).

## Anki Conventions

- **Single deck**: All cards go into the configured deck in `road_to_B1/anki/config.json` (default: `Dutch`) and are organized using space-separated tags (e.g., `les1 perfectum irregular`).
- **CSV format**: Always use Anki's Cloze CSV format:
  ```csv
  #separator:comma
  #html:false
  #notetype:Cloze
  #tags column:3
  ```
  - Column 1 (`Text`): Natural spoken Dutch sentence with `{{c1::target::English hint}}` (and optional `{{c2::...}}`). Quote fields containing commas.
  - Column 2 (`Back Extra`): Clear English translation + concise grammar/usage cue in parentheses.
  - Column 3 (`Tags`): Space-separated lowercase tags starting with the lesson tag (`les1`, `les2`, etc.) followed by grammar/topic tags.
- **No duplicates**:
  - Always run `python3 scripts/anki_sync.py validate` before pushing.
  - Never re-upload sets marked `"status": "already_synced"` in `road_to_B1/anki/manifest.json` (such as `dutch_week1_anki_cloze-v2.csv`) unless explicitly asked to update or adopt them.
  - Use `scripts/anki_sync.py push` (which tracks note IDs in `road_to_B1/anki/manifest.json` and checks existing notes in AnkiConnect) instead of raw manual imports.

## Tutoring Style & Language Policy

- **Exercises and reviews: 100% Dutch (`Nederlands`)**:
  - Write **all practice worksheets** (`road_to_B1/exercises/*.docx`) completely in clear, natural A2/B1-level Dutch — instructions, prompts, hints, and the hidden white-text `Antwoordmodel` (use Dutch context/prompts instead of English translations).
  - Conduct **all worksheet reviews, corrections, interactive drills, voice-note feedback, and live-voice debriefs** completely in clear, encouraging Dutch.
  - Explain *waarom* simply in Dutch (bijv. *inversie / werkwoord op plaats 2*, *SoFTKeTCHuP*, *hebben of zijn*, *scheidbare werkwoorden*, *bijzin -> werkwoorden aan het einde*).
- Keep explanations concise, practical, and focused on natural spoken Dutch (avoid overly academic jargon when a clear rule + example works better).
- When correcting Eduardo's Dutch: affirm what worked, show the natural correction, briefly explain *waarom* in Dutch, and log persistent patterns in `road_to_B1/notes/index.docx`.
- Note subtle spoken-Dutch tips (e.g., `bordspel` for board game, `eten`/`gegeten` vs `drinken`/`gedronken`, Dutch particles like `even`, `maar`, `lekker`).
