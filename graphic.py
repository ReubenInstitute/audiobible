import os
import io
import ffmpeg
from PIL import Image as PILImage, ImageChops, ImageDraw, ImageFont, ImageFilter
from Scriptures.Text import Word
import Hebrew
from fontTools.ttLib import TTFont

from pathlib import Path

ROOT = Path(__file__).parent

FONTS_FOLDER = ROOT / "../Fonts"

PSALM_COVER_HEADLINE_FONT = FONTS_FOLDER / "LulavCLM-Bold.otf"
PSALM_COVER_TITLE_FONT = FONTS_FOLDER / "LulavCLM-Bold.otf"
PSALM_COVER_SUBTITLE_FONT = FONTS_FOLDER / "LulavCLM-Bold.otf"

PARASHAH_COVER_HEADLINE_FONT = FONTS_FOLDER / "LulavCLM-Bold.otf"
PARASHAH_COVER_TITLE_FONT = FONTS_FOLDER / "LulavCLM-Bold.otf"
PARASHAH_COVER_SUBTITLE_FONT = FONTS_FOLDER / "LulavCLM-Bold.otf"

PSALM_TITLE_FONT = FONTS_FOLDER / "LulavCLM-Bold.otf"
PSALM_SUBTITLE_FONT = FONTS_FOLDER / "LulavCLM-Bold.otf"
PSALM_TEXT_FONT = FONTS_FOLDER / "OpenSansHebrewCondensedRI-Regular.ttf"
PSALM_FOOTER_FONT = FONTS_FOLDER / "OpenSansHebrewCondensed-Bold.ttf"

PARASHAH_TITLE_FONT = FONTS_FOLDER / "OpenSansHebrewCondensed-Bold.ttf"
PARASHAH_SUBTITLE_FONT = FONTS_FOLDER / "OpenSansHebrewCondensed-Regular.ttf"
PARASHAH_TEXT_FONT = FONTS_FOLDER / "SuezOne-Regular.ttf"
PARASHAH_FOOTER_FONT = FONTS_FOLDER / "OpenSansHebrewCondensed-Bold.ttf"


_extreme_chars_cache = {}


def _get_extreme_chars(filename):
	font_path = Path(FONTS_FOLDER) / filename
	key = (filename, font_path.stat().st_mtime)
	if key in _extreme_chars_cache:
		return _extreme_chars_cache[key]

	pil_font = ImageFont.truetype(str(font_path), 80)

	tt = TTFont(font_path)
	cmap = tt.getBestCmap()

	def has_glyph(s):
		return all(ord(c) in cmap for c in s)

	temp_image = PILImage.new('RGB', (1000, 1000))
	canvas = ImageDraw.Draw(temp_image)

	top_extreme = ""
	min_top_y = 10000
	for letter in Hebrew.PLAIN_LETTERS:
		if not has_glyph(letter):
			continue
		for cant in Hebrew.UPPER_CANTILLATIONS:
			if not has_glyph(cant):
				continue
			test_text = letter + cant
			bbox = canvas.textbbox((500, 500), test_text, font=pil_font, direction="rtl")
			if bbox and bbox[1] < min_top_y:
				min_top_y = bbox[1]
				top_extreme = test_text

	bottom_extreme = ""
	max_bottom_y = -10000
	for letter in Hebrew.PLAIN_LETTERS:
		if not has_glyph(letter):
			continue
		for diac in Hebrew.DIACRITICS + Hebrew.HATAFS:
			if not has_glyph(diac):
				continue
			test_text = letter + diac
			bbox = canvas.textbbox((500, 500), test_text, font=pil_font, direction="rtl")
			if bbox and bbox[3] > max_bottom_y:
				max_bottom_y = bbox[3]
				bottom_extreme = test_text

	extreme_chars = top_extreme + bottom_extreme
	_extreme_chars_cache[key] = extreme_chars
	return extreme_chars


class Asset:
	def __init__(self, size):
		self.size = size

	@property
	def width(self):
		return self.size[0]

	@property
	def height(self):
		return self.size[1]

	@property
	def landscape(self):
		return self.width > self.height

	@property
	def square(self):
		return self.width == self.height


class Image(Asset):
	def __init__(self, size):
		super().__init__(size)
		self._image = PILImage.new('RGBA', size, (0, 0, 0, 0))

	# Two-layer drop shadow: a wide soft glow for separation from the video, and a tight dark core for
	# contact definition. Pure gaussian blur (no dilation, which makes square/blocky edges).
	SHADOW_OFFSET = (2, 3)
	SHADOW_LAYERS = ((7, 150), (2, 200))	# (blur radius, opacity 0-255)
	SHADOW_PAD = 3 * max(r for r, _ in SHADOW_LAYERS) + max(SHADOW_OFFSET)	# gaussian tail is ~3 sigma; keeps it uncut

	@staticmethod
	def add_shadow(image):
		"""Return a bigger RGBA image (grown by SHADOW_PAD on every side) with a soft shadow behind the given image."""
		pad = Image.SHADOW_PAD
		ox, oy = Image.SHADOW_OFFSET
		size = (image.width + pad*2, image.height + pad*2)
		alpha = PILImage.new('L', size, 0)
		alpha.paste(image.getchannel('A'), (pad + ox, pad + oy))
		composite = PILImage.new('RGBA', size, (0, 0, 0, 0))
		for radius, opacity in Image.SHADOW_LAYERS:
			mask = alpha.filter(ImageFilter.GaussianBlur(radius)).point(lambda a: a * opacity // 255)
			layer = PILImage.new('RGBA', size, (0, 0, 0, 0))
			layer.putalpha(mask)
			composite.alpha_composite(layer)
		composite.alpha_composite(image.convert('RGBA'), (pad, pad))
		return composite


	@staticmethod
	def bbox(xy, text, font_filename, font_size, direction=None):
		temp_img = PILImage.new('RGB', (1, 1))
		temp_canvas = ImageDraw.Draw(temp_img)
		font = ImageFont.truetype(os.path.join(FONTS_FOLDER, font_filename), font_size)
		extreme_chars = _get_extreme_chars(font_filename)
		if not extreme_chars:
			return temp_canvas.textbbox(xy, text, font=font, anchor=None, direction=direction)
		full_bbox = temp_canvas.textbbox(xy, text + extreme_chars, font=font, anchor=None, direction=direction)
		text_bbox = temp_canvas.textbbox(xy, text, font=font, anchor=None, direction=direction)
		return (text_bbox[0], full_bbox[1], text_bbox[2], full_bbox[3])


	def draw_text(self, xy, text, font_filename, font_size, color=None, shadow=True, anchor=None, direction=None):
		actual_color = color if color is not None else "#FFFFFF"
		font = ImageFont.truetype(os.path.join(FONTS_FOLDER, font_filename), font_size)
		extreme_chars = _get_extreme_chars(font_filename)

		# Use a temporary canvas for measurement
		temp_measure = PILImage.new('RGB', (1, 1))
		temp_canvas = ImageDraw.Draw(temp_measure)
		text_bbox = temp_canvas.textbbox((0, 0), text, font=font, anchor=None, direction=direction)
		full_bbox = temp_canvas.textbbox((0, 0), text + extreme_chars, font=font, anchor=None, direction=direction)

		# Create a temporary image for the text layer
		temp_image = PILImage.new('RGBA', (text_bbox[2] - text_bbox[0], full_bbox[3] - full_bbox[1]), (0, 0, 0, 0))
		temp_draw = ImageDraw.Draw(temp_image)

		if anchor == "mm":
			temp_draw.text((0, -full_bbox[1]), text, fill=actual_color, font=font, direction=direction)
		else:
			temp_draw.text((0, -full_bbox[1]), text, fill=actual_color, font=font, direction=direction)

		if not shadow:
			if anchor == "mm":
				self._image.paste(temp_image, (int(xy[0] - (text_bbox[2] - text_bbox[0]) / 2), int(xy[1] - (full_bbox[3] - full_bbox[1]) / 2)), temp_image)
			else:
				self._image.paste(temp_image, (int(xy[0]), int(xy[1])), temp_image)
			return

		shadowed_image = self.add_shadow(temp_image)

		if anchor == "mm":
			self._image.paste(shadowed_image, (int(xy[0] - (shadowed_image.width / 2)), int(xy[1] - (shadowed_image.height / 2))), shadowed_image)
		else:
			self._image.paste(shadowed_image, (int(xy[0] - self.SHADOW_PAD), int(xy[1] - self.SHADOW_PAD)), shadowed_image)


class Plate(Image):
	def __init__(self, size):
		super().__init__(size)

	@staticmethod
	def expand(lines, font_filename, width, height):
		font_size = 200
		best_font = ImageFont.load_default()
		while font_size > 20:
			try:
				current_font = ImageFont.truetype(os.path.join(FONTS_FOLDER, font_filename), font_size)
			except IOError:
				current_font = ImageFont.load_default()
			total_height = 0
			max_line_width = 0
			for line in lines:
				text = ''.join(word.text + word.spacer for word in line).rstrip()
				box = Image.bbox((0, 0), text, font_filename, font_size)
				total_height += (box[3] - box[1]) * 1.3
				max_line_width = max(max_line_width, box[2] - box[0])
			if total_height < height * 0.9 and max_line_width < width * 0.9:
				best_font = current_font
				break
			font_size -= 1
		return best_font

	@staticmethod
	def wrap(words, font_filename, font_size, width):
		if not words:
			return []
		font = ImageFont.truetype(os.path.join(FONTS_FOLDER, font_filename), font_size)
		space_width = Image.bbox((0, 0), ' ', font_filename, font_size)[2]
		results = []
		current_line = []
		current_width = 0
		for word in words:
			word_width = Image.bbox((0, 0), word.text + word.spacer.strip(), font_filename, font_size)[2]
			gap = 0 if current_line and current_line[-1].spacer == Hebrew.MAQAF else space_width
			if current_line and current_width + gap + word_width > width:
				results.append(current_line)
				current_line = [word]
				current_width = word_width
			else:
				if current_line:
					current_width += gap
				current_line.append(word)
				current_width += word_width
		if current_line:
			results.append(current_line)
		return results

	def draw_left_aligned(self, x, y, width, words, font_filename, font_size, color, rtl=False, verse=None):
		if rtl:
			words = list(reversed(words))
		font = ImageFont.truetype(os.path.join(FONTS_FOLDER, font_filename), font_size)
		space_width = Image.bbox((0, 0), ' ', font_filename, font_size)[2]
		current_x = x
		for word in words:
			word_width = Image.bbox((0, 0), word.text, font_filename, font_size)[2]
			self.draw_text((int(current_x), int(y)), word.text, font_filename, font_size,
						   color=("#ffff00" if verse and word.verse.number == verse else color),
						   shadow=True, direction="rtl" if rtl else "ltr")
			current_x += word_width + space_width

	def draw_right_aligned(self, x, y, width, words, font_filename, font_size, color, rtl=False, verse=None):
		if rtl:
			words = list(reversed(words))
		font = ImageFont.truetype(os.path.join(FONTS_FOLDER, font_filename), font_size)
		space_width = Image.bbox((0, 0), ' ', font_filename, font_size)[2]
		total_width = sum(Image.bbox((0, 0), word.text, font_filename, font_size)[2] for word in words)
		total_width += space_width * (len(words) - 1)
		current_x = x + width - total_width
		for word in words:
			word_width = Image.bbox((0, 0), word.text, font_filename, font_size)[2]
			self.draw_text((int(current_x), int(y)), word.text, font_filename, font_size,
						   color=("#ffff00" if verse and word.verse.number == verse else color),
						   shadow=True, direction="rtl" if rtl else "ltr")
			current_x += word_width + space_width

	def draw_justified(self, x, y, width, words, font_filename, font_size, color, rtl=False, verse=None):
		if rtl:
			words = list(reversed(words))
		if not words:
			return
		font = ImageFont.truetype(os.path.join(FONTS_FOLDER, font_filename), font_size)
		widths = [Image.bbox((0, 0), word.text + word.spacer.strip(), font_filename, font_size)[2] for word in words]
		# a word joined to the next one with a maqaf takes no gap
		gaps = [k for k in range(len(words) - 1) if (words[k + 1] if rtl else words[k]).spacer != Hebrew.MAQAF]
		spacing = (width - sum(widths)) / len(gaps) if gaps else 0
		current_x = x
		for i, word in enumerate(words):
			self.draw_text((int(current_x), int(y)), word.text + word.spacer.strip(), font_filename, font_size,
						   color=("#ffff00" if verse and word.verse.number == verse else color),
						   shadow=True, direction="rtl" if rtl else "ltr")
			current_x += widths[i] + (spacing if i in gaps else 0)

	def draw_centered(self, x, y, width, words, font_filename, font_size, color, rtl=False, verse=None, highlight=None, first=1):
		# Always position words individually (summed widths), even with no highlight: a
		# whole-string measurement doesn't agree pixel-for-pixel with the summed one, and the
		# base (no-highlight) plate must land on the exact same pixels as the highlight plates
		# it's composited under in the video, or the two show through as a doubled image.
		font = ImageFont.truetype(os.path.join(FONTS_FOLDER, font_filename), font_size)
		numbered = list(enumerate(words, first))
		if rtl:
			numbered = list(reversed(numbered))
		space_width = Image.bbox((0, 0), ' ', font_filename, font_size)[2]
		widths = [Image.bbox((0, 0), word.text + word.spacer.strip(), font_filename, font_size)[2] for _, word in numbered]
		# a word joined to the next one with a maqaf takes no space
		gaps = [0 if (numbered[k + 1][1] if rtl else word).spacer == Hebrew.MAQAF else space_width
				for k, (_, word) in enumerate(numbered[:-1])]
		current_x = x + (width - sum(widths) - sum(gaps)) // 2
		for k, (number, word) in enumerate(numbered):
			if highlight is not None:
				yellow = number == highlight
			elif verse is not None:
				yellow = word.verse and word.verse.number == verse
			else:
				yellow = False
			self.draw_text((int(current_x), int(y)), word.text + word.spacer.strip(), font_filename, font_size,
						   color="#ffff00" if yellow else color,
						   shadow=True, direction="rtl" if rtl else "ltr")
			current_x += widths[k] + (gaps[k] if k < len(gaps) else 0)


class PsalmCover(Image):
	HEADLINE_FONT   = 0.10
	TITLE_FONT	  = 0.167
	NUMBER_FONT	 = 0.361
	HEADLINE_Y	  = 0.22
	TITLE_Y		 = 0.3646
	NUMBER_Y		= 0.6354
	SAFEZONE_CENTER = 0.458

	def __init__(self, psalm, size):
		super().__init__(size)
		self.psalm = psalm

	@property
	def basename(self):
		return f'{self.psalm.number:03d}-{self.width}x{self.height}'

	@property
	def image(self):
		bg_path = ASSETS_FOLDER / "back.jpg" if self.square else Paths.ASSETS_FOLDER / f"back-{self.width}x{self.height}.jpg"
		background = PILImage.open(bg_path).convert('RGB').resize((self.width, self.height))
		color_overlay = PILImage.new('RGB', (self.width, self.height), self.psalm.color)
		background_rgba = background.convert('RGBA')
		color_overlay_rgba = color_overlay.convert('RGBA')
		background = PILImage.blend(background_rgba, color_overlay_rgba, alpha=0.7)
		background = background.filter(ImageFilter.GaussianBlur(2))

		self._image = background

		shorter_side = min(self.width, self.height)

		headline_font_size = int(shorter_side * self.HEADLINE_FONT)
		title_font_size  = int(shorter_side * self.TITLE_FONT)
		number_font_size = int(shorter_side * self.NUMBER_FONT)

		headline_text = "תהילים"
		headline_bbox = self.bbox((0, 0), headline_text, PSALM_COVER_HEADLINE_FONT, headline_font_size)
		headline_w = headline_bbox[2] - headline_bbox[0]
		headline_h = headline_bbox[3] - headline_bbox[1]

		title_text = "מזמור"
		title_bbox = self.bbox((0, 0), title_text, PSALM_COVER_TITLE_FONT, title_font_size)
		title_w = title_bbox[2] - title_bbox[0]
		title_h = title_bbox[3] - title_bbox[1]

		number_text = self.psalm.hebrew_number
		number_bbox = self.bbox((0, 0), number_text, PSALM_COVER_SUBTITLE_FONT, number_font_size)
		number_w = number_bbox[2] - number_bbox[0]
		number_h = number_bbox[3] - number_bbox[1]

		if self.width < self.height:
			block_center_y = int(self.height * self.SAFEZONE_CENTER)
		else:
			block_center_y = self.height // 2

		square_top = block_center_y - shorter_side // 2

		headline_x = (self.width - headline_w) // 2
		headline_y = square_top + int(shorter_side * self.HEADLINE_Y) - headline_h // 2

		title_x = (self.width - title_w) // 2
		title_y = square_top + int(shorter_side * self.TITLE_Y) - title_h // 2

		number_x = (self.width - number_w) // 2
		number_y = square_top + int(shorter_side * self.NUMBER_Y) - number_h // 2

		self.draw_text((headline_x, headline_y), headline_text, PSALM_COVER_HEADLINE_FONT, headline_font_size,
					   color="#ffffff", shadow=True, direction="rtl")
		self.draw_text((title_x, title_y), title_text, PSALM_COVER_TITLE_FONT, title_font_size,
					   color="#ffff00", shadow=True, direction="rtl")
		self.draw_text((number_x, number_y), number_text, PSALM_COVER_SUBTITLE_FONT, number_font_size,
					   color="#ffffff", shadow=True, direction="rtl")

		return self._image


class ParashahCover(Image):
	HEADLINE_FONT   = 0.10
	TITLE_FONT	  = 0.167
	SUBTITLE_FONT   = 0.24
	HEADLINE_Y	  = 0.22
	TITLE_Y		 = 0.3646
	SUBTITLE_Y	  = 0.6354
	SAFEZONE_CENTER = 0.458
	MARGIN		  = 0.9

	def __init__(self, parashah, size):
		super().__init__(size)
		self.parashah = parashah

	@property
	def basename(self):
		return f'{self.parashah.number:02d}-{self.width}x{self.height}'

	def fit(self, text, font, size):
		while size > 20:
			box = self.bbox((0, 0), text, font, size)
			if box[2] - box[0] <= self.width * self.MARGIN:
				break
			size -= 2
		return size

	@property
	def image(self):
		bg_path = ASSETS_FOLDER / "back.jpg" if self.square else ASSETS_FOLDER / f"back-{self.width}x{self.height}.jpg"
		background = PILImage.open(bg_path).convert('RGB').resize((self.width, self.height))
		color_overlay = PILImage.new('RGB', (self.width, self.height), self.parashah.color)
		background = PILImage.blend(background.convert('RGBA'), color_overlay.convert('RGBA'), alpha=0.7)
		self._image = background.filter(ImageFilter.GaussianBlur(2))

		shorter_side = min(self.width, self.height)

		headline_text = "תורה"
		title_text = f"ספר {self.parashah.book.hebrew_name}"
		subtitle_text = f"פרשת {self.parashah.hebrew_name}"

		subtitle_font_size = self.fit(subtitle_text, PARASHAH_COVER_SUBTITLE_FONT, int(shorter_side * self.SUBTITLE_FONT))
		title_font_size = self.fit(title_text, PARASHAH_COVER_TITLE_FONT, min(int(shorter_side * self.TITLE_FONT), int(subtitle_font_size * 0.7)))
		headline_font_size = min(int(shorter_side * self.HEADLINE_FONT), int(title_font_size * 0.8))

		if self.width < self.height:
			block_center_y = int(self.height * self.SAFEZONE_CENTER)
		else:
			block_center_y = self.height // 2
		square_top = block_center_y - shorter_side // 2

		lines = [
			(headline_text, PARASHAH_COVER_HEADLINE_FONT, headline_font_size, self.HEADLINE_Y, "#ffffff"),
			(title_text, PARASHAH_COVER_TITLE_FONT, title_font_size, self.TITLE_Y, "#ffff00"),
			(subtitle_text, PARASHAH_COVER_SUBTITLE_FONT, subtitle_font_size, self.SUBTITLE_Y, "#ffffff"),
		]
		for text, font, font_size, y, color in lines:
			box = self.bbox((0, 0), text, font, font_size)
			x = (self.width - (box[2] - box[0])) // 2
			top = square_top + int(shorter_side * y) - (box[3] - box[1]) // 2
			self.draw_text((x, top), text, font, font_size, color=color, shadow=True, direction="rtl")

		return self._image


class EpisodeCover(Image):
	def __init__(self, episode, size):
		super().__init__(size)
		self.episode = episode

	@property
	def basename(self):
		return f"torah-{self.episode.parashah.number:02d}.{self.episode.number:02d}"

	@property
	def image(self):
		video_file = os.path.join(ASSETS_FOLDER, "back.mp4")
		frame_data, _ = (ffmpeg.input(video_file, ss=0)
			.output('pipe:', vframes=1, format='image2', vcodec='png')
			.run(capture_stdout=True, quiet=True)
		)
		background = PILImage.open(io.BytesIO(frame_data)).convert('RGB')
		background = background.resize((self.width, self.height), PILImage.LANCZOS)

		color_overlay = PILImage.new('RGB', (self.width, self.height), self.episode.color)
		background_rgba = background.convert('RGBA')
		color_overlay_rgba = color_overlay.convert('RGBA')
		background = PILImage.blend(background_rgba, color_overlay_rgba, alpha=0.7)
		background = background.filter(ImageFilter.GaussianBlur(2))

		self._image = background

		self.draw_text((self.width // 2, 300), "פרשת", "OpenSansHebrewCondensed-Bold.ttf", 90,
					   color="#ffffff", anchor="mm", direction="rtl")
		self.draw_text((self.width // 2, 400), self.episode.parashah.hebrew_name,
					   "OpenSansHebrewCondensed-Bold.ttf", 90, color="#ffffff", anchor="mm", direction="rtl")
		self.draw_text((self.width // 2, 550), str(self.episode.number),
					   "OpenSansHebrewCondensed-Bold.ttf", 180, color="#ffffff", anchor="mm", direction="rtl")

		title_lines = self.episode.hebrew_title.split(' ')
		for i, line in enumerate(title_lines):
			y = 700 + i * 120
			self.draw_text((self.width // 2, y), line, "OpenSansHebrewCondensed-Bold.ttf", 100,
						   color="#ffff00", anchor="mm", direction="rtl")

		return self._image


class EpisodeOverlay(Image):
	def __init__(self, episode, size):
		super().__init__(size)
		self.episode = episode

	@property
	def basename(self):
		return f"{self.episode.parashah.number:02d}_{self.episode.number:02d}_title"

	@property
	def image(self):
		self._image = PILImage.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
		logo_size = int(self.height * 0.15)
		logo_x = int(self.width * 0.1)
		logo_y = int(self.height * 0.045)
		logo = PILImage.open(ROOT / "../Brand/logo.png").resize((logo_size, logo_size))
		logo = Image.add_shadow(logo)
		self._image.paste(logo, (logo_x - Image.SHADOW_PAD, logo_y - Image.SHADOW_PAD), logo)
		parashah = self.episode.parashah
		self.draw_text((self.width // 2, int(self.height * 0.10)), f"ספר {parashah.book.hebrew_name}",
				PARASHAH_TITLE_FONT, int(self.height * 30 / 720), color="#ffffff", anchor="mm", direction="rtl")
		self.draw_text((self.width // 2, int(self.height * 0.19)), f"פרשת {parashah.hebrew_name}",
				PARASHAH_SUBTITLE_FONT, int(self.height * 60 / 720), color="#ffffff", anchor="mm", direction="rtl")
		return self._image


class ParashahOverlay(Image):
	def __init__(self, parashah, size):
		super().__init__(size)
		self.parashah = parashah

	@property
	def basename(self):
		return f"{self.parashah.number:02d}_parashah_title"

	@property
	def image(self):
		self._image = PILImage.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
		logo_size = int(self.height * 0.15)
		logo_x = int(self.width * 0.1)
		logo_y = int(self.height * 0.045)
		logo = PILImage.open(ROOT / "../Brand/logo.png").resize((logo_size, logo_size))
		logo = Image.add_shadow(logo)
		self._image.paste(logo, (logo_x - Image.SHADOW_PAD, logo_y - Image.SHADOW_PAD), logo)
		self.draw_text((self.width // 2, int(self.height * 0.10)), f"ספר {self.parashah.book.hebrew_name}",
				PARASHAH_TITLE_FONT, int(self.height * 30 / 720), color="#ffffff", anchor="mm", direction="rtl")
		self.draw_text((self.width // 2, int(self.height * 0.19)), f"פרשת {self.parashah.hebrew_name}",
				PARASHAH_SUBTITLE_FONT, int(self.height * 60 / 720), color="#ffffff", anchor="mm", direction="rtl")
		return self._image


class PsalmOverlay(Image):
	def __init__(self, psalm, size):
		super().__init__(size)
		self.psalm = psalm

	@property
	def basename(self):
		return f"{self.psalm.number:03d}_title"

	@property
	def image(self):
		self._image = PILImage.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
		if self.landscape:
			LOGO_SIZE = 0.15
			logo_size = int(self.height * LOGO_SIZE)
			logo_x = int(self.width * 0.1)
			TITLE_Y = 0.10
			NUMBER_Y = 0.19
			TITLE_FONTSIZE = int(self.height * 30 / 720)   # previously 30
			NUMBER_FONTSIZE = int(self.height * 60 / 720)  # previously 60
		else:
			LOGO_SIZE = 0.15
			logo_size = int(self.width * LOGO_SIZE)
			logo_x = (self.width - logo_size) // 2
			TITLE_Y = 0.20
			TITLE_Y = 0.17
			NUMBER_Y = 0.24
			NUMBER_Y = 0.23
			TITLE_FONTSIZE = int(self.width * 30 / 720)	# previously 30
			NUMBER_FONTSIZE = int(self.width * 60 / 720)   # previously 60
		LOGO_Y = 0.085
		LOGO_Y = 0.045
		logo_y = int(self.height * LOGO_Y)
		logo = PILImage.open(ROOT / "../Brand/logo.png").resize((logo_size, logo_size))
		logo = Image.add_shadow(logo)
		self._image.paste(logo, (logo_x - Image.SHADOW_PAD, logo_y - Image.SHADOW_PAD), logo)
		title_y = int(self.height * TITLE_Y)
		self.draw_text((self.width // 2, title_y), "תהילים",
				PSALM_TITLE_FONT, TITLE_FONTSIZE,
				color="#ffffff", anchor="mm", direction="rtl")
		number_y = int(self.height * NUMBER_Y)
		self.draw_text((self.width // 2, number_y), f"מזמור {self.psalm.hebrew_number}",
				PSALM_SUBTITLE_FONT, NUMBER_FONTSIZE,
				color="#ffffff", anchor="mm", direction="rtl")
		return self._image


class NarrationParagraphVersePlate(Plate):
	def __init__(self, layout, verse, size):
		super().__init__(size)
		self.layout = layout
		self.verse = verse

	@property
	def footer(self):
		return ''

	@property
	def highlight(self):
		return self.verse if self.verse != 0 else None

	@property
	def image(self):
		self._image = PILImage.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
		header_height = int(self.height * 0.20)
		safe_height = int(self.height * 0.60)
		footer_height = int(self.height * 0.20)
		margin = int(self.width * 0.15)
		available_width = self.width - 2 * margin
		font_size = 50
		layout = [[Word(Hebrew.strip_cantillation(Hebrew.strip_hebrew_punctuation(Hebrew.strip_yhwh(word.text), strip_maqaf=False)), word.verse, word.spacer) for word in line] for line in self.layout]

		temp_canvas = ImageDraw.Draw(PILImage.new('RGB', (1, 1)))
		total_height = 0
		all_sublines = []
		for visual_line in layout:
			sublines = Plate.wrap(visual_line, PARASHAH_TEXT_FONT, font_size, available_width)
			for line_words in sublines:
				if line_words:
					text = ''.join(word.text + word.spacer for word in line_words).rstrip()
					box = Image.bbox((0, 0), text, PARASHAH_TEXT_FONT, font_size, direction="rtl")
					line_height = box[3] - box[1]
					total_height += line_height
					all_sublines.append((line_words, line_height))

		current_y = header_height + (safe_height - total_height) // 2
		line_index = 0
		for visual_line in layout:
			sublines = Plate.wrap(visual_line, PARASHAH_TEXT_FONT, font_size, available_width)
			for j, line_words in enumerate(sublines):
				if line_words and line_index < len(all_sublines):
					line_height = all_sublines[line_index][1]
					draw_y = current_y
					if j == len(sublines) - 1:
						self.draw_centered(margin, draw_y, available_width, line_words,
										   PARASHAH_TEXT_FONT, font_size, "#ffffff",
										   rtl=True, verse=self.highlight)
					else:
						self.draw_justified(margin, draw_y, available_width, line_words,
											PARASHAH_TEXT_FONT, font_size, "#ffffff",
											rtl=True, verse=self.highlight)
					current_y += line_height * 1.0
					line_index += 1

		if self.footer:
			self.draw_text((self.width // 2, header_height + safe_height + (footer_height - 200) // 2),
					self.footer, PARASHAH_FOOTER_FONT, 30,
					color="#ffffff", anchor="mm", direction="rtl")
		return self._image


class ParashahParagraphVersePlate(NarrationParagraphVersePlate):
	def __init__(self, parashah, paragraph, verse, size):
		layout = parashah.paragraphs[paragraph-1].layout
		super().__init__(layout, verse, size)
		self.parashah = parashah
		self.paragraph = paragraph

	@property
	def highlight(self):
		return self.parashah.verses[self.verse-1].number if self.verse != 0 else None

	@property
	def footer(self):
		if self.verse == 0:
			return ''
		verse_obj = self.parashah.verses[self.verse - 1]
		book_name = Hebrew.strip_diacritics(verse_obj.chapter.book.hebrew_name)
		chapter_num = verse_obj.chapter.hebrew_fancy_number
		verse_num = verse_obj.hebrew_fancy_number
		return f"ספר {book_name} • פרק {chapter_num} • פסוק {verse_num}"

	@property
	def basename(self):
		return f"{self.parashah.number}.{self.paragraph}.{self.verse}"


class EpisodeParagraphVersePlate(NarrationParagraphVersePlate):
	def __init__(self, episode, paragraph, verse, size):
		layout = episode.paragraphs[paragraph-1].layout
		super().__init__(layout, verse, size)
		self.episode = episode
		self.paragraph = paragraph

	@property
	def basename(self):
		return f"{self.episode.parashah.number}.{self.episode.number}.{self.paragraph}.{self.verse}"

	@property
	def highlight(self):
		return self.episode.verses[self.verse - 1].number if self.verse != 0 else None

	@property
	def footer(self):
		if self.verse == 0:
			return ''
		verse_obj = self.episode.verses[self.verse - 1]
		book_name = Hebrew.strip_diacritics(verse_obj.chapter.book.hebrew_name)
		chapter_num = verse_obj.chapter.hebrew_fancy_number
		verse_num = verse_obj.hebrew_fancy_number
		return f"ספר {book_name} • פרק {chapter_num} • פסוק {verse_num}"


class PoemVersePlate(Plate):
	def __init__(self, slide, verse_num, size, highlight=0):
		super().__init__(size)
		self.slide = slide
		self.verse_num = verse_num
		self.highlight = highlight		# number of the word in yellow, 0 for none

	@property
	def footer(self):
		return ''

	@property
	def image(self):
		self._image = PILImage.new('RGBA', (self.width, self.height), (0, 0, 0, 0))

		header_height = int(self.height * 0.20)
		safe_height = int(self.height * 0.60)
		footer_height = int(self.height * 0.20)
		margin = int(self.width * 0.10)
		available_width = self.width - 2 * margin

		font = Plate.expand(self.slide.layout, PSALM_TEXT_FONT, available_width, safe_height)

		total_height = 0
		for line in self.slide.layout:
			text = ''.join(word.text + word.spacer for word in line).rstrip()
			box = Image.bbox((0, 0), text, PSALM_TEXT_FONT, font.size)
			total_height += (box[3] - box[1])

		y = header_height + (safe_height - total_height) // 2

		first = 1
		for line in self.slide.layout:
			text = ''.join(word.text + word.spacer for word in line).rstrip()
			box = Image.bbox((0, 0), text, PSALM_TEXT_FONT, font.size)
			line_height = box[3] - box[1]
			self.draw_centered(0, y, self.width, line, PSALM_TEXT_FONT, font.size, "#ffffff", rtl=True,
					highlight=self.highlight, first=first)
			first += len(line)
			y += line_height


		if self.footer:
			print (self.footer)
			print (len(self.footer))
			self.draw_text((self.width // 2, header_height + safe_height + footer_height // 2),
					self.footer, PSALM_FOOTER_FONT, 35,
					color="#ffffff", anchor="mm", direction="rtl")
		return self._image


class PsalmVerseSlide(Asset):
	def __init__(self, psalm, paragraph, verse, size):
		super().__init__(size)
		self.psalm = psalm
		self.paragraph = paragraph
		self.verse = verse

	@property
	def layout(self):
		return self.psalm.paragraphs[self.paragraph-1].layout[self.verse-1]


class PsalmVersePlate(PoemVersePlate):
	def __init__(self, slide, size, highlight=0):
		super().__init__(slide, slide.verse, size, highlight)

	@property
	def basename(self):
		word = f".w{self.highlight}" if self.highlight else ""
		return f"{self.slide.psalm.number}.{self.slide.paragraph}.{self.slide.verse}{word}"

	@property
	def footer(self):
		return self.slide.layout[0][0].verse.hebrew_fancy_number


class PsalmVersePreview(Image):
	def __init__(self, slide, size):
		super().__init__(size)
		self.slide = slide
		still = Path.home() / "build" / f"still-{self.width}x{self.height}.png"
		still.parent.mkdir(parents=True, exist_ok=True)
		background = ffmpeg.input(str(ASSETS_FOLDER / f"back-{self.width}x{self.height}.mp4"), ss=5)
		background = background.filter('scale', self.width, self.height, force_original_aspect_ratio='increase')
		background = background.filter('crop', w=self.width, h=self.height)
		background.output(str(still), vframes=1).run(overwrite_output=True, quiet=True)
		self._background = PILImage.open(still).convert('RGB')

	@property
	def basename(self):
		return f"{self.slide.psalm.number}.{self.slide.paragraph}.{self.slide.verse}"

	@property
	def color(self):
		return self.slide.psalm.color

	@property
	def background(self):
		color = PILImage.new('RGB', self._background.size, self.color)
		return PILImage.blend(self._background, ImageChops.overlay(self._background, color), 0.7)

	@property
	def image(self):
		self._image = self.background.convert('RGBA')
		self._image.alpha_composite(PsalmOverlay(self.slide.psalm, self.size).image)
		self._image.alpha_composite(PsalmVersePlate(self.slide, self.size).image)
		return self._image


class ParashahVersePreview(Image):
	def __init__(self, parashah, paragraph, verse, size):
		super().__init__(size)
		self.parashah = parashah
		self.paragraph = paragraph
		self.verse = verse
		still = Path.home() / "build" / f"still-{self.width}x{self.height}.png"
		still.parent.mkdir(parents=True, exist_ok=True)
		background = ffmpeg.input(str(ASSETS_FOLDER / f"back-{self.width}x{self.height}.mp4"), ss=5)
		background = background.filter('scale', self.width, self.height, force_original_aspect_ratio='increase')
		background = background.filter('crop', w=self.width, h=self.height)
		background.output(str(still), vframes=1).run(overwrite_output=True, quiet=True)
		self._background = PILImage.open(still).convert('RGB')

	@property
	def basename(self):
		return f"{self.parashah.number}.{self.paragraph}.{self.verse}"

	@property
	def color(self):
		return self.parashah.color

	@property
	def background(self):
		color = PILImage.new('RGB', self._background.size, self.color)
		return PILImage.blend(self._background, ImageChops.overlay(self._background, color), 0.7)

	@property
	def image(self):
		self._image = self.background.convert('RGBA')
		self._image.alpha_composite(ParashahOverlay(self.parashah, self.size).image)
		self._image.alpha_composite(ParashahParagraphVersePlate(self.parashah, self.paragraph, self.verse, self.size).image)
		return self._image


class ParashahParagraphSlide(Asset):
	def __init__(self, parashah, paragraph, size):
		super().__init__(size)
		self.parashah = parashah
		self.paragraph = paragraph


class EpisodeParagraphSlide(Asset):
	def __init__(self, episode, paragraph, size):
		super().__init__(size)
		self.episode = episode
		self.paragraph = paragraph


class Slide(Image):
	def __init__(self, layout, size):
		super().__init__(size)
		self.layout = layout


class PsalmSlide(Slide):
	def __init__(self, layout, psalm, paragraph, slide, size):
		super().__init__(layout, size)
		self.psalm = psalm
		self.paragraph = paragraph
		self.slide = slide

	@property
	def basename(self):
		return f"{self.psalm:03d}.{self.paragraph:02d}.{self.slide:1d}"

	@property
	def image(self):
		image = PILImage.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
		self._image = image

		header_height = int(self.height * 0.20)
		safe_height = int(self.height * 0.60)
		footer_height = int(self.height * 0.20)
		margin = int(self.width * 0.10)
		available_width = self.width - 2 * margin

		font = Slide.expand(self.layout, "OpenSansHebrewRI-Regular.ttf", available_width, safe_height)

		total_height = 0
		for line in self.layout:
			text = ' '.join(word.text for word in line)
			box = Image.bbox((0, 0), text, "OpenSansHebrewRI-Regular.ttf", font.size)
			total_height += (box[3] - box[1])

		y = header_height + (safe_height - total_height) // 2
		verse_num = self.layout[0][0].verse.number

		for line in self.layout:
			text = ' '.join(word.text for word in line)
			box = Image.bbox((0, 0), text, "OpenSansHebrewRI-Regular.ttf", font.size)
			line_height = box[3] - box[1]
			self.draw_centered_slide(0, y, self.width, line, "OpenSansHebrewRI-Regular.ttf", font.size, "#ffff00", rtl=True, verse=verse_num)
			y += line_height

		if self.layout and self.layout[0] and self.layout[0][0] and self.layout[0][0].verse:
			verse_num = self.layout[0][0].verse.hebrew_number
			self.draw_text((self.width // 2, header_height + safe_height + footer_height // 2), verse_num,
						   "OpenSansHebrewCondensed-Bold.ttf", 35, color="#ffffff", anchor="mm", direction="rtl")

		return self._image


class ParashahSlide(Slide):
	def __init__(self, layout, parashah, episode, paragraph, slide):
		super().__init__(layout)
		self.parashah = parashah
		self.episode = episode
		self.paragraph = paragraph
		self.slide = slide