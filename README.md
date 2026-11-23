# Dutch Tutoring Companion

A companion workspace for weekly Dutch lessons: turning tutor lesson PDFs into `.docx` study notes, Google-Docs-editable practice worksheets, live voice conversation briefs, voice-note pronunciation coaching, and Anki Cloze flashcards synced via AnkiConnect.

## Folder Structure

```text
.
├── road_to_B1/            # Synced with Google Drive ONLY (gitignored)
│   ├── lessons/           # Weekly lesson PDFs from tutor (source records)
│   ├── notes/             # Structured .docx notes + index.docx curriculum tracker
│   ├── exercises/         # Editable .docx worksheets (hidden white Answer Key) + live voice prompts
│   ├── audio/             # inbox/ (your voice memos) and tutor/ (spoken Dutch replies)
│   └── anki/              # Anki Cloze CSV decks, config.json, and manifest.json
├── scripts/               # CLI tooling (anki_sync.py, docx_tools.py, dutch_tts.py)
├── AGENTS.md              # Always-on tutoring & Anki conventions for the AI agent
└── .agents/skills/        # Reusable workflows (process-lesson, dutch-practice)
```

## Google Drive Setup

Point **Google Drive for Desktop** (`Preferences → My Mac → Add folder`) to **`road_to_B1/`** so all lesson PDFs, `.docx` notes, editable `.docx` worksheets, live voice prompts, audio clips, and Anki CSVs sync automatically to Drive (while Git stays clean with only tooling and agent config).

## One-Time AnkiConnect Setup

To let `scripts/anki_sync.py` push, update, tag, and inspect cards directly in Anki Desktop:

1. Open **Anki** (`/Applications/Anki.app`).
2. Go to **Tools → Add-ons → Get Add-ons...**
3. Enter code **`2055492159`** (AnkiConnect) and click **OK**.
4. Fully quit (`Cmd+Q`) and reopen Anki.
5. Verify the connection:
   ```bash
   python3 scripts/anki_sync.py status
   ```

## Weekly Workflow

1. Drop the new lesson PDF into `road_to_B1/lessons/`.
2. Ask the agent to process the new lesson (`process-lesson` skill):
   - Creates `road_to_B1/notes/lesXX_YYYY-MM-DD.docx` and updates `road_to_B1/notes/index.docx`.
   - Creates editable `road_to_B1/exercises/lesXX_<topic>.docx` (Answer Key hidden in white text) and `road_to_B1/exercises/lesXX_live_voice_prompt.docx`.
   - Creates a validated Cloze CSV in `road_to_B1/anki/lesXX_<topic>.csv` and pushes new cards to Anki via `scripts/anki_sync.py push`.
3. Complete worksheets directly in Google Docs (`road_to_B1/exercises/`), practice live speaking using `lesXX_live_voice_prompt.docx`, or drop voice memos in `road_to_B1/audio/inbox/` for pronunciation & grammar coaching.

## CLI Reference

### `.docx` Notes & Worksheets (`scripts/docx_tools.py`)
```bash
# Write a formatted .docx directly from Markdown stdin (hides <details> Answer Key in white text)
python3 scripts/docx_tools.py write road_to_B1/exercises/les01_perfectum.docx < draft.md

# Read any .docx document (notes, index, or completed worksheet) as plain text
python3 scripts/docx_tools.py read road_to_B1/exercises/les01_perfectum.docx
```

### Voice & Conversation Practice (`scripts/dutch_tts.py`)
```bash
# Generate spoken Dutch audio (neural edge-tts Fenna/Maarten + offline macOS Xander fallback)
python3 scripts/dutch_tts.py "Hoi Eduardo! Wat heb je dit weekend gedaan?" --play
python3 scripts/dutch_tts.py "Ik ben gisteren naar de winkel gefietst." --voice maarten --rate +0%
```

### Anki Sync (`scripts/anki_sync.py`)
```bash
python3 scripts/anki_sync.py status
python3 scripts/anki_sync.py validate
python3 scripts/anki_sync.py push road_to_B1/anki/les01_perfectum.csv --dry-run
python3 scripts/anki_sync.py push road_to_B1/anki/les01_perfectum.csv
python3 scripts/anki_sync.py adopt road_to_B1/anki/dutch_week1_anki_cloze-v2.csv
python3 scripts/anki_sync.py inspect --struggling
```
