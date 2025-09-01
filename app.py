import asyncio
import contextlib
import datetime
import edge_tts
import ffmpeg
import io
import json
import os
import shutil
import tempfile
import time
import traceback

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from openai import OpenAI
from PIL import Image, ImageFilter

from constants import (
	ASSET_FOLDER, BGM_FOLDER, FONTS_FOLDER, LOCAL_IMAGE_DB, LOGO_FOLDER, PLAYLIST_FOLDER,
	SCRIPT_FOLDER, THUMBNAIL_FOLDER, VIDEO_EXTENSION, VIDEO_OUTPUT_FOLDER
)
from convert_vertical_to_horizontal import convert_all_in_folder
from convert_webp_to_jpg import convert_webp_to_jpg_in_folder
from image_selector import ImageSelector
from metadata_creator import MetadataCreator
from script_generator import ScriptGenerator
from tts_engine import TTSEngine
from utils import sanitize_filename
from video_creators.gardening_video_creator import GardeningVideoCreator
from video_creators.health_video_creator import HealthVideoCreator
from video_creators.diabetes_video_creator import DiabetesVideoCreator
from youtube_uploader import YouTubeUploader
from werkzeug.utils import secure_filename

# Read API keys from environment variables
load_dotenv()
openai_api_key = os.getenv("OPEN_AI_API_KEY")
if not openai_api_key:
	raise ValueError("❌ ERROR: Missing OpenAI API key. Check your .env file.")

# Setup application
app = Flask(__name__, template_folder=os.path.join(os.getcwd(), 'templates'))
ai_client = OpenAI(api_key=openai_api_key)

ACTIVE_CHANNELS = [
	"gardening"
]


def load_playlists():
	all_playlists = {channel: {} for channel in ACTIVE_CHANNELS}  # ✅ Default empty dict for each category

	for channel in ACTIVE_CHANNELS:
		file_path = os.path.join(PLAYLIST_FOLDER, f"{channel}_playlists.json")
		if os.path.exists(file_path):
			with open(file_path, "r", encoding="utf-8") as f:
				all_playlists[channel] = json.load(f)  # ✅ Load JSON if file exists

	return all_playlists

async def run_tts_pipeline(tts_client, formatted_title, main_points_amount, script_path):
	subparts_durations = await tts_client.get_tts_subparts(formatted_title, main_points_amount)
	audio_path, subtitles_path = await tts_client.generate_tts(script_path, formatted_title, main_points_amount)
	return subparts_durations, audio_path, subtitles_path


@app.route("/rename_images", methods=["POST"])
def rename_images():
	from rename_images import rename_images
	output = io.StringIO()
	with contextlib.redirect_stdout(output):
		rename_images()
	return output.getvalue(), 200


@app.route("/generate_image_summary", methods=["POST"])
def generate_image_summary():
	from generate_image_summary import generate_image_summary
	output = io.StringIO()
	with contextlib.redirect_stdout(output):
		generate_image_summary()
	return output.getvalue(), 200


@app.route("/update_playlists", methods=["POST"])
def update_playlists():
	from youtube_uploader import YouTubeUploader

	results = {}

	for channel in ACTIVE_CHANNELS:
		uploader = YouTubeUploader(channel)
		result = uploader.fetch_and_store_playlists()
		results[channel] = f"{len(result)} playlists updated" if result else "Failed to update"

	return results


@app.route("/bulk_image_availability_check", methods=["POST"])
def bulk_image_check():
	from bulk_image_availability_check import run_bulk_image_availability_check
	topics = request.form.get("topics", "")
	output = io.StringIO()
	with contextlib.redirect_stdout(output):
		run_bulk_image_availability_check(topics)
	return output.getvalue()


@app.route('/video-edit')
def video_edit():
	"""
	Serve video edit input form.
	"""
	playlists = load_playlists()  # Load playlists from JSON
	default_channel = "gardening"  # Set a default category for the first load
	return render_template("index.html", playlists=playlists, category=default_channel)


@app.route('/convert-vertical', methods=['POST'])
def convert_vertical_endpoint():
	folder_path = request.form.get("folder_path")
	if not folder_path or not os.path.isdir(folder_path):
		return "❌ Invalid folder path.", 400

	converted, skipped = convert_all_in_folder(folder_path)
	return f"✅ Done: {converted} vertical images converted, {skipped} skipped, folder: {folder_path}"


