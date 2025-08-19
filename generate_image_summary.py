import os
import json
from constants import IMAGE_SUMMARY_FILE, LOCAL_IMAGE_DB

def generate_image_summary():
	"""
	Scans LOCAL_IMAGE_DB and creates a summary file mapping actual folder names to image filenames.
	"""
	image_db = {}

	for topic_folder in os.listdir(LOCAL_IMAGE_DB):
		topic_path = os.path.join(LOCAL_IMAGE_DB, topic_folder)
		if os.path.isdir(topic_path):
			images = [
				img
				for img in os.listdir(topic_path)
				# if img.lower().endswith((".png", ".jpg", ".jpeg"))
				if img.endswith((".png", ".jpg", ".jpeg"))
			]

			if images:
				image_db[topic_folder.strip()] = images  # 🔁 Store real folder name

	with open(IMAGE_SUMMARY_FILE, "w", encoding="utf-8") as f:
		json.dump(image_db, f, indent=4, ensure_ascii=False)

	print(f"✅ Image summary updated! {len(image_db)} topics found.")

if __name__ == "__main__":
	generate_image_summary()
