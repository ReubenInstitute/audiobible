import os
import ffmpeg
from pathlib import Path

from .graphic import Asset
from .audio import AudioBible, PsalmAudio, ParashahAudio, EpisodeAudio

ROOT = Path(__file__).parent
ASSETS_FOLDER = ROOT / "../Assets"

class Video(Asset):
	FADE_DURATION = 0.5
	FPS = 25
	BACKGROUND_OPACITY = 0.7
	PRESET = 'veryfast'
	CRF = 23
	AUDIO_BITRATE = '192k'


class EpisodeVideo(Video):
	def __init__(self, episode, size, raw=False):
		super().__init__(size)
		self.episode = episode
		self.raw = raw
		self.audiobible = AudioBible.get_instance()

	@property
	def basename(self):
		return f'parashah{self.parashah.number:02d}'

	@property
	def duration(self):
		total = 0.0
		for paragraph in self.episode.paragraphs:
			for verse in paragraph.verses:
				total += self.FADE_DURATION + self.audiobible.cloned_duration(verse) + self.FADE_DURATION
		return total

	@property
	def audio_stream(self):
		return EpisodeAudio(self.episode).stream

	@property
	def backgroundless_video_stream(self):
		"""The episode's foreground only (verse/title plates composited, alpha, no background),
		so ffmpeg never has to hold the whole episode's filtergraph at once when this is later
		rendered to a .mov and concatenated with other episodes' — see export_mov()."""
		episode = self.episode
		verses = episode.verses
		units = [(paragraph, verse, i, len(paragraph.verses)) for paragraph in episode.paragraphs for i, verse in enumerate(paragraph.verses)]
		segments = []
		for n, (paragraph, verse, i, count) in enumerate(units):
			verse_duration = self.FADE_DURATION + self.audiobible.cloned_duration(verse) + self.FADE_DURATION
			frames = round(verse_duration * self.FPS)
			first, last = n == 0, n == len(units) - 1
			first_in_paragraph, last_in_paragraph = i == 0, i == count - 1
			verse_index = verses.index(verse) + 1
			prefix = f"{episode.parashah.number}.{episode.number}.{paragraph.number}"
			base = self.plate(f"{prefix}.0.png", frames, fade_in=(0,) if first_in_paragraph else None, fade_out=(0,) if last_in_paragraph else None)
			highlight = self.plate(f"{prefix}.{verse_index}.png", frames, fade_in=(1,), fade_out=(1,))
			title = self.plate(f"{episode.parashah.number:02d}_{episode.number:02d}_title.png", frames,
							   fade_in=(0,) if first else None, fade_out=(0,) if last else None)
			segment = ffmpeg.overlay(base, highlight, format='auto', shortest=1)
			segment = ffmpeg.overlay(segment, title, format='auto', shortest=1)
			segments.append(segment)
		return ffmpeg.concat(*segments, v=1, a=0).node[0]

	@property
	def video_stream(self):
		return ffmpeg.overlay(self.background, self.backgroundless_video_stream, format='auto', shortest=1)

	def plate(self, name, frames, fade_in=None, fade_out=None):
		image = ffmpeg.input(os.path.join(Path.home(), "build", name), loop=1, framerate=self.FPS, t=frames / self.FPS)
		image = image.filter('scale', self.width, self.height).filter('format', 'rgba')
		if fade_in:
			image = image.filter('fade', type='in', alpha=fade_in[0], duration=self.FADE_DURATION)
		if fade_out:
			image = image.filter('fade', type='out', alpha=fade_out[0], start_time=frames / self.FPS - self.FADE_DURATION, duration=self.FADE_DURATION)
		return image

	@property
	def background(self):
		duration = self.duration
		fog_name = "back-720x1280.mp4" if not self.landscape else "back-1280x720.mp4"
		fog_path = os.path.join(ASSETS_FOLDER, fog_name)
		background = ffmpeg.input(fog_path, stream_loop=-1, t=duration)
		background = background.filter('scale', self.width, self.height, force_original_aspect_ratio='increase')
		background = background.filter('crop', w=self.width, h=self.height)
		r, g, b = self.episode.parashah.color
		color_overlay = ffmpeg.input(f'color=c=#{r:02x}{g:02x}{b:02x}:s={self.width}x{self.height}', f='lavfi', t=duration)
		return ffmpeg.filter([background, color_overlay], 'blend', all_mode='overlay', all_opacity=self.BACKGROUND_OPACITY)


