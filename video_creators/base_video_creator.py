import ffmpeg
import os
from PIL import Image

from constants import BGM_FOLDER, FONTS_FOLDER


BASE_TARGET_WIDTH = 1366
BASE_TARGET_HEIGHT = 768

class BaseVideoCreator:
	"""Base class for video creation logic. Subclasses must implement required abstract methods."""

	def __init__(self, narration_audio, subtitle_file, output_file, intro_images, main_topic_images, conclusion_images, subparts_durations, font_path=FONTS_FOLDER, logo_path=None):
		self.bgm_audio = self.select_bgm()
		self.font_path = font_path
		self.logo_path = logo_path
		self.narration_audio = narration_audio
		self.narration_duration = self.get_narration_duration()
		self.output_file = output_file
		self.subtitle_file = subtitle_file

	def create_video(self):
		raise NotImplementedError("Subclasses must implement `create_video`")

	def get_subtitle_style(self):
		raise NotImplementedError("Subclasses must implement `get_subtitle_style`")

	def select_bgm(self):
		raise NotImplementedError("Subclasses must implement `select_bgm`")

	def get_narration_duration(self):
		print("⏳ Get narration duration")
		probe = ffmpeg.probe(self.narration_audio)
		return float(probe["format"]["duration"])

	def normalize_subparts_duration(self):
		print("⏳ Normalize subparts duration")
		summed_subparts = sum(self.subparts_durations)
		scale_factor = self.narration_duration / summed_subparts
		print(f"✅ Normalized subpart durations to match narration ({self.narration_duration}s)")
		return [d * scale_factor for d in self.subparts_durations]

	def build_canvas(self, duration=None, height=1080, width=1920, custom_bg_path=None):
		print("🎨 Build base background")
		if duration is None:
			duration = self.narration_duration

		if custom_bg_path and os.path.exists(custom_bg_path):
			return (
				ffmpeg
				.input(custom_bg_path, loop=1, t=duration)
				.filter("scale", width, height)
				.filter("format", "rgba")
			)
		else:
			print("⚠️ Background image not found. Using black canvas instead.")
			return ffmpeg.input(f"color=c=black:s={width}x{height}:d={duration}", format="lavfi")

	def mix_audio(self, bgm_volume=5):
		print("🔊 Mix Audio")
		narration = ffmpeg.input(self.narration_audio)
		if self.bgm_audio:
			bgm = ffmpeg.input(self.bgm_audio, stream_loop=-1).filter("volume", (bgm_volume/100))
			return ffmpeg.filter([narration, bgm], "amix", duration="first", dropout_transition=2)
		return narration

	def overlay_image_sequence(self, video_stream, image_paths, start_time, total_duration, width=BASE_TARGET_WIDTH, height=BASE_TARGET_HEIGHT, motion="static", draw_box=False, x_offset=277, y_offset=156):
		FIXED_VIDEO_DURATION = 5
		print("🎬 overlay_image_sequence BASE")
		if not image_paths:
			raise RuntimeError("❌ No image paths provided to overlay_image_sequence!")

		num_videos = sum(1 for p in image_paths if p.lower().endswith((".mp4", ".mov", ".webm", ".avi")))
		num_images = len(image_paths) - num_videos

		video_total_duration = num_videos * FIXED_VIDEO_DURATION
		remaining_duration = total_duration - video_total_duration
		duration_per_image = remaining_duration / num_images if num_images else 0

		print(f"total_duration: {total_duration}")
		print(f"video_total_duration: {video_total_duration}")
		print(f"remaining_duration: {remaining_duration}")
		print(f"duration_per_image: {duration_per_image}")

		for img_path in image_paths:
			is_video = img_path.lower().endswith((".mp4", ".mov", ".webm", ".avi"))
			duration = FIXED_VIDEO_DURATION if is_video else duration_per_image
			if is_video:
				image_input = ffmpeg.input(img_path, ss=0, t=duration)
			else:
				image_input = ffmpeg.input(img_path, seek_timestamp=0)

			# Apply target width and height
			image_input = image_input.filter("scale", width, height)

			if draw_box:
				image_input = image_input.filter("drawbox", x=0, y=0, w=width, h=height, color="black@1", thickness=4)

			# Apply motion
			if motion == "sling_horizontal_lr":
				video_stream = ffmpeg.overlay(
					video_stream,
					image_input,
					x=f"{x_offset} - 60 * sin(PI * (t - {start_time}) / {duration})",
					y=f"{y_offset}",
					enable=f"between(t,{start_time},{start_time + duration})"
				)
			elif motion == "bounce_vertical":
				video_stream = ffmpeg.overlay(
					video_stream,
					image_input,
					x=f"{x_offset}",
					y=f"{y_offset} + 4*sin(2*PI*(t-{start_time})/1.5)",  # Smaller bounce (4px), faster (1.5s period)
					enable=f"between(t,{start_time},{start_time + duration})"
				)
			elif motion == "static":
				video_stream = ffmpeg.overlay(
					video_stream,
					image_input,
					x=f"{x_offset}",
					y=f"{y_offset}",
					enable=f"between(t,{start_time},{start_time + duration})"
				)

			start_time += duration

		return video_stream, start_time

	def overlay_logo(self, video_stream, x=10, y=10, scale=400):
		print("🎨 Overlay Logo")
		if not self.logo_path or not os.path.exists(self.logo_path):
			print(f"❌ Logo file not found: {self.logo_path}")
			return video_stream
		print(f"🖼️ Using logo: {self.logo_path}")
		logo = ffmpeg.input(self.logo_path).filter("scale", scale, -1).filter("format", "rgba")
		return ffmpeg.overlay(video_stream, logo, x=x, y=y, eof_action="repeat")

	def apply_subtitles(self, video_stream):
		print("💬 Apply Subtitles")
		return video_stream.filter(
			"subtitles", self.subtitle_file,
			fontsdir=os.path.abspath(self.font_path),
			force_style=self.get_subtitle_style()
		)

	# 🔧 Image Utilities

	@staticmethod
	def get_image_resolution(image_path):
		"""Returns (width, height) of an image or video."""
		if image_path.lower().endswith((".mp4", ".mov", ".webm", ".avi")):
			# Use ffprobe to get video resolution
			try:
				probe = ffmpeg.probe(image_path)
				video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]
				if not video_streams:
					raise ValueError("No video stream found.")
				width = int(video_streams[0]["width"])
				height = int(video_streams[0]["height"])
				return width, height
			except Exception as e:
				raise RuntimeError(f"Failed to get video resolution for {image_path}: {e}")
		else:
			# Fall back to PIL for image files
			with Image.open(image_path) as img:
				return img.width, img.height

	@staticmethod
	def is_wide_image(width, height):
		"""Returns True if image is landscape/wide."""
		return width / height >= 1.5
