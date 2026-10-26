import csv
import os
import ffmpeg
from pathlib import Path
from mutagen.id3 import ID3, TIT2, COMM, TPE1, TPUB, TYER, TLAN, TRCK, TALB, TCOP, APIC

from AVTools import Media, Services
from Hebrew import Number

from .audio import (
	AudioBible, PsalmAudio, ParashahAudio, EpisodeAudio,
	ORIGINAL_CSV, CLONED_CSV, ENGLISH_CSV,
)


class AudioBibleDev(AudioBible):

	def set_verse_timing(self, verse, start_time, end_time):
		key = (verse.chapter.book.number, verse.chapter.number, verse.number)
		self.timings[key] = (start_time, end_time)
		self.save_verse_timings()
		#export_original_mp3(book_num, chapter_num, verse_num)

	def save_verse_timings(self):
		with open(ORIGINAL_CSV, 'w', newline='', encoding='utf-8') as file:
			writer = csv.writer(file)
			writer.writerow(['book', 'chapter', 'verse', 'start', 'end'])
			for (book_num, chapter_num, verse_num), (start_time, end_time) in sorted(self.timings.items()):
				writer.writerow([book_num, chapter_num, verse_num, start_time, end_time])

	def word_align(self, verse):
		book_num = verse.chapter.book.number
		chapter_num = verse.chapter.number
		verse_num = verse.number
		cloned_mp3_path = self.cloned_mp3(verse)

		if not cloned_mp3_path.exists():
			return False

		bare_text = verse.bare_text

		word_timings = Services.word_alignment(cloned_mp3_path, bare_text)

		alignment_path = Path('csv/alignment.csv')
		alignment_path.parent.mkdir(exist_ok=True)

		rows = []
		if alignment_path.exists():
			with open(alignment_path, 'r', encoding='utf-8') as f:
				reader = csv.DictReader(f)
				rows = [row for row in reader
				if not (int(row['book']) == book_num and
						int(row['chapter']) == chapter_num and
						int(row['verse']) == verse_num)]
		for idx, (start, end, text) in enumerate(word_timings, start=1):
			rows.append({
				'book': book_num,
				'chapter': chapter_num,
				'verse': verse_num,
				'word': idx,
				'start': f"{start:.3f}",
				'end': f"{end:.3f}"
			})

		rows.sort(key=lambda r: (int(r['book']), int(r['chapter']), int(r['verse']), int(r['word'])))
		with open(alignment_path, 'w', newline='', encoding='utf-8') as f:
			writer = csv.DictWriter(f, fieldnames=['book', 'chapter', 'verse', 'word', 'start', 'end'])
			writer.writeheader()
			writer.writerows(rows)

		return True

	def save_cloned_duration(self, verse, duration):
		self._save_duration(CLONED_CSV, verse, duration, self.cloned_durations)

	def save_english_duration(self, verse, duration):
		self._save_duration(ENGLISH_CSV, verse, duration, self.english_durations)

	def _save_duration(self, csv_path, verse, duration, durations_dict):
		key = (verse.chapter.book.number, verse.chapter.number, verse.number)
		durations_dict[key] = duration
		rows = []
		if csv_path.exists():
			with open(csv_path, 'r', encoding='utf-8') as file:
				reader = csv.DictReader(file)
				rows = list(reader)
		found = False
		for row in rows:
			if (int(row['book']) == verse.chapter.book.number and
				int(row['chapter']) == verse.chapter.number and
				int(row['verse']) == verse.number):
				row['duration'] = duration
				found = True
				break
		if not found:
			rows.append({
				'book': verse.chapter.book.number,
				'chapter': verse.chapter.number,
				'verse': verse.number,
				'duration': duration
			})
		with open(csv_path, 'w', newline='', encoding='utf-8') as file:
			writer = csv.DictWriter(file, fieldnames=['book', 'chapter', 'verse', 'duration'])
			writer.writeheader()
			writer.writerows(rows)

	def generate_clone(self, verse):
		if not self.has_original_audio(verse):
			return False
		original_mp3_path = self.original_mp3(verse)
		cloned_mp3_path = self.cloned_mp3(verse)
		voice_id = "dPah2VEoifKnZT37774q"
		Services.speech_to_speech(original_mp3_path, voice_id, cloned_mp3_path)
		duration = Media.get_duration(cloned_mp3_path)
		self.save_cloned_duration(verse, duration)
		self.word_align(verse)
		return True

	def generate_english_audio(self, book, chapter, verse, english_text):
		basename = f"{book:02d}.{chapter:03d}.{verse:03d}"
		english_mp3_path = self.bible_audio.english_directory / f"{basename}.mp3"
		voice_id = "dPah2VEoifKnZT37774q"
		try:
			Services.text_to_speech(english_text, voice_id, english_mp3_path)
		except:
			return False
		duration = BibleAudio.get_audio_duration(english_mp3_path)
		self.save_english_duration(book, chapter, verse, duration)
		return True

	def export_original_mp3(self, verse):
		if not self.has_original_audio(verse):
			return
		start_time, end_time = self.verse_timing(verse)
		basename = f"{verse.chapter.book.number:03d}.{verse.chapter.number:03d}.{verse.number:03d}"
		book = verse.chapter.book.number
		wav = Path.home() / "build" / f"{book:02d}.wav"
		if not wav.exists():
			wav.parent.mkdir(parents=True, exist_ok=True)
			part = wav.with_suffix('.part.wav')
			(ffmpeg
				.input(str(Paths.SOURCE_FOLDER / f"{book:02d}.mp3"))
				.output(str(part), acodec='pcm_s16le', ac=1)
				.overwrite_output()
				.run()
			)
			os.replace(part, wav)
		out = Paths.CLONED_FOLDER / f"cloned{basename}.mp3"
		(ffmpeg
			.input(str(wav), ss=start_time, to=end_time)
			.output(str(out), format='mp3', audio_bitrate='192k')
			.overwrite_output()
			.run()
		)


