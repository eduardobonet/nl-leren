#!/usr/bin/env python3
"""AnkiConnect management CLI for the Dutch Tutoring Companion.

Zero external dependencies (Python 3 stdlib only).
Manages Anki Cloze CSV sets in anki/, validates formatting offline, and pushes,
updates, adopts, and inspects cards via AnkiConnect (http://127.0.0.1:8765).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
ANKI_DIR = ROOT_DIR / "road_to_B1" / "anki"
CONFIG_PATH = ANKI_DIR / "config.json"
MANIFEST_PATH = ANKI_DIR / "manifest.json"

CLOZE_RE = re.compile(r"\{\{c(\d+)::([^}]+)\}\}")


class AnkiConnectError(RuntimeError):
    """Raised when AnkiConnect returns an error or cannot be reached."""


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_config() -> dict[str, Any]:
    return load_json(
        CONFIG_PATH,
        {
            "ankiconnect_url": "http://127.0.0.1:8765",
            "deck": "Dutch",
            "notetype": "Cloze",
            "auto_sync_ankiweb": True,
        },
    )


def load_manifest() -> dict[str, Any]:
    return load_json(MANIFEST_PATH, {"version": 1, "sets": {}})


def anki_invoke(action: str, params: dict[str, Any] | None = None, url: str | None = None) -> Any:
    cfg = load_config()
    endpoint = url or cfg["ankiconnect_url"]
    payload = {"action": action, "version": 6}
    if params is not None:
        payload["params"] = params

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise AnkiConnectError(
            f"Could not connect to AnkiConnect at {endpoint}. "
            "Make sure Anki Desktop is running with add-on 2055492159 installed."
        ) from exc

    if body.get("error") is not None:
        raise AnkiConnectError(f"AnkiConnect error for '{action}': {body['error']}")
    return body.get("result")


def card_key(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def plain_sentence(text: str) -> str:
    """Strip Cloze markup {{cN::answer::hint}} -> answer for stable matching across hint edits."""
    def _repl(match: re.Match[str]) -> str:
        return match.group(2).split("::", 1)[0]

    rendered = CLOZE_RE.sub(_repl, text)
    return " ".join(rendered.strip().lower().split())


def sentence_key(text: str) -> str:
    return "s:" + hashlib.sha1(plain_sentence(text).encode("utf-8")).hexdigest()[:12]


def parse_anki_csv(path: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Parse an Anki Cloze CSV with #header directives."""
    headers: dict[str, str] = {}
    data_lines: list[tuple[int, str]] = []

    raw_lines = path.read_text(encoding="utf-8-sig").splitlines()
    for idx, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if ":" in stripped[1:]:
                k, v = stripped[1:].split(":", 1)
                headers[k.strip().lower()] = v.strip()
            continue
        data_lines.append((idx, line))

    sep_map = {"comma": ",", "tab": "\t", "semicolon": ";"}
    delimiter = sep_map.get(headers.get("separator", "comma").lower(), ",")

    cards: list[dict[str, Any]] = []
    for line_no, raw in data_lines:
        row = next(csv.reader([raw], delimiter=delimiter))
        cards.append(
            {
                "line": line_no,
                "raw_cols": row,
                "text": row[0].strip() if len(row) > 0 else "",
                "extra": row[1].strip() if len(row) > 1 else "",
                "tags": row[2].strip().split() if len(row) > 2 else [],
            }
        )
    return headers, cards


