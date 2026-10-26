import csv
import os
import ffmpeg
from pathlib import Path

ROOT = Path(__file__).parent

ORIGINAL_FOLDER = ROOT / "../shmueloff-original"
ORIGINAL_CSV = ORIGINAL_FOLDER / "original.csv"
CLONED_FOLDER = ROOT / "../shmueloff-darkknox2"
CLONED_CSV = CLONED_FOLDER / "cloned.csv"
ALIGNMENT_CSV = CLONED_FOLDER / "alignment.csv"
ENGLISH_CSV = ROOT / "../english-darkknox2/english.csv"
TITLES_FOLDER = ROOT / "../biblemedia-titles"
TITLES_CSV = TITLES_FOLDER / "titles.csv"
ASSETS_FOLDER = ROOT / "../Assets"

FADE_DURATION = 0.5


class AudioBible:
	_instance = None

	@classmethod
	def get_instance(cls):
		if cls._instance is None:
			cls._instance = AudioBible()
		return cls._instance

	def __init__(self):
		self.title_durations = {}
		self.cloned_durations = {}
		self.english_durations = {}
		self.timings = {}
		self.alignment = {}
		self._load_timings()
		self.load_cloned_durations()
		self.load_alignment()
		with open(TITLES_CSV, 'r', encoding='utf-8') as f:
			reader = csv.DictReader(f)
			for row in reader:
				self.title_durations[row['filename']] = float(row['duration'])

	def _load_timings(self):
		with open(ORIGINAL_CSV, 'r', encoding='utf-8') as file:
			reader = csv.DictReader(file)
			for row in reader:
				book_number = int(row['book'])
				chapter_number = int(row['chapter'])
				verse_number = int(row['verse'])
				start_time = float(row['start'])
				end_time = float(row['end'])
				key = (book_number, chapter_number, verse_number)
				self.timings[key] = (start_time, end_time)

	def verse_timing(self, verse):
		key = (verse.chapter.book.number, verse.chapter.number, verse.number)
		return self.timings.get(key, (0.0, 0.0))

	def load_cloned_durations(self):
		used_durations = set()
		with open(CLONED_CSV, 'r', encoding='utf-8') as file:
			reader = csv.DictReader(file)
			for row in reader:
				book_number = int(row['book'])
				chapter_number = int(row['chapter'])
				verse_number = int(row['verse'])
				duration = float(row['duration'])
				while duration in used_durations:
					duration -= 0.000001
				used_durations.add(duration)
				key = (book_number, chapter_number, verse_number)
				self.cloned_durations[key] = duration

	def load_alignment(self):
		with open(ALIGNMENT_CSV, 'r', encoding='utf-8') as file:
			for row in csv.DictReader(file):
				key = (int(row['book']), int(row['chapter']), int(row['verse']))
				self.alignment.setdefault(key, {})[int(row['word'])] = (float(row['start']), float(row['end']))

	def verse_word_timing(self, verse):
		# {word number: (start, end)} in seconds from the start of the cloned verse audio
		return self.alignment[(verse.chapter.book.number, verse.chapter.number, verse.number)]

	def load_english_durations(self):
		used_durations = set()
		with open(ENGLISH_CSV, 'r', encoding='utf-8') as file:
			reader = csv.DictReader(file)
			for row in reader:
				book_number = int(row['book'])
				chapter_number = int(row['chapter'])
				verse_number = int(row['verse'])
				duration = float(row['duration'])
				while duration in used_durations:
					duration -= 0.000001
				used_durations.add(duration)
				key = (book_number, chapter_number, verse_number)
				self.english_durations[key] = duration

	def has_original_audio(self, verse):
		key = (verse.chapter.book.number, verse.chapter.number, verse.number)
		return key in self.timings

	def has_cloned_audio(self, verse):
		key = (verse.chapter.book.number, verse.chapter.number, verse.number)
		return key in self.cloned_durations

	def has_english_audio(self, verse):
		key = (verse.chapter.book.number, verse.chapter.number, verse.number)
		return key in self.english_durations

	def title_duration(self, filename):
		return self.title_durations.get(filename, 0.0)

	def cloned_duration(self, verse):
		key = (verse.chapter.book.number, verse.chapter.number, verse.number)
		return self.cloned_durations.get(key, 0.0)

	def english_duration(self, verse):
		key = (verse.chapter.book.number, verse.chapter.number, verse.number)
		return self.english_durations.get(key, 0.0)

	def original_mp3(self, verse):
		book, chapter, verse_num = verse.chapter.book.number, verse.chapter.number, verse.number
		return ORIGINAL_FOLDER / f"{book:02d}" / f"{chapter:03d}" / f"{verse_num:03d}.mp3"

	def cloned_mp3(self, verse):
		book, chapter, verse_num = verse.chapter.book.number, verse.chapter.number, verse.number
		return CLONED_FOLDER / f"{book:02d}" / f"{chapter:03d}" / f"{verse_num:03d}.mp3"

	def english_mp3(self, verse):
		book, chapter, verse_num = verse.chapter.book.number, verse.chapter.number, verse.number
		return ENGLISH_FOLDER / f"{book:02d}" / f"{chapter:03d}" / f"{verse_num:03d}.mp3"