class PsalmAudioDev(PsalmAudio):

	def export_mp3(self, folder):
		filename = Path(folder) / f'{self.basename}.mp3'
		filename.parent.mkdir(parents=True, exist_ok=True)
		part = filename.with_suffix('.part.mp3')
		ffmpeg.output(self.stream, str(part), acodec='mp3').overwrite_output().run()
		os.replace(part, filename)
		self._set_id3_tags(folder)

	def export_sln(self, folder):
		filename = Path(folder) / f'{self.basename}.sln'
		filename.parent.mkdir(parents=True, exist_ok=True)
		ffmpeg.output(self.stream, str(filename), acodec='pcm_s16le', ar='8000', ac=1, f='s16le').overwrite_output().run()

	def _set_id3_tags(self, folder):
		filename = Path(folder) / f'{self.basename}.mp3'
		common_tags = {
			'title': f'מזמור {Number(self.psalm.number).fancy_text}',
			'artist': 'מכון ראובן',
			'publisher': 'מכון ראובן',
			'year': 2026,
			'month': 5,
			'track_index': self.psalm.number,
			'num_tracks': 150,
			'album': 'תהילים',
			'language': 'heb',
		}

		comments = [
			'קריינות: אברהם שמואלוב (הוקלט בשנות ה‑70), שוחזרה באמצעות ElevenLabs. סדרת תהילים של מכון ראובן.',
			'קריינות: אברהם שמואלוב (הוקלט בשנות ה‑70), שוחזרה באמצעות ElevenLabs. מוזיקת רקע: Suno AI v5. סדרת תהילים של מכון ראובן.'
		]

		tags = dict(common_tags)
		tags['comments'] = comments[0] if not self.music else comments[1]
		#tags['image'] = Paths.COVERS_FOLDER / f'{self.psalm.number:03d}-1000x1000.png'

		Media.set_id3_tags(filename, tags)


class ParashahAudioDev(ParashahAudio):

	def export_mp3(self, folder):
		filename = Path(folder) / f'{self.basename}.mp3'
		filename.parent.mkdir(parents=True, exist_ok=True)
		part = filename.with_suffix('.part.mp3')
		ffmpeg.output(self.stream, str(part), acodec='mp3').overwrite_output().run()
		os.replace(part, filename)
		self._set_id3_tags(folder)

	def export_sln(self, folder):
		filename = Path(folder) / f'{self.basename}.sln'
		filename.parent.mkdir(parents=True, exist_ok=True)
		ffmpeg.output(self.stream, str(filename), acodec='pcm_s16le', ar='8000', ac=1, f='s16le').overwrite_output().run()

	def _set_id3_tags(self, folder):
		filename = Path(folder) / f'{self.basename}.mp3'
		audio = ID3()
		audio.add(TIT2(encoding=3, text=self.parashah.hebrew_name))
		audio.add(COMM(encoding=3, lang='heb', desc='', text=''))
		audio.add(TPE1(encoding=3, text='מכון ראובן'))
		audio.add(TPUB(encoding=3, text='מכון ראובן'))
		audio.add(TYER(encoding=3, text='2025'))
		audio.add(TLAN(encoding=3, text='heb'))
		audio.add(TRCK(encoding=3, text=f'{self.parashah.number:02d}/54'))
		audio.add(TALB(encoding=3, text='פרשת השבוע'))
		audio.add(TCOP(encoding=3, text=''))
		cover_path = Paths.COVERS_FOLDER / f'{self.parashah.number:02d}-1000x1000.png'
		with open(cover_path, 'rb') as f:
			audio.add(APIC(encoding=0, mime='image/png', type=3, desc='Cover', data=f.read()))
		audio.save(filename, v2_version=3)


class EpisodeAudioDev(EpisodeAudio):

	def export_mp3(self, folder):
		filename = Path(folder) / f'{self.basename}.mp3'
		filename.parent.mkdir(parents=True, exist_ok=True)
		ffmpeg.output(self.stream, filename=str(filename), acodec='mp3').overwrite_output().run()
		self._set_id3_tags(folder)

	def export_sln(self, folder):
		filename = Path(folder) / f'{self.basename}.sln'
		filename.parent.mkdir(parents=True, exist_ok=True)
		ffmpeg.output(self.stream, str(filename), acodec='pcm_s16le', ar='8000', ac=1, f='s16le').overwrite_output().run()

	def _set_id3_tags(self, folder):
		filename = Path(folder) / f'{self.basename}.mp3'
		audio = ID3()
		audio.add(TIT2(encoding=3, text=self.basename))
		audio.save(filename, v2_version=3)
