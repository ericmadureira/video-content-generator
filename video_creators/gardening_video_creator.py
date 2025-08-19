import ffmpeg
import os
import time

from constants import ASSET_FOLDER, BGM_FOLDER, TOPIC_IMAGES_PER_SUBPART
from video_creators.base_video_creator import BaseVideoCreator

PRODUCT_CTA_TIME = 10 # seconds
INTRO_CTA_TIME = 10 # seconds


class GardeningVideoCreator(BaseVideoCreator):
	def __init__(self, video_title, narration_audio, subtitle_file, output_file, intro_images, main_topic_images, conclusion_images, subparts_durations, font_path=None, logo_path=None, loop_video=None):
		super().__init__(
			narration_audio,
			subtitle_file,
			output_file,
			intro_images,
			main_topic_images,
			conclusion_images,
			subparts_durations,
			font_path,
			logo_path
		)
		self.video_title = video_title
		self.intro_images = intro_images
		self.main_topic_images = main_topic_images
		self.conclusion_images = conclusion_images
		self.subparts_durations = subparts_durations
		self.loop_video = loop_video

	def get_subtitle_style(self):
		return "FontName=Heavitas,FontSize=16,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=2"

	def select_bgm(self):
		return f"{BGM_FOLDER}/gardening_bgm.mp3"

	def create_video(self):
		print("🔄 STARTED Gardening VIDEO CREATION!")
		start_time = time.time()

		if os.path.exists(self.output_file):
			print(f"📼 Skipping: Video already exists for: {self.video_title}")
			return self.output_file

		custom_bg_path = os.path.join(ASSET_FOLDER, "garden_bg.png")
		video_stream = self.build_canvas(custom_bg_path=custom_bg_path)
		current_time = 0

		bell_sfx_list = []

		print("🎬 Overlay Intro Images")
		video_stream, current_time = self.overlay_image_sequence(
			video_stream,
			self.intro_images,
			current_time,
			self.subparts_durations[0],
			motion="sling_horizontal_lr",
			draw_box=True
		)

		print("🧑 Overlay intro avatar")
		intro_avatar_start_time = 3
		intro_avatar_end_time = 8
		intro_avatar_path = os.path.join(ASSET_FOLDER, "gardening_avatar_intro.png")
		intro_avatar_stream = ffmpeg.input(intro_avatar_path).filter('scale', 900, -1)
		video_stream = ffmpeg.overlay(
			video_stream,
			intro_avatar_stream,
			x='-300',
			y='main_h-overlay_h',
			enable=f'between(t,{intro_avatar_start_time},{intro_avatar_end_time})'
		)

		print("🔔 Prepare bell assets")
		bell_index = 0
		bell_sfx_path = os.path.join(ASSET_FOLDER, "bell_ding.mp3")
		bell_sfx_raw = ffmpeg.input(bell_sfx_path, ss=0, t=1).audio
		bell_sfx_streams = bell_sfx_raw.filter_multi_output('asplit', len(self.subparts_durations) + 3)  # intro + main points + conclusion + redundância

		print("🔔 Mix intro bell sound")
		intro_bell_stream = bell_sfx_streams[bell_index].filter("adelay", f"{intro_avatar_start_time * 1000}|{intro_avatar_start_time * 1000}").filter("volume", 0.10)
		bell_sfx_list.append(intro_bell_stream)
		bell_index += 1

		# print("💰 Overlay CTA on intro")
		# intro_cta = ffmpeg.input(f"{ASSET_FOLDER}/cta-cyc-07-08-2025-1.png")
		# video_stream = ffmpeg.overlay(
		# 	video_stream,
		# 	intro_cta,
		# 	enable=f'between(t,{current_time - INTRO_CTA_TIME},{current_time})',
		# 	x='(main_w-overlay_w)/2',  # Horizontally centralized
		# 	y='0'                      # Top of screen
		# )

		print("🧑 Prepare main avatar assets")
		main_avatar_path = os.path.join(ASSET_FOLDER, "gardening_avatar_main_point.png")
		main_avatar_scaled = ffmpeg.input(main_avatar_path).filter('scale', 900, -1)
		main_avatar_stream = main_avatar_scaled.filter_multi_output('split', 6)  # up to 6 uses

		print("🎬 Overlay Main Topic Images")
		for idx in range(len(self.subparts_durations) - 2):
			start_idx = idx * TOPIC_IMAGES_PER_SUBPART
			end_idx = start_idx + TOPIC_IMAGES_PER_SUBPART
			subpart_images = self.main_topic_images[start_idx:end_idx]

			if not subpart_images:
				print(f"⚠️ Not enough images for subpart {idx + 1}, skipping...")
				continue

			subpart_start = current_time

			print("🔔 Mix bell sound")
			main_point_bell_stream = bell_sfx_streams[bell_index].filter("adelay", f"{subpart_start * 1000}|{subpart_start * 1000}").filter("volume", 0.10)
			bell_sfx_list.append(main_point_bell_stream)
			bell_index += 1

			print(f"🎬 Overlay Images for Main Topic {idx+1}")
			video_stream, current_time = self.overlay_image_sequence(
				video_stream,
				subpart_images,
				current_time,
				self.subparts_durations[idx + 1],
				motion="bounce_vertical"
			)

			print("🧑 Overlay main point avatar")
			video_stream = ffmpeg.overlay(
				video_stream,
				main_avatar_stream[bell_index - 1],
				x='-100',
				y='main_h-overlay_h',
				enable=f'between(t,{subpart_start},{subpart_start + 3})'
			)

			if idx == 0:  # fim do ponto 1
				print("💰 Overlay CTA after subpart 2")
				subpart_2_cta = ffmpeg.input(f"{ASSET_FOLDER}/cta-cyc-07-08-2025-2.png")
				video_stream = ffmpeg.overlay(
					video_stream,
					subpart_2_cta,
					enable=f'between(t,{current_time - PRODUCT_CTA_TIME},{current_time})',
					x='(main_w-overlay_w)/2',  # Horizontally centralized
					y='0'                      # Top of screen
				)


		print("🔔 Mix conclusion bell sound")
		conclusion_bell_stream = bell_sfx_streams[bell_index].filter("adelay", f"{current_time * 1000}|{current_time * 1000}").filter("volume", 0.10)
		bell_sfx_list.append(conclusion_bell_stream)

		conclusion_start = current_time  # <== Capture before alteration

		print("🎬 Overlay Conclusion Images")
		video_stream, current_time = self.overlay_image_sequence(
			video_stream,
			self.conclusion_images,
			current_time,
			self.subparts_durations[-1],
			motion="sling_horizontal_lr",
			draw_box=True
		)

		print("💰 Overlay CTA during conclusion")
		conclusion_cta = ffmpeg.input(f"{ASSET_FOLDER}/cta-cyc-07-08-2025-3.png")
		video_stream = ffmpeg.overlay(
			video_stream,
			conclusion_cta,
			enable=f'between(t,{current_time - PRODUCT_CTA_TIME},{current_time})',
			x='(main_w-overlay_w)/2',
			y='0'
		)

		print("🎨 Overlay Logo")
		video_stream = self.overlay_logo(video_stream)

		print("💬 Apply Subtitles")
		video_stream = self.apply_subtitles(video_stream)

		print("🔊 Mix main Audio")
		main_audio = self.mix_audio()

		print("🔉 Mix bell sounds with main audio.")
		all_audio_streams = [main_audio] + bell_sfx_list
		mixed_audio = ffmpeg.filter(all_audio_streams, 'amix', inputs=len(all_audio_streams), duration='longest')
		mixed_audio = mixed_audio.filter('dynaudnorm').filter('volume', 1.3)

		print("📦 Finalizing Video Output")
		final_output = ffmpeg.output(
			video_stream, mixed_audio, self.output_file,
			vcodec="libx264", acodec="aac", strict="experimental", pix_fmt="yuv420p"
	 	)

		ffmpeg.run(final_output, overwrite_output=True)

		print(f"✅ Video created successfully: {self.output_file}")
		print(f"⏳ Video editing time: {round(time.time() - start_time, 1)} s")
		return self.output_file
