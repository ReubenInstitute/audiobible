#!/usr/bin/env python3
"""
Export psalm and parashah audio and videos.

Run with:

	PYTHONPATH=~/WORK/Scriptures:~/WORK/StyledScriptures python3 export.py [type] number... [--cache]

	export.py 8 46 75 --cache    all three psalm tiers of each psalm
	export.py psalm 117          bare tier only (mp3 + horizontal video)
	export.py psalm+ 117         + tier only (mp3 + vertical video)
	export.py psalm++ 117        ++ tier only (vertical video, no audio)
	export.py parashah 1 3       bare tier for parashot 1 and 3

Without a type all three psalm tiers are exported (numbers are then psalm
numbers). With type 'parashah', numbers are parashah numbers instead.
Files are written to the user's home folder and are overwritten, unless
--cache is given: then a file that already exists is skipped, so an
interrupted batch can be started again with the same command.
"""

import sys
from pathlib import Path

from Scriptures import Scriptures
from Scriptures import Psalms
from Scriptures import Parashot
from AVTools import Media
import BibleMedia

TYPES = ("psalm", "psalm+", "psalm++", "parashah")
PSALM_TYPES = ("psalm", "psalm+", "psalm++")


def usage(message):
	sys.exit(f"{message}\nusage: export.py [{'|'.join(TYPES)}] number... [--cache]")


def output_filename(item, method):
	"""The file the Dev class will write, used for --cache."""
	if method == "export_mp3":
		return Path.home() / f"{item.basename}.mp3"
	return Path.home() / f"{item.basename}.mp4"


def export_psalm(psalms, num, types, cache):
	psalm = psalms[num - 1]

	items = []
	if "psalm" in types:
		items.append(("Bare audio", BibleMedia.PsalmAudioDev(psalm, music=False), "export_mp3"))
		items.append(("Bare video", BibleMedia.PsalmVideoDev(psalm, size=Media.HDH), "export"))
	if "psalm+" in types:
		items.append(("+ audio", BibleMedia.PsalmAudioDev(psalm, music=True), "export_mp3"))
		items.append(("+ video", BibleMedia.PsalmVideoDev(psalm, size=Media.SDV, music=True), "export"))
	if "psalm++" in types:
		items.append(("++ video", BibleMedia.PsalmVideoDev(psalm, size=Media.SDV, music=True, graphics=True), "export"))

	for name, item, method in items:
		filename = output_filename(item, method)
		if cache and filename.exists():
			print(f"  {name} already exists, skipping")
			continue
		print(f"  Generating {name} …")
		getattr(item, method)(Path.home())


def export_parashah(parashot, num, cache):
	parashah = parashot[num - 1]

	items = [
#		("Audio", BibleMedia.ParashahAudioDev(parashah), "export_mp3"),
		("Video", BibleMedia.ParashahVideoDev(parashah, size=Media.SDH), "export"),
	]

	for name, item, method in items:
		filename = output_filename(item, method)
		if cache and filename.exists():
			print(f"  {name} already exists, skipping")
			continue
		print(f"  Generating {name} …")
		getattr(item, method)(Path.home())


def main():
	args = sys.argv[1:]
	cache = "--cache" in args
	args = [arg for arg in args if arg != "--cache"]
	types = PSALM_TYPES
	if args and not args[0].isdigit():
		type = args.pop(0)
		if type not in TYPES:
			usage(f"unknown type '{type}'")
		types = (type,)
	if not args:
		usage("no numbers")
	if not all(arg.isdigit() for arg in args):
		usage("numbers must be integers")
	numbers = list(map(int, args))

	bible = Scriptures().bible

	if types == ("parashah",):
		parashot = Parashot(bible)
		for num in numbers:
			print(f"\n── Parashah {num} ──")
			export_parashah(parashot, num, cache)
	else:
		if not all(1 <= num <= 150 for num in numbers):
			usage("psalm numbers go from 1 to 150")
		psalms = Psalms(bible)
		for num in numbers:
			print(f"\n── Psalm {num} ──")
			export_psalm(psalms, num, types, cache)

	print("\n✅ Export complete.")


if __name__ == "__main__":
	main()
