#!/usr/bin/env python3
"""Rebuild cloned.csv from real MP3 durations."""
import csv, ffmpeg
from pathlib import Path
import Paths

def rebuild():
    folder = Paths.CLONED_FOLDER
    mp3_files = sorted(folder.rglob("*.mp3"))
    print(f"Found {len(mp3_files)} cloned mp3 files under {folder}")

    csv_path = folder / "cloned.csv"

    rows = []
    for mp3_file in mp3_files:
        print (mp3_file)
        try:
            rel = mp3_file.relative_to(folder)
            parts = rel.parts
            if len(parts) < 3:
                print(f"Warning: unexpected depth: {rel}")
                continue
            book_str = parts[0]      # e.g. "01"
            chapter_str = parts[1]  # e.g. "001"
            verse_file = parts[2]   # e.g. "001.mp3"
            verse_str = Path(verse_file).stem  # e.g. "001"
            
            book_num = int(book_str)
            chapter_num = int(chapter_str)
            verse_num = int(verse_str)
        except (ValueError, IndexError) as e:
            print(f"Warning: {mp3_file} ({e})")
            continue
        duration = float(ffmpeg.probe(str(mp3_file))['format']['duration'])
        rows.append({'book': book_num, 'chapter': chapter_num, 'verse': verse_num, 'duration': duration})

    rows.sort(key=lambda r: (r['book'], r['chapter'], r['verse']))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['book', 'chapter', 'verse', 'duration'])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Rebuilt {csv_path} with {len(rows)} entries")

if __name__ == "__main__":
    rebuild()