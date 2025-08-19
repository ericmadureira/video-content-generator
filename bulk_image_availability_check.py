from colorama import init, Fore, Style
import json
import os
import sys

from constants import IMAGE_SUMMARY_FILE, LOCAL_IMAGE_DB
from generate_image_summary import generate_image_summary
from utils import normalize_text

# Minimum required images per topic
MIN_IMAGES = 17

init() #colorama

def load_image_summary():
	"""Loads the pre-generated image summary JSON."""
	generate_image_summary()

	if not os.path.exists(IMAGE_SUMMARY_FILE):
		print("❌ ERROR: Image summary file not found! Run generate_image_summary.py first.")
		sys.exit(1)

	with open(IMAGE_SUMMARY_FILE, "r", encoding="utf-8") as f:
		return json.load(f)

def get_images_for_topic(topic, image_database):
	"""Retrieves images for a topic using normalized keys, supporting multilingual variants."""
	topic_key = normalize_text(topic)

	for stored_key, images in image_database.items():
		# Split folder name like "manzana - apple - maçã" into variants and normalize all
		normalized_variants = [normalize_text(v) for v in stored_key.split(" - ")]

		if topic_key in normalized_variants:
			return images

	return []

def check_images_for_topics(topic_list, image_database):
	"""Checks which topics have fewer images than the minimum."""
	missing_topics = {}
	for topic in topic_list:
		matching_images = get_images_for_topic(topic, image_database)
		image_count = len(matching_images)
		if image_count < MIN_IMAGES:
			missing_topics[topic] = {
				"image_count": image_count,
				"status": "❌ Needs More Images"
			}
	return missing_topics

def run_bulk_image_availability_check(raw_input):
	"""Main function for UI or CLI to run image availability check."""
	topics = [topic.strip() for line in raw_input.split("\n") for topic in line.split(",") if topic.strip()]
	image_database = load_image_summary()
	missing_images = check_images_for_topics(topics, image_database)

	total_topics = len(topics)
	missing_count = len(missing_images)
	missing_percent = (missing_count / total_topics) * 100 if total_topics else 0

	if missing_images:
		report_path = "missing_image_topics.json"
		with open(report_path, "w", encoding="utf-8") as f:
			json.dump(missing_images, f, indent=4, ensure_ascii=False)

		print("\n🚨 Topics Missing Enough Images:")
		for topic in sorted(missing_images):
			data = missing_images[topic]
			print(f"   - {topic}: {data['image_count']} images found (Needs {MIN_IMAGES})")

		# Red console output (ANSI escape codes)
		print(f"\n{Fore.RED}🔴 {missing_count} of {total_topics} topics are missing images ({missing_percent:.1f}%) {Style.RESET_ALL}")
		print(f"\n📜 Report saved as: {report_path}")
	else:
		print("\n✅ All topics have sufficient images!")

# For CLI usage
if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("\n❌ ERROR: No topics provided. Please copy-paste your topics separated by commas or line breaks.\n")
		print("Example usage:")
		print('  python bulk_image_availability_check.py "Tomate, Pepino, Chayote, Cebolla, Amaranto, Espiñaca"')
		sys.exit(1)

	raw_input = " ".join(sys.argv[1:])
	run_bulk_image_availability_check(raw_input)