class PsalmVideo(Video):
	def __init__(self, psalm, size, music=False, graphics=False):
		super().__init__(size)
		self.psalm = psalm
		self.music = music
		self.graphics = graphics
		self.audiobible = AudioBible.get_instance()

	@property
	def basename(self):
		suffix = '++' if self.graphics else '+' if self.music else ''
		return f'psalm{suffix}{self.psalm.number:03d}'

	@property
	def duration(self):
		psalm_audio = PsalmAudio(self.psalm)
		return psalm_audio.duration

	@property
	def background(self):
		duration = self.duration
		if not self.graphics:
			fog_name = "back-720x1280.mp4" if not self.landscape else "back-1280x720.mp4"
			background = ffmpeg.input(os.path.join(ASSETS_FOLDER, fog_name), stream_loop=-1, t=duration)
			background = background.filter('scale', self.width, self.height, force_original_aspect_ratio='increase')
			background = background.filter('crop', w=self.width, h=self.height)
			color_hex = f"#{self.psalm.color[0]:02x}{self.psalm.color[1]:02x}{self.psalm.color[2]:02x}"
			color_overlay = ffmpeg.input(f'color=c={color_hex}:s={self.width}x{self.height}', f='lavfi', t=duration)
			background = ffmpeg.filter([background, color_overlay], 'blend', all_mode='overlay', all_opacity=self.BACKGROUND_OPACITY)
		else:
			custom_bg = os.path.join(ASSETS_FOLDER, f'{self.psalm.number:03d}.mp4')
			background = ffmpeg.input(custom_bg, stream_loop=-1, t=duration)
			background = background.filter('scale', self.width, self.height, force_original_aspect_ratio='increase')
			background = background.filter('crop', w=self.width, h=self.height)
		return background

	@property
	def overlay(self):
		duration = self.duration
		title_image_path = os.path.join(Path.home(), "build", f"{self.psalm.number:03d}_title.png")
		overlay = ffmpeg.input(title_image_path, loop=1, t=duration)
		overlay = overlay.filter('scale', self.width, self.height)
		overlay = overlay.filter('format', 'rgba')
		overlay = overlay.filter('fade', type='in', start_time=0, duration=self.FADE_DURATION)
		overlay = overlay.filter('fade', type='out', start_time=duration - self.FADE_DURATION, duration=self.FADE_DURATION)
		return overlay

	@property
	def video_stream(self):
		audiobible = self.audiobible
		duration = self.duration

		title_dur = audiobible.title_duration(f'psalm{self.psalm.number:03d}.mp3')
		title_total_duration = self.FADE_DURATION + title_dur + self.FADE_DURATION
		title_video = ffmpeg.input(f'nullsrc=s={self.width}x{self.height}:d={title_total_duration}', f='lavfi')
		title_video = title_video.filter('format', 'rgba')
		title_video = title_video.filter('geq', r='0', g='0', b='0', a='0')


		verse_videos = []
		for paragraph in self.psalm.paragraphs:
			for verse in paragraph.verses:
				if not audiobible.has_cloned_audio(verse):
					continue
				audio_duration = audiobible.cloned_duration(verse)
				if audio_duration == 0.0:
					continue
				if audio_duration < self.FADE_DURATION * 2:
					audio_duration = self.FADE_DURATION * 2
				segment_duration = self.FADE_DURATION + audio_duration + self.FADE_DURATION
				prefix = os.path.join(Path.home(), "build",
									  f"{self.psalm.number}.{paragraph.number}.{verse.number}")
				# white until a word is spoken, yellow while it is; the timings count from the start of the audio
				shown = []
				now = 0.0
				for number, (start, end) in sorted(audiobible.verse_word_timing(verse).items()):
					start += self.FADE_DURATION
					end += self.FADE_DURATION
					shown += [(f"{prefix}.png", start - now), (f"{prefix}.w{number}.png", end - start)]
					now = end
				shown.append((f"{prefix}.png", segment_duration - now))
				list_path = f"{prefix}.txt"
				with open(list_path, 'w') as f:
					for path, seconds in shown:
						f.write(f"file '{os.path.abspath(path)}'\nduration {seconds:.3f}\n")
					f.write(f"file '{os.path.abspath(shown[-1][0])}'\n")
				verse_video = ffmpeg.input(list_path, f='concat', safe=0).filter('fps', fps=self.FPS)
				verse_video = verse_video.filter('scale', self.width, self.height)
				verse_video = verse_video.filter('format', 'rgba')
				verse_video = verse_video.filter('fade', type='in', alpha=1, duration=self.FADE_DURATION)
				verse_video = verse_video.filter('fade', type='out', alpha=1,
												 start_time=segment_duration - self.FADE_DURATION,
												 duration=self.FADE_DURATION)
				verse_videos.append(verse_video)

		all_videos = [title_video] + verse_videos
		if not all_videos:
			video_concat = ffmpeg.input('anullsrc', f='lavfi', t=duration).video.filter('format', 'rgba').filter('geq', r='0', g='0', b='0', a='0')
		else:
			video_concat = ffmpeg.concat(*all_videos, v=1, a=0).node[0]

		video = self.background
		video = ffmpeg.overlay(video, video_concat, format='auto', shortest=1)
		video = ffmpeg.overlay(video, self.overlay, format='auto', shortest=1)
		return video

	@property
	def audio_stream(self):
		psalm_audio = PsalmAudio(self.psalm, music=self.music)
		return psalm_audio.stream