class PsalmAudio:

	def __init__(self, psalm, music=False):
		self.psalm = psalm
		self.audiobible = AudioBible.get_instance()
		self.music = music

	@property
	def basename(self):
		suffix = '+' if self.music else ''
		return f'psalm{suffix}{self.psalm.number:03d}'

	@property
	def segments(self):
		segments_list = []

		title_path = TITLES_FOLDER / f'psalm{self.psalm.number:03d}.mp3'
		title_seg = ffmpeg.concat(
			ffmpeg.input('anullsrc=r=44100:cl=stereo', t=FADE_DURATION, f='lavfi').audio,
			ffmpeg.input(title_path).audio.filter('asetpts', 'PTS-STARTPTS'),
			ffmpeg.input('anullsrc=r=44100:cl=stereo', t=FADE_DURATION, f='lavfi').audio,
			v=0, a=1
		)
		segments_list.append(title_seg)

		for paragraph in self.psalm.paragraphs:
			for verse in paragraph.verses:
				mp3 = self.audiobible.cloned_mp3(verse)
				verse_seg = ffmpeg.concat(
					ffmpeg.input('anullsrc=r=44100:cl=stereo', t=FADE_DURATION, f='lavfi').audio,
					ffmpeg.input(mp3).filter('asetpts', 'PTS-STARTPTS'),
					ffmpeg.input('anullsrc=r=44100:cl=stereo', t=FADE_DURATION, f='lavfi').audio,
					v=0, a=1
				)
				segments_list.append(verse_seg)

		return segments_list

	@property
	def duration(self):
		total = 0.0
		title_dur = self.audiobible.title_duration(f'psalm{self.psalm.number:03d}.mp3')
		total += FADE_DURATION + title_dur + FADE_DURATION
		for verse in self.psalm.verses:
			dur = self.audiobible.cloned_duration(verse)
			total += FADE_DURATION + dur + FADE_DURATION
		return total

	@property
	def stream(self):
		narration = ffmpeg.concat(*self.segments, v=0, a=1).node[0]
		if not self.music:
			return narration

		music_file = ASSETS_FOLDER / f'{self.psalm.number:03d}.mp3'
		track = ffmpeg.input(music_file).audio
		title_dur = FADE_DURATION + self.audiobible.title_duration(f'psalm{self.psalm.number:03d}.mp3') + FADE_DURATION
		total_dur = self.duration
		delay_ms = int(title_dur * 1000)

		music = track.filter('adelay', f'{delay_ms}|{delay_ms}')
		music = music.filter('atrim', duration=total_dur)
		music = music.filter('volume', 0.2)
		music = music.filter('afade', type='in', start_time=0, duration=0.5)
		FOUT = 1.5
		fade_out_start = total_dur - FOUT - title_dur
		music = music.filter('afade', type='out', start_time=fade_out_start, duration=FOUT)

		return ffmpeg.filter([narration, music], 'amix', inputs=2, duration='shortest')


class ParashahAudio:

	def __init__(self, parashah):
		self.parashah = parashah
		self.audiobible = AudioBible.get_instance()

	@property
	def basename(self):
		return f'parashah{self.parashah.number:02d}'

	@property
	def segments(self):
		segments = []
		for verse in self.parashah.verses:
			segments.append(ffmpeg.concat(
				ffmpeg.input('anullsrc=r=44100:cl=stereo', t=FADE_DURATION, f='lavfi').audio,
				ffmpeg.input(self.audiobible.cloned_mp3(verse)).audio.filter('asetpts', 'PTS-STARTPTS'),
				ffmpeg.input('anullsrc=r=44100:cl=stereo', t=FADE_DURATION, f='lavfi').audio,
				v=0, a=1
			))
		return segments

	@property
	def duration(self):
		total = 0.0
		for verse in self.parashah.verses:
			dur = self.audiobible.cloned_duration(verse)
			total += FADE_DURATION + dur + FADE_DURATION
		return total

	@property
	def stream(self):
		return ffmpeg.concat(*self.segments, v=0, a=1).node[0]


class EpisodeAudio:

	def __init__(self, episode):
		self.episode = episode
		self.audiobible = AudioBible.get_instance()

	@property
	def basename(self):
		return f"parashah{self.episode.parashah.number:02d}-{self.episode.number:02d}"

	@property
	def segments(self):
		segments = []
		for verse in self.episode.verses:
			mp3 = self.audiobible.cloned_mp3(verse)
			verse_seg = ffmpeg.concat(
				ffmpeg.input('anullsrc=r=44100:cl=stereo', t=FADE_DURATION, f='lavfi').audio,
				ffmpeg.input(mp3).audio.filter('asetpts', 'PTS-STARTPTS'),
				ffmpeg.input('anullsrc=r=44100:cl=stereo', t=FADE_DURATION, f='lavfi').audio,
				v=0, a=1
			)
			segments.append(verse_seg)
		return segments

	@property
	def duration(self):
		total = 0.0
		for verse in self.episode.verses:
			dur = self.audiobible.cloned_duration(verse)
			total += FADE_DURATION + dur + FADE_DURATION
		return total

	@property
	def stream(self):
		return ffmpeg.concat(*self.segments, v=0, a=1).node[0]
