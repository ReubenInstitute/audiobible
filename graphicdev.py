import os
from PIL import Image as PILImage, ImageDraw
import Hebrew
from Hebrew import Number
from AVTools import Media

from .graphic import (
	Asset, Image, Plate,
	PsalmCover, ParashahCover, EpisodeCover,
	EpisodeOverlay, ParashahOverlay, PsalmOverlay,
	NarrationParagraphVersePlate, ParashahParagraphVersePlate, EpisodeParagraphVersePlate,
	PoemVersePlate,
	PsalmVerseSlide, PsalmVersePlate, PsalmVersePreview, ParashahVersePreview,
	ParashahParagraphSlide, EpisodeParagraphSlide,
	Slide, PsalmSlide, ParashahSlide,
)


class ImageDev(Image):
	def export(self, folder):
		filename = os.path.join(folder, f"{self.basename}.png")
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		self.image.save(filename)


class PsalmCoverDev(PsalmCover, ImageDev):
	pass


class ParashahCoverDev(ParashahCover, ImageDev):
	pass


class EpisodeCoverDev(EpisodeCover, ImageDev):
	pass


class EpisodeOverlayDev(EpisodeOverlay, ImageDev):
	pass


class ParashahOverlayDev(ParashahOverlay, ImageDev):
	pass


class PsalmOverlayDev(PsalmOverlay, ImageDev):
	pass


class NarrationParagraphVersePlateDev(NarrationParagraphVersePlate, ImageDev):
	pass


class ParashahParagraphVersePlateDev(ParashahParagraphVersePlate, ImageDev):
	pass


class EpisodeParagraphVersePlateDev(EpisodeParagraphVersePlate, ImageDev):
	pass


class PsalmVersePlateDev(PsalmVersePlate, ImageDev):
	pass


class PsalmVersePreviewDev(PsalmVersePreview, ImageDev):
	pass


class ParashahVersePreviewDev(ParashahVersePreview, ImageDev):
	pass


class PsalmSlideDev(PsalmSlide, ImageDev):
	pass


class PsalmVerseSlideDev(PsalmVerseSlide):
	def export(self, folder):
		# the plain plate, then one for every word with that word in yellow
		PsalmVersePlateDev(self, self.size).export(folder)
		for number in range(1, sum(len(line) for line in self.layout) + 1):
			PsalmVersePlateDev(self, self.size, number).export(folder)


class ParashahParagraphSlideDev(ParashahParagraphSlide):
	def export(self, folder):
		paragraph = self.parashah.paragraphs[self.paragraph-1]
		all_verses = self.parashah.verses
		ParashahParagraphVersePlateDev(self.parashah, self.paragraph, verse=0, size=self.size).export(folder)
		for verse in paragraph.verses:
			ParashahParagraphVersePlateDev(self.parashah, self.paragraph, verse=all_verses.index(verse) + 1, size=self.size).export(folder)


class EpisodeParagraphSlideDev(EpisodeParagraphSlide):
	def export(self, folder):
		layout = self.episode.paragraphs[self.paragraph-1].layout
		paragraph = self.episode.paragraphs[self.paragraph-1]
		verses = [self.episode.verses.index(verse) + 1 for verse in paragraph.verses]
		base_plate = EpisodeParagraphVersePlateDev(self.episode, self.paragraph, verse=0, size=self.size)
		base_plate.export(folder)
		for v in verses:
			plate = EpisodeParagraphVersePlateDev(self.episode, self.paragraph, verse=v, size=self.size)
			plate.export(folder)


class ParashahSlideDev(ParashahSlide):
	def export(self, landscape=False):
		"""
		Export using ParashahParagraphVersePlateDev for consistency with the
		video rendering pipeline. The old implementation reimplemented rendering
		with a hardcoded TaameyFrankCLM-Medium.ttf font, causing mismatched
		output vs the plates used in video export.
		"""
		paragraph = self.parashah.paragraphs[self.paragraph - 1]
		all_verses = self.parashah.verses
		
		# Base plate (verse=0 = no highlight)
		ParashahParagraphVersePlateDev(self.parashah, self.paragraph, verse=0, size=self.size).export("build")
		
		# Highlight plates for each verse in this paragraph
		for verse in paragraph.verses:
			verse_idx = all_verses.index(verse) + 1
			ParashahParagraphVersePlateDev(self.parashah, self.paragraph, verse=verse_idx, size=self.size).export("build")