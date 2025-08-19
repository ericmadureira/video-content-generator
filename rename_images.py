import os
import hashlib
import json
import time
from constants import LOCAL_IMAGE_DB, LOG_FILE


def load_renamed_files():
	"""Loads the renamed file log to prevent renaming existing files."""
	if os.path.exists(LOG_FILE):
		with open(LOG_FILE, "r", encoding="utf-8") as f:
			return json.load(f)
	return {}

def save_renamed_files(log_data):
	"""Saves the updated renamed file log."""
	with open(LOG_FILE, "w", encoding="utf-8") as f:
		json.dump(log_data, f, indent=4, ensure_ascii=False)

def rename_images():
	"""
	Renames only new images in LOCAL_IMAGE_DB using shorter hashed names.
	Prevents re-renaming files by storing renamed filenames in a log file.
	"""
	print("🖼 STARTED image rename!")
	start_time = time.time()
	renamed_files = load_renamed_files()
	updated_log = renamed_files.copy()

	for topic_folder in os.listdir(LOCAL_IMAGE_DB):
		topic_path = os.path.join(LOCAL_IMAGE_DB, topic_folder)

		if os.path.isdir(topic_path):
			for img in os.listdir(topic_path):
				if img.endswith((".png", ".jpg", ".jpeg")):
					original_path = os.path.join(topic_path, img)

					# ✅ Skip renaming if the file is already in the log
					if original_path in renamed_files:
						continue

					# ✅ Generate a unique filename (10-char hash + extension)
					file_extension = os.path.splitext(img)[-1]
					short_filename = hashlib.md5(img.encode()).hexdigest()[:10] + file_extension
					new_path = os.path.join(topic_path, short_filename)

					# ✅ Ensure unique filename within the same folder
					counter = 1
					while os.path.exists(new_path):
						short_filename = hashlib.md5((img + str(counter)).encode()).hexdigest()[:10] + file_extension
						new_path = os.path.join(topic_path, short_filename)
						counter += 1

					# ✅ Rename file
					os.rename(original_path, new_path)
					# print(f"✅ Renamed: {img} → {short_filename}")

					# ✅ Update log
					updated_log[original_path] = new_path

	# ✅ Save updated log
	save_renamed_files(updated_log)
	end_time = time.time()
	total_time = end_time - start_time
	print(f"⏳ Image rename time: {round(total_time, 1)} s")

if __name__ == "__main__":
	rename_images()