def validate_csv_files(paths: list[Path]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    seen_texts: dict[str, str] = {}

    for path in paths:
        if not path.exists():
            errors.append(f"{path}: file not found")
            continue

        headers, cards = parse_anki_csv(path)
        if headers.get("notetype", "").lower() != "cloze":
            errors.append(f"{path}: missing or invalid '#notetype:Cloze' header")
        if headers.get("tags column") != "3":
            errors.append(f"{path}: missing or invalid '#tags column:3' header")
        if not cards:
            errors.append(f"{path}: contains no cards")

        for card in cards:
            loc = f"{path.name}:{card['line']}"
            if len(card["raw_cols"]) != 3:
                errors.append(f"{loc}: expected 3 columns, got {len(card['raw_cols'])}")
                continue
            text = card["text"]
            extra = card["extra"]
            tags = card["tags"]

            if not text:
                errors.append(f"{loc}: empty Text (column 1)")
            if not extra:
                errors.append(f"{loc}: empty Back Extra (column 2)")
            if not tags:
                errors.append(f"{loc}: missing tags (column 3)")

            matches = CLOZE_RE.findall(text)
            if not matches:
                errors.append(f"{loc}: no valid {{c1::...}} cloze deletion found")
            if text.count("{{") != text.count("}}"):
                errors.append(f"{loc}: unbalanced '{{{{' / '}}}}' braces")

            norm = " ".join(text.lower().split())
            if norm in seen_texts:
                errors.append(f"{loc}: duplicate card text (also in {seen_texts[norm]})")
            else:
                seen_texts[norm] = loc

    return (len(errors) == 0), errors


def resolve_cloze_fields(notetype: str) -> tuple[str, str]:
    """Detect Text and Back Extra/Extra field names for the Cloze model."""
    fields = anki_invoke("modelFieldNames", {"modelName": notetype})
    if not fields or len(fields) < 2:
        raise AnkiConnectError(f"Note type '{notetype}' not found or has <2 fields: {fields}")
    text_field = "Text" if "Text" in fields else fields[0]
    if "Back Extra" in fields:
        extra_field = "Back Extra"
    elif "Extra" in fields:
        extra_field = "Extra"
    else:
        extra_field = fields[1]
    return text_field, extra_field


def find_existing_note_id(text: str, text_field: str) -> int | None:
    """Search Anki for an existing note with exact matching Text field."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    query = f'"{text_field}:{escaped}"'
    ids = anki_invoke("findNotes", {"query": query})
    if not ids:
        return None
    infos = anki_invoke("notesInfo", {"notes": ids})
    for info in infos:
        field_val = info.get("fields", {}).get(text_field, {}).get("value", "")
        if field_val.strip() == text.strip():
            return int(info["noteId"])
    return None


def cmd_validate(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.files] if args.files else sorted(ANKI_DIR.glob("*.csv"))
    if not paths:
        print("No CSV files found in road_to_B1/anki/.")
        return 0

    ok, errors = validate_csv_files(paths)
    total_cards = 0
    for path in paths:
        if path.exists():
            _, cards = parse_anki_csv(path)
            total_cards += len(cards)
            print(f"  {path.name}: {len(cards)} cards")

    if ok:
        print(f"OK: {len(paths)} file(s), {total_cards} total cards validated with 0 errors.")
        return 0

    print("\nValidation errors:")
    for err in errors:
        print(f"  - {err}")
    return 1


def cmd_status(_args: argparse.Namespace) -> int:
    cfg = load_config()
    manifest = load_manifest()
    print(f"Configured deck: {cfg['deck']} | Note type: {cfg['notetype']}")
    print(f"AnkiConnect URL: {cfg['ankiconnect_url']}")

    print("\nLocal CSV sets:")
    for csv_path in sorted(ANKI_DIR.glob("*.csv")):
        _, cards = parse_anki_csv(csv_path)
        meta = manifest.get("sets", {}).get(csv_path.name, {})
        status = meta.get("status", "untracked")
        tracked = len(meta.get("notes", {}))
        print(f"  - {csv_path.name}: {len(cards)} cards | status={status} | tracked_ids={tracked}")

    print("\nAnkiConnect check:")
    try:
        version = anki_invoke("version")
        decks = anki_invoke("deckNames")
        text_field, extra_field = resolve_cloze_fields(cfg["notetype"])
        print(f"  Connected! AnkiConnect v{version}")
        print(f"  Cloze fields: {text_field!r}, {extra_field!r}")
        print(f"  Configured deck exists: {cfg['deck'] in decks}")
        print(f"  Available decks: {', '.join(decks)}")
        return 0
    except AnkiConnectError as exc:
        print(f"  NOT CONNECTED: {exc}")
        return 1


def cmd_adopt(args: argparse.Namespace) -> int:
    cfg = load_config()
    manifest = load_manifest()
    text_field, _ = resolve_cloze_fields(cfg["notetype"])

    for file_str in args.files:
        path = Path(file_str)
        if not path.is_absolute() and not path.exists():
            path = ANKI_DIR / file_str
        _, cards = parse_anki_csv(path)
        entry = manifest.setdefault("sets", {}).setdefault(
            path.name, {"status": "synced", "notes": {}}
        )
        notes_map: dict[str, int] = entry.setdefault("notes", {})
        matched = 0
        missing = 0
        found_decks: set[str] = set()

        for card in cards:
            nid = find_existing_note_id(card["text"], text_field)
            if nid is not None:
                notes_map[card_key(card["text"])] = nid
                matched += 1
                cids = anki_invoke("findCards", {"query": f"nid:{nid}"})
                if cids:
                    cinfos = anki_invoke("cardsInfo", {"cards": cids[:1]})
                    if cinfos:
                        found_decks.add(cinfos[0].get("deckName", ""))
            else:
                missing += 1

        entry["status"] = "synced" if missing == 0 else "already_synced"
        print(
            f"{path.name}: adopted {matched}/{len(cards)} notes "
            f"(missing={missing}, decks={sorted(d for d in found_decks if d)})"
        )

    save_json(MANIFEST_PATH, manifest)
    print(f"Updated {MANIFEST_PATH.relative_to(ROOT_DIR)}")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    cfg = load_config()
    manifest = load_manifest()
    deck = args.deck or cfg["deck"]
    notetype = cfg["notetype"]

    if args.all:
        paths = []
        for csv_path in sorted(ANKI_DIR.glob("*.csv")):
            meta = manifest.get("sets", {}).get(csv_path.name, {})
            if meta.get("status") == "already_synced" and not args.include_already_synced:
                print(f"Skipping {csv_path.name} (status=already_synced; use 'adopt' or --include-already-synced)")
                continue
            paths.append(csv_path)
    else:
        paths = []
        for f in args.files:
            p = Path(f)
            if not p.is_absolute() and not p.exists():
                p = ANKI_DIR / f
            paths.append(p)

    if not paths:
        print("No CSV files selected to push.")
        return 0

    ok, errors = validate_csv_files(paths)
    if not ok:
        print("Validation failed; aborting push:")
        for err in errors:
            print(f"  - {err}")
        return 1

    text_field, extra_field = resolve_cloze_fields(notetype)
    if not args.dry_run:
        anki_invoke("createDeck", {"deck": deck})

    total_added = 0
    total_updated = 0
    total_adopted = 0
    total_unchanged = 0

    for path in paths:
        _, cards = parse_anki_csv(path)
        entry = manifest.setdefault("sets", {}).setdefault(
            path.name, {"status": "pending", "notes": {}}
        )
        notes_map: dict[str, int] = entry.setdefault("notes", {})

        # Preload existing tracked notes by plain sentence so hint/cloze edits update in place.
        tracked_by_sentence: dict[str, tuple[str, int]] = {}
        tracked_ids = [nid for nid in notes_map.values() if isinstance(nid, int)]
        if tracked_ids:
            id_to_mkey = {nid: mk for mk, nid in notes_map.items()}
            for info in anki_invoke("notesInfo", {"notes": tracked_ids}):
                if info and info.get("noteId"):
                    tnid = int(info["noteId"])
                    cur_txt = info["fields"].get(text_field, {}).get("value", "").strip()
                    if cur_txt:
                        tracked_by_sentence[sentence_key(cur_txt)] = (id_to_mkey[tnid], tnid)

        print(f"\nProcessing {path.name} -> deck '{deck}' ({len(cards)} cards):")
        for card in cards:
            key = card_key(card["text"])
            skey = sentence_key(card["text"])
            nid = notes_map.get(skey) or notes_map.get(key)
            if nid is None and skey in tracked_by_sentence:
                old_key, matched_nid = tracked_by_sentence[skey]
                nid = matched_nid
                if not args.dry_run:
                    notes_map.pop(old_key, None)
                    notes_map[skey] = nid
            fields = {text_field: card["text"], extra_field: card["extra"]}
            tags = card["tags"]

            if nid is None:
                existing_nid = find_existing_note_id(card["text"], text_field)
                if existing_nid is not None:
                    nid = existing_nid
                    notes_map[skey] = nid
                    total_adopted += 1
                    print(f"  [adopt]   line {card['line']} -> existing note {nid}")

            if nid is not None:
                infos = anki_invoke("notesInfo", {"notes": [nid]})
                if infos and infos[0].get("noteId"):
                    info = infos[0]
                    cur_text = info["fields"].get(text_field, {}).get("value", "").strip()
                    cur_extra = info["fields"].get(extra_field, {}).get("value", "").strip()
                    cur_tags = set(info.get("tags", []))
                    desired_tags = set(tags)

                    needs_field_update = (cur_text != card["text"]) or (cur_extra != card["extra"])
                    missing_tags = desired_tags - cur_tags

                    if not needs_field_update and not missing_tags:
                        total_unchanged += 1
                        continue

                    if args.dry_run:
                        print(f"  [update]  line {card['line']} (note {nid}) [dry-run]")
                    else:
                        if needs_field_update:
                            anki_invoke("updateNoteFields", {"note": {"id": nid, "fields": fields}})
                        if missing_tags:
                            anki_invoke(
                                "addTags",
                                {"notes": [nid], "tags": " ".join(sorted(missing_tags))},
                            )
                        print(f"  [update]  line {card['line']} (note {nid})")
                    total_updated += 1
                    continue

            if args.dry_run:
                print(f"  [add]     line {card['line']}: {card['text'][:60]} [dry-run]")
                total_added += 1
            else:
                new_id = anki_invoke(
                    "addNote",
                    {
                        "note": {
                            "deckName": deck,
                            "modelName": notetype,
                            "fields": fields,
                            "tags": tags,
                            "options": {"allowDuplicate": False},
                        }
                    },
                )
                notes_map[skey] = int(new_id)
                total_added += 1
                print(f"  [add]     line {card['line']} -> note {new_id}")

        if not args.dry_run:
            entry["status"] = "synced"

    if not args.dry_run:
        save_json(MANIFEST_PATH, manifest)
        if not args.no_sync and cfg.get("auto_sync_ankiweb", True) and (total_added or total_updated):
            print("\nTriggering AnkiWeb sync...")
            anki_invoke("sync")
            print("AnkiWeb sync complete.")

    print(
        f"\nSummary: added={total_added}, updated={total_updated}, "
        f"adopted={total_adopted}, unchanged={total_unchanged}"
    )
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    cfg = load_config()
    deck = args.deck or cfg["deck"]
    query = f'deck:"{deck}"'
    if args.tag:
        query += f" tag:{args.tag}"

    note_ids = anki_invoke("findNotes", {"query": query})
    print(f"Deck '{deck}' (query: {query}): {len(note_ids)} notes")
    if not note_ids:
        return 0

    infos = anki_invoke("notesInfo", {"notes": note_ids})
    tag_counts: dict[str, int] = {}
    for info in infos:
        for tag in info.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    print("\nTag distribution:")
    for tag, count in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {tag:20s} {count}")

    if args.struggling:
        lapse_query = f'{query} prop:lapses>={args.min_lapses}'
        card_ids = anki_invoke("findCards", {"query": lapse_query})
        print(f"\nStruggling cards (lapses >= {args.min_lapses}): {len(card_ids)}")
        if card_ids:
            card_infos = anki_invoke("cardsInfo", {"cards": card_ids[:25]})
            text_field, _ = resolve_cloze_fields(cfg["notetype"])
            for ci in sorted(card_infos, key=lambda c: -c.get("lapses", 0)):
                txt = ci.get("fields", {}).get(text_field, {}).get("value", "").strip()
                print(f"  - [lapses={ci.get('lapses', 0)}] {txt}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Dutch lesson Anki Cloze sets via AnkiConnect."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="Validate CSV files offline.")
    p_val.add_argument("files", nargs="*", help="CSV files to validate (default: all road_to_B1/anki/*.csv)")
    p_val.set_defaults(func=cmd_validate)

    p_stat = sub.add_parser("status", help="Check AnkiConnect status and local CSV manifest.")
    p_stat.set_defaults(func=cmd_status)

    p_adopt = sub.add_parser("adopt", help="Link already-imported CSV cards to Anki note IDs.")
    p_adopt.add_argument("files", nargs="+", help="CSV file(s) to adopt")
    p_adopt.set_defaults(func=cmd_adopt)

    p_push = sub.add_parser("push", help="Push/update CSV card sets into Anki via AnkiConnect.")
    p_push.add_argument("files", nargs="*", help="CSV file(s) to push")
    p_push.add_argument("--all", action="store_true", help="Push all non-already_synced CSVs in road_to_B1/anki/")
    p_push.add_argument(
        "--include-already-synced",
        action="store_true",
        help="Also check sets marked already_synced when using --all",
    )
    p_push.add_argument("--deck", help="Override target Anki deck name")
    p_push.add_argument("--dry-run", action="store_true", help="Preview changes without modifying Anki")
    p_push.add_argument("--no-sync", action="store_true", help="Skip AnkiWeb sync after push")
    p_push.set_defaults(func=cmd_push)

    p_insp = sub.add_parser("inspect", help="Inspect Anki deck tag counts and struggling cards.")
    p_insp.add_argument("--deck", help="Deck name (default from config.json)")
    p_insp.add_argument("--tag", help="Filter by tag")
    p_insp.add_argument("--struggling", action="store_true", help="Show cards with lapses")
    p_insp.add_argument("--min-lapses", type=int, default=2, help="Minimum lapses threshold (default: 2)")
    p_insp.set_defaults(func=cmd_inspect)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except AnkiConnectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
