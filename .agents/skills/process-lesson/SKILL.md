---
name: process-lesson
description: >-
  Use this skill whenever a new Dutch lesson PDF is added to road_to_B1/ (or
  road_to_B1/lesXX/) or when the user asks to process a weekly lesson into .docx
  overview notes, practice exercises, live voice prompts, and Anki cards.
---

# Process Weekly Dutch Lesson

Follow this workflow to turn a raw lesson PDF into a clean lesson folder `road_to_B1/lesXX/` with structured `.docx` study materials (Google Drive only, no `.md` files inside `road_to_B1/`) and synced Anki cards.

## Steps

1. **Inspect existing state**
   - Check `road_to_B1/` and `road_to_B1/lesXX/` for the new PDF file (if the PDF was dropped at the root of `road_to_B1/`, move it into `road_to_B1/lesXX/`).
   - Read the running curriculum index using:
     ```bash
     python3 scripts/docx_tools.py read road_to_B1/index.docx
     ```
     to see the lesson number, previous topics, and any recurring mistakes to reinforce.
   - Read `road_to_B1/anki/manifest.json` and `road_to_B1/anki/config.json` to see existing card sets and the target deck.

2. **Read the lesson PDF thoroughly**
   - Use `read_file` on the PDF (review both OCR and rendered page images so formatted tables or typos are caught accurately).
   - Gently correct any typos from the raw class notes in the structured overview.

3. **Create structured `.docx` lesson overview (no `.md` files)**
   - Pipe structured Markdown directly into `python3 scripts/docx_tools.py write road_to_B1/lesXX/overzicht_YYYY-MM-DD.docx` containing:
     - Lesson metadata (number, date, topic)
     - Conversation highlights & useful expressions (`Het gesprek`)
     - Vocabulary table (`Vocabulair`) with Dutch, explanation/translation, and usage/gender (`de`/`het`) notes
     - Grammar breakdown (`Grammatica`) with concise rules, examples, and exceptions
     - Homework & next-lesson preview (`Huiswerk / Volgende les`)
   - Update `road_to_B1/index.docx` via `scripts/docx_tools.py write` with the new lesson entry, grammar topics, vocab highlights, and upcoming focus.

4. **Create weekly `.docx` practice exercises & live voice brief (100% in Dutch)**
   - Pipe the worksheet Markdown directly into `python3 scripts/docx_tools.py write road_to_B1/lesXX/oefeningen/oefening_<onderwerp>.docx`. **Write the entire worksheet in clear A2/B1 Dutch** (instructions, hints, exercises, and hidden white-text `Antwoordmodel` — no English instructions or EN->NL translations). Include a progressive mix of:
     - Invuloefeningen (`hebben`/`zijn`, werkwoordsvormen, signaalwoorden)
     - Zinnen herschrijven (bijv. presens -> perfectum, `want` -> `omdat`)
     - Woordenschat- en contrastoefeningen met Nederlandse context
     - Een korte schrijf- of spreekopdracht
     - A `<details><summary>Antwoordmodel</summary>...</details>` block at the bottom (automatically rendered in invisible white text on a new page for agent grading).
   - Pipe a tailored **Live Voice Conversation Brief** (in Dutch) directly into `python3 scripts/docx_tools.py write road_to_B1/lesXX/live_voice_prompt.docx`, ready to copy-paste into Gemini Live / ChatGPT Voice and incorporating the week's grammar/vocab plus active watchlist items from `road_to_B1/index.docx`.
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
     - Use `{{c1::target::hint}}` (and optional `{{c2::...}}` for paired grammar like auxiliary + participle or conjunction + verb order). **Never spoil the Dutch target or grammar rule in the front hint**: use neutral `hebben / zijn` for auxiliary choice/conjugation, plain meaning hints for verbs/vocab (no Dutch verb spelling like `(op-ge-staan)`), and put all grammar explanations in column 2 (`Back Extra`).
     - Put clear translation + concise Dutch grammar cue in column 2.
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
