---
name: process-lesson
description: >-
  Use this skill whenever a new Dutch lesson PDF is added to road_to_B1/lessons/
  or when the user asks to process a weekly lesson into .docx notes, practice
  exercises, live voice prompts, and Anki cards.
---

# Process Weekly Dutch Lesson

Follow this workflow to turn a raw lesson PDF in `road_to_B1/lessons/` into structured `.docx` study materials (Google Drive only, no `.md` files inside `road_to_B1/`) and synced Anki cards.

## Steps

1. **Inspect existing state**
   - Check `road_to_B1/lessons/` for the new PDF file.
   - Read the running curriculum index using:
     ```bash
     python3 scripts/docx_tools.py read road_to_B1/notes/index.docx
     ```
     to see the lesson number, previous topics, and any recurring mistakes to reinforce.
   - Read `road_to_B1/anki/manifest.json` and `road_to_B1/anki/config.json` to see existing card sets and the target deck.

2. **Read the lesson PDF thoroughly**
   - Use `read_file` on the PDF (review both OCR and rendered page images so formatted tables or typos are caught accurately).
   - Gently correct any typos from the raw class notes in the structured summary.

3. **Create structured `.docx` lesson notes (no `.md` files)**
   - Pipe structured Markdown directly into `python3 scripts/docx_tools.py write road_to_B1/notes/lesXX_YYYY-MM-DD.docx` containing:
     - Lesson metadata (number, date, topic)
     - Conversation highlights & useful expressions (`Het gesprek`)
     - Vocabulary table (`Vocabulair`) with Dutch, English, and usage/gender (`de`/`het`) notes
     - Grammar breakdown (`Grammatica`) with concise rules, examples, and exceptions
     - Homework & next-lesson preview (`Huiswerk / Volgende les`)
   - Update `road_to_B1/notes/index.docx` via `scripts/docx_tools.py write` with the new lesson entry, grammar topics, vocab highlights, and upcoming focus.

4. **Create weekly `.docx` practice exercises & live voice brief**
   - Pipe the worksheet Markdown directly into `python3 scripts/docx_tools.py write road_to_B1/exercises/lesXX_<topic>.docx` with a progressive mix of:
     - Targeted grammar fill-in-the-blank / transformation drills
     - Vocabulary & contrast exercises
     - Natural translation prompts (EN -> NL)
     - A short free-production prompt
     - A `<details><summary>Answer Key</summary>...</details>` block at the bottom (automatically rendered in invisible white text on a new page for agent grading).
   - Pipe a tailored **Live Voice Conversation Brief** directly into `python3 scripts/docx_tools.py write road_to_B1/exercises/lesXX_live_voice_prompt.docx`, ready to copy-paste into Gemini Live / ChatGPT Voice and incorporating the week's grammar/vocab plus active watchlist items from `road_to_B1/notes/index.docx`.
   - If AnkiConnect is reachable, optionally run `python3 scripts/anki_sync.py inspect --struggling` and weave 1–2 struggling patterns into the worksheet and live voice brief.

5. **Create & validate Anki Cloze cards**
   - Create `road_to_B1/anki/lesXX_<topic>.csv` using the project's standard Cloze CSV format:
     ```csv
     #separator:comma
     #html:false
     #notetype:Cloze
     #tags column:3
     ```
   - Follow these card-quality rules:
     - Natural, spoken Dutch sentences (15–30 cards per lesson, focused on active recall).
     - Use `{{c1::target::English hint}}` (and optional `{{c2::...}}` for paired grammar like auxiliary + participle or conjunction + verb order).
     - Put clear English translation + concise grammar cue in column 2.
     - Quote any CSV field containing a comma.
     - Tag with `lesX` plus lowercase topic tags (e.g., `les2 separable signaalwoorden`).
   - Register the new CSV in `road_to_B1/anki/manifest.json` with `"status": "pending"`.
   - Validate offline:
     ```bash
     python3 scripts/anki_sync.py validate
     ```
     Fix any validation errors before proceeding.

6. **Sync to Anki via AnkiConnect**
   - Preview and push:
     ```bash
     python3 scripts/anki_sync.py push road_to_B1/anki/lesXX_<topic>.csv --dry-run
     python3 scripts/anki_sync.py push road_to_B1/anki/lesXX_<topic>.csv
     ```
   - If Anki Desktop / AnkiConnect is not open, leave the CSV validated and `"status": "pending"` in `road_to_B1/anki/manifest.json`, and tell Eduardo the exact command to run once Anki is open.