class ParashahVideo(Video):
	def __init__(self, parashah, size, episode_limit=None):
		"""episode_limit: if set, only render the first N episodes (still full
		quality) instead of the whole parashah — for a quick, representative
		sample export without waiting through every episode."""
		super().__init__(size)
		self.parashah = parashah
		self.episode_limit = episode_limit
		self.audiobible = AudioBible.get_instance()

	@property
	def basename(self):
		return f'parashah{self.parashah.number:02d}'

	@property
	def duration(self):
		total = 0.0
		for verse in self.verses:
			total += self.FADE_DURATION + self.audiobible.cloned_duration(verse) + self.FADE_DURATION
		return total

	@property
	def episodes(self):
		return self.parashah.episodes[:self.episode_limit] if self.episode_limit else self.parashah.episodes

	@property
	def paragraphs(self):
		return [paragraph for episode in self.episodes for paragraph in episode.paragraphs]

	@property
	def verses(self):
		return [verse for paragraph in self.paragraphs for verse in paragraph.verses]

	@property
	def audio_stream(self):
		if not self.episode_limit:
			return ParashahAudio(self.parashah).stream
		# episode_limit is set: build audio from self.verses instead of
		# ParashahAudio, which always covers the whole parashah.
		audiobible = self.audiobible
		segments = []
		for verse in self.verses:
			segments.append(ffmpeg.concat(
				ffmpeg.input('anullsrc=r=44100:cl=stereo', t=self.FADE_DURATION, f='lavfi').audio,
				ffmpeg.input(audiobible.cloned_mp3(verse)).audio.filter('asetpts', 'PTS-STARTPTS'),
				ffmpeg.input('anullsrc=r=44100:cl=stereo', t=self.FADE_DURATION, f='lavfi').audio,
				v=0, a=1
			))
		return ffmpeg.concat(*segments, v=0, a=1).node[0]

	def plate(self, name, frames, fade_in=None, fade_out=None):
		image = ffmpeg.input(os.path.join(Path.home(), "build", name), loop=1, framerate=self.FPS, t=frames / self.FPS)
		image = image.filter('scale', self.width, self.height).filter('format', 'rgba')
		if fade_in:
			image = image.filter('fade', type='in', alpha=fade_in[0], duration=self.FADE_DURATION)
		if fade_out:
			image = image.filter('fade', type='out', alpha=fade_out[0], start_time=frames / self.FPS - self.FADE_DURATION, duration=self.FADE_DURATION)
		return image

	@property
	def background(self):
		duration = self.duration
		fog_name = "back-720x1280.mp4" if not self.landscape else "back-1280x720.mp4"
		fog_path = os.path.join(ASSETS_FOLDER, fog_name)
		background = ffmpeg.input(fog_path, stream_loop=-1, t=duration)
		background = background.filter('scale', self.width, self.height, force_original_aspect_ratio='increase')
		background = background.filter('crop', w=self.width, h=self.height)
		r, g, b = self.parashah.color
		color_overlay = ffmpeg.input(f'color=c=#{r:02x}{g:02x}{b:02x}:s={self.width}x{self.height}', f='lavfi', t=duration)
		return ffmpeg.filter([background, color_overlay], 'blend', all_mode='overlay', all_opacity=self.BACKGROUND_OPACITY)









	@property
	def video_stream(self):
		"""The ENTIRE parashah graph: plates composited per verse, concatenated,
		then the animated background overlaid. Feed straight to ffmpeg.output.
		Uses exact float durations (zero rounding) so audio and video stay locked."""
		paragraphs = list(self.paragraphs)
		para_starts = []
		para_durs = []
		para_time = 0.0
		for p in paragraphs:
			pdur = sum(self.FADE_DURATION + self.audiobible.cloned_duration(v) + self.FADE_DURATION for v in p.verses)
			para_starts.append(para_time)
			para_durs.append(pdur)
			para_time += pdur
		parashah_dur = para_time

		total_verses = sum(len(p.verses) for p in paragraphs)

		# Title plate: decoded ONCE for the whole parashah, fanned out with split
		title_input = self.plate(f"{self.parashah.number:02d}_parashah_title.png", parashah_dur * self.FPS,
								 fade_in=(0,), fade_out=(0,))
		title_branches = title_input.filter_multi_output('split', total_verses)

		all_segments = []
		vi = 0
		for pn, paragraph in enumerate(paragraphs, 1):
			pdur = para_durs[pn - 1]
			pstart = para_starts[pn - 1]
			prefix = f"{self.parashah.number}.{pn}"
			# Base plate: decoded ONCE per paragraph, fanned out with split
			base_input = self.plate(f"{prefix}.0.png", pdur * self.FPS,
									fade_in=(0,), fade_out=(0,))
			base_branches = base_input.filter_multi_output('split', len(paragraph.verses))
			vtime = 0.0
			for k, verse in enumerate(paragraph.verses):
				verse_dur = self.FADE_DURATION + self.audiobible.cloned_duration(verse) + self.FADE_DURATION
				gstart = pstart + vtime

				base_slice = base_branches[k].filter('trim', start=vtime, duration=verse_dur).filter('setpts', 'PTS-STARTPTS')
				high = self.plate(f"{prefix}.{self.verses.index(verse) + 1}.png", verse_dur * self.FPS, fade_in=(1,), fade_out=(1,))
				title_slice = title_branches[vi].filter('trim', start=gstart, duration=verse_dur).filter('setpts', 'PTS-STARTPTS')

				seg = ffmpeg.overlay(base_slice, high, format='auto', shortest=1)
				seg = ffmpeg.overlay(seg, title_slice, format='auto', shortest=1)
				all_segments.append(seg)
				vtime += verse_dur
				vi += 1

		if not all_segments:
			video = ffmpeg.input('nullsrc=s={}x{}'.format(self.width, self.height), f='lavfi').filter('geq', r='0', g='0', b='0', a='0')
		else:
			video = ffmpeg.concat(*all_segments, v=1, a=0).node[0]
		return ffmpeg.overlay(self.background, video, format='auto', shortest=1)