@app.route('/convert-webp', methods=['POST'])
def convert_webp_endpoint():
	folder_path = request.form.get("folder_path")
	if not folder_path or not os.path.isdir(folder_path):
		return "❌ Invalid folder path.", 400

	converted, skipped = convert_webp_to_jpg_in_folder(folder_path)
	return f"✅ Done: {converted} .webp images converted to .jpg, {skipped} skipped, folder: {folder_path}"


@app.route('/dashboard')
def index():
	"""
	Serve initial HTML page with the dashboard.
	"""
	playlists = load_playlists()  # Load playlists from JSON
	default_channel = "gardening"  # Set a default channel for the first load
	image_folders = sorted([f for f in os.listdir(LOCAL_IMAGE_DB) if os.path.isdir(os.path.join(LOCAL_IMAGE_DB, f))])
	return render_template("dashboard.html", playlists=playlists, category=default_channel, image_folders=image_folders)


@app.route('/generate-content', methods=['POST'])
def generate_content():
	"""
	API endpoint to automate content production: script, TTS, video, subtitles, and YouTube upload.
	"""
	# ✅ GET FORM VALUES
	process_start_time = time.time()
	title = request.form.get('title')
	category = request.form.get('category')
	custom_intro_files = request.files.getlist("custom_intro_files[]")
	custom_folder = request.form.get("custom_folder")
	mainpoints = request.form.get('mainpoints')
	schedule_date = request.form.get('schedule_date')
	playlist_ids = request.form.getlist('playlists')
	run_until = request.form.get("run_until", "video")  # Runs up to video by default.

	run_script = True  # Always run script
	run_tts = run_until in ["tts", "images", "video", "upload"]
	run_images = run_until in ["images", "video", "upload"]
	run_video = run_until in ["video", "upload"]
	run_upload = run_until == "upload"

	# Automatically counts main points separated by comma ,
	main_points_amount = len([point.strip() for point in mainpoints.split(",") if point.strip()])

	if not title:
		return jsonify({"error": "Please provide a video title or idea"}), 400
	if not main_points_amount:
		return jsonify({"error": "Please provide the amount of main points"}), 400
	if not category:
		return jsonify({"error": "Please provide a video category"}), 400
	if not mainpoints:
		return jsonify({"error": "Please provide main points"}), 400

	# ✅ SANITIZE TITLE
	formatted_title = sanitize_filename(title)
	formatted_title = title.replace(":", "_").replace("?", "_").replace("'", "_").replace("/", "_").replace("+", "_").replace("=", "_").lower()

	# ✅ DEFAULT THUMBNAIL PATH
	thumbnail_path = os.path.join(THUMBNAIL_FOLDER, f"{formatted_title}.jpg")

	# ✅ NO THUMBNAIL
	if not os.path.exists(thumbnail_path):
		# ✅ No default thumbnail found
		print(f"⚠️ WARNING: No thumbnail found for {formatted_title}. Upload will proceed without one.")

	# ✅ CUSTOM INTRO FILES
	custom_intro_paths = []
	if custom_intro_files:
		temp_intro_dir = tempfile.mkdtemp(prefix="intro_", dir=os.getcwd())  # avoids deep temp paths
		for i, file in enumerate(custom_intro_files):
			if file and file.filename:
				# Shorten filename to avoid long paths
				ext = os.path.splitext(file.filename)[-1]
				filename = f"{i}{ext}"
				save_path = os.path.join(temp_intro_dir, filename)
				file.save(save_path)
				custom_intro_paths.append(save_path)
		print("📦 Passing custom intro files to selector in this order:")
		for path in custom_intro_paths:
			print("   →", path)

	# ✅ SCHEDULED UPLOAD (Convert to ISO 8601)
	scheduled_time = None
	if schedule_date:
		try:
			scheduled_time = datetime.datetime.strptime(schedule_date, "%Y-%m-%dT%H:%M").isoformat() + "Z"
			print(f"⏳ Video scheduled for: {scheduled_time}")
		except ValueError:
			return jsonify({"error": "Invalid date format. Use YYYY-MM-DDTHH:MM"}), 400

	output_video_path = os.path.join(VIDEO_OUTPUT_FOLDER, f"{formatted_title}{VIDEO_EXTENSION}")
	# ✅ If video already exists and user only wants to upload, skip to upload step
	if os.path.exists(output_video_path):
		print(f"📼 Skipping content creation: Video already exists for: {output_video_path}")
		if run_upload:
			run_script = False
			run_tts = False
			run_images = False
			run_video = False
		else:
			return f"📼 Skipped: Video already exists at {output_video_path}. Now ready for upload."

	try:
		# ✅ Step 1: Generate the script.
		if run_script:
			print("✅ Step 1: Generate the script.")
			script_generator = ScriptGenerator(category, title, main_points_amount, formatted_title, mainpoints, ai_client)
			script_path = script_generator.generate_script()

		# ✅ Step 2: Generate narration and subtitles from script.
		if run_tts:
			print("✅ Step 2: Generate narration and subtitles from script.")
			tts_client = TTSEngine(category)
			subparts_durations, audio_path, subtitles_path = asyncio.run(run_tts_pipeline(tts_client, formatted_title, main_points_amount, script_path))
			print(f"⌚ subparts_durations: {subparts_durations}")
			print(f"🎤 audio_path: {audio_path}")
			print(f"📗 subtitles_path: {subtitles_path}")

		# ✅ Step 3: Pick images for the video.
		if run_images:
			print("✅ Step 3: Pick images for the video.")
			mainpoints_list = [point.strip() for point in mainpoints.split(",")]
			selector = ImageSelector(mainpoints_list, custom_intro_files=custom_intro_paths)
			intro_images, main_topic_images, conclusion_images = selector.pick_images(main_points_amount) # returns array of paths

		# ✅ Step 4: Generate Video with selected images.
		if run_video:
			print("✅ Step 4: Generate Video with selected images.")

			if category == 'gardening':
				video_creator = GardeningVideoCreator(
					narration_audio=audio_path,
					subtitle_file=subtitles_path,
					output_file=output_video_path,
					video_title=title,
					font_path=FONTS_FOLDER,
					intro_images=intro_images,
					main_topic_images=main_topic_images,
					conclusion_images=conclusion_images,
					subparts_durations=subparts_durations,
					logo_path=f"{LOGO_FOLDER}/cyc-logo.png",
				)
			elif category == 'health':
				video_creator = HealthVideoCreator(
					narration_audio=audio_path,
					subtitle_file=subtitles_path,
					output_file=output_video_path,
					video_title=title,
					font_path=FONTS_FOLDER,
					intro_images=intro_images,
					main_topic_images=main_topic_images,
					conclusion_images=conclusion_images,
					subparts_durations=subparts_durations,
					logo_path=f"{LOGO_FOLDER}/folha-canal.png",
				)
			elif category == 'diabetes':
				video_creator = DiabetesVideoCreator(
					narration_audio=audio_path,
					subtitle_file=subtitles_path,
					output_file=output_video_path,
					video_title=title,
					font_path=FONTS_FOLDER,
					intro_images=intro_images,
					main_topic_images=main_topic_images,
					conclusion_images=conclusion_images,
					subparts_durations=subparts_durations,
				)
			else:
				return jsonify({"error": "Invalid category"}), 400

			video_creator.create_video()

		if run_upload:
			# ✅ Step 5: Generate video metadata.
			print("✅ Step 5: Generate video metadata.")
			title_and_mainpoints = formatted_title + mainpoints
			metadata_creator = MetadataCreator(ai_client, category, title_and_mainpoints)
			description = metadata_creator.generate_description()
			tags = metadata_creator.generate_tags()

			# ✅ Step 6: Upload Video to YouTube.
			print("✅ Step 6: Upload Video to YouTube.")
			youtube_uploader = YouTubeUploader(category)
			video_id = youtube_uploader.upload_video(
				video_path=output_video_path,
				title=title,
				description=description,
				tags=tags,
				privacy_status="private",
				scheduled_time=scheduled_time,
				thumbnail_path=thumbnail_path,
				playlist_ids=playlist_ids
			)

		process_end_time = time.time()
		process_total_time = process_end_time - process_start_time
		print(f"📺 Total content generation time: {round(process_total_time, 1)} s")
		return f"✅ Video successfully created & uploaded for: {formatted_title} (Scheduled: {scheduled_time})"
	except Exception as e:
		print("❌ ERROR OCCURRED!")
		print(traceback.format_exc())  # Log full error traceback
		return jsonify({"status": "error", "message": str(e)}), 500

	# ✅ Last Step: Clear temp directory
	finally:
		if 'temp_intro_dir' in locals() and os.path.exists(temp_intro_dir):
			shutil.rmtree(temp_intro_dir, ignore_errors=True)


if __name__ == '__main__':
	# Ensure important folders exist.
	os.makedirs(SCRIPT_FOLDER, exist_ok=True)
	os.makedirs(VIDEO_OUTPUT_FOLDER, exist_ok=True)
	os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

	# Run the Flask app locally.
	app.run(port=5000, debug=True)
