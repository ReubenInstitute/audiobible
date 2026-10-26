import os
import ffmpeg
from pathlib import Path

from AVTools import Media

from .video import Video, EpisodeVideo, PsalmVideo, ParashahVideo
from .graphicdev import (
	EpisodeOverlayDev, ParashahOverlayDev, PsalmOverlayDev,
	PsalmVerseSlideDev, ParashahParagraphSlideDev, EpisodeParagraphSlideDev,
)

ROOT = Path(__file__).parent
ASSETS_FOLDER = ROOT / "../Assets"

class VideoDev(Video):
	def export(self, folder):
		filename = Path(folder) / f"{self.basename}.mp4"
		filename.parent.mkdir(parents=True, exist_ok=True)
		part = filename.with_suffix('.part.mp4')
		video = self.video_stream
		audio = self.audio_stream
		ffmpeg.output(
			video,
			audio,
			str(part),
			vcodec='libx264',
			preset=self.PRESET,
			crf=self.CRF,
			acodec='aac',
			audio_bitrate=self.AUDIO_BITRATE,
			pix_fmt='yuv420p',
		).run(overwrite_output=True)
		os.replace(part, filename)


class EpisodeVideoDev(EpisodeVideo):
	def export_graphics(self):
		build_folder = Path.home() / "build"
		overlay = EpisodeOverlayDev(self.episode, size=self.size)
		overlay.export(build_folder)
		for paragraph in self.episode.paragraphs:
			slide = EpisodeParagraphSlideDev(self.episode, paragraph.number, size=self.size)
			slide.export(build_folder)

#	def export_mov(self, folder):
#		filename = Path(folder) / f"{self.basename}.mov"
#		filename.parent.mkdir(parents=True, exist_ok=True)
#		ffmpeg.output(self.backgroundless_video_stream, str(filename), vcodec='prores_ks', **{'profile:v': '422'}, pix_fmt='yuv422p10le', r=self.FPS).run(overwrite_output=True)
#		#**{'profile:v': '4444'}, pix_fmt='yuva444p10le', r=self.FPS).run(overwrite_output=True)
#		return filename

	def export(self, folder):
		self.export_graphics()
		VideoDev.export(self, folder)


class PsalmVideoDev(PsalmVideo):
	def export_graphics(self):
		build_folder = Path.home() / "build"
		overlay = PsalmOverlayDev(self.psalm, size=self.size)
		overlay.export(build_folder)
		for paragraph in self.psalm.paragraphs:
			for verse in paragraph.verses:
				slide = PsalmVerseSlideDev(self.psalm, paragraph.number, verse.number, size=self.size)
				slide.export(build_folder)

	def export(self, folder):
		self.export_graphics()
		VideoDev.export(self, folder)


class ParashahVideoDev(ParashahVideo):
	def export_graphics(self):
		build_folder = Path.home() / "build"
		ParashahOverlayDev(self.parashah, size=self.size).export(build_folder)
		for number in range(1, len(self.paragraphs) + 1):
			ParashahParagraphSlideDev(self.parashah, number, size=self.size).export(build_folder)

	def clip(self, filename, paragraph, verse_index, duration, start_t, first, last, first_in_paragraph, last_in_paragraph):
		prefix = f"{self.parashah.number}.{paragraph}"
		frames = duration * self.FPS

		fog_name = "back-720x1280.mp4" if not self.landscape else "back-1280x720.mp4"
		fog_path = os.path.join(ASSETS_FOLDER, fog_name)
		fog = ffmpeg.input(fog_path, stream_loop=-1, ss=start_t % Media.get_duration(fog_path), t=duration)
		fog = fog.filter('scale', self.width, self.height, force_original_aspect_ratio='increase')
		fog = fog.filter('crop', w=self.width, h=self.height)
		r, g, b = self.parashah.color
		color_overlay = ffmpeg.input(f'color=c=#{r:02x}{g:02x}{b:02x}:s={self.width}x{self.height}', f='lavfi', t=duration)
		background = ffmpeg.filter([fog, color_overlay], 'blend', all_mode='overlay', all_opacity=0.7)

		base = self.plate(f"{prefix}.0.png", frames, fade_in=(0,) if first_in_paragraph else None, fade_out=(0,) if last_in_paragraph else None)
		highlight = self.plate(f"{prefix}.{verse_index}.png", frames, fade_in=(1,), fade_out=(1,))
		title = self.plate(f"{self.parashah.number:02d}_parashah_title.png", frames,
						   fade_in=(0,) if first else None, fade_out=(0,) if last else None)
		video = ffmpeg.overlay(background, base, format='auto', shortest=1)
		video = ffmpeg.overlay(video, highlight, format='auto', shortest=1)
		video = ffmpeg.overlay(video, title, format='auto', shortest=1)
		ffmpeg.output(video, str(filename), vcodec='libx264', preset=self.PRESET, crf=self.CRF,
					  pix_fmt='yuv420p', r=self.FPS, t=duration).run(overwrite_output=True)

	def export(self, folder):
		self.export_graphics()
		filename = Path(folder) / f"{self.basename}.mp4"
		filename.parent.mkdir(parents=True, exist_ok=True)
		clips_folder = Path.home() / "build" / "clips" / f"parashah-{self.parashah.number:02d}"
		clips_folder.mkdir(parents=True, exist_ok=True)
		verses = self.verses
		units = [(number, verse, i, len(paragraph.verses))
				 for number, paragraph in enumerate(self.paragraphs, 1)
				 for i, verse in enumerate(paragraph.verses)]
		clips = []
		start_t = 0.0
		for n, (number, verse, i, count) in enumerate(units):
			verse_duration = self.FADE_DURATION + self.audiobible.cloned_duration(verse) + self.FADE_DURATION
			clip = clips_folder / f"{n:03d}.mp4"
			self.clip(clip, number, verses.index(verse) + 1, verse_duration, start_t, n == 0, n == len(units) - 1, i == 0, i == count - 1)
			clips.append(clip)
			start_t += verse_duration
		list_file = clips_folder / "clips.txt"
		list_file.write_text(''.join(f"file '{clip.resolve()}'\n" for clip in clips))
		part = filename.with_suffix('.part.mp4')
		ffmpeg.output(
			ffmpeg.input(str(list_file), f='concat', safe=0).video,
			self.audio_stream,
			str(part),
			vcodec='copy', acodec='aac', audio_bitrate=self.AUDIO_BITRATE,
			movflags='+faststart',
		).run(overwrite_output=True)
		os.replace(part, filename)