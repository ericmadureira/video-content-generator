import json
import os
import random
import sys
import unicodedata

from constants import IMAGE_SUMMARY_FILE, IMAGES_PER_TOPIC, LOCAL_IMAGE_DB, TOPIC_IMAGES_PER_SUBPART


def normalize_text(text):
	"""Removes accents and converts to lowercase."""
	text = unicodedata.normalize('NFD', text)
	return ''.join(char for char in text if unicodedata.category(char) != 'Mn').lower().strip()


class ImageSelector:
	def __init__(self, main_points, exclude_images=None, custom_intro_files=None):
		self.main_points = main_points
		self.exclude_images = set(exclude_images or [])
		self.custom_intro_files = custom_intro_files or []
		for f in self.custom_intro_files:
			self.exclude_images.add(f)

		self.image_database = self._load_image_summary()
		self.missing_topics = []
		self.intro_images = []
		self.main_topic_images = []
		self.conclusion_images = []

	def _load_image_summary(self):
		if not os.path.exists(IMAGE_SUMMARY_FILE):
			print("❌ ERROR: Image summary file not found! Run generate_image_summary.py first.")
			sys.exit(1)

		with open(IMAGE_SUMMARY_FILE, "r", encoding="utf-8") as f:
			return json.load(f)

	def pick_images(self, main_points_amount):
		print("DEBUG: Starting image selection with:")
		print("  → Topics:", self.main_points)
		print("  → Custom Intro Files:", self.custom_intro_files)
		print("  → Excluded Images:", len(self.exclude_images))
		INTRO_IMAGE_COUNT = main_points_amount

		for i, topic in enumerate(self.main_points):
			topic_key = normalize_text(topic)
			matching_images = self._get_images_for_topic(topic_key)
			print(f"🔍 Topic '{topic}' ({topic_key}) has {len(matching_images)} total matches before exclusions")

			filtered_images = [img for img in matching_images if img not in self.exclude_images]
			print(f"   → {len(filtered_images)} images after exclusion")

			if len(filtered_images) < IMAGES_PER_TOPIC:
				self.missing_topics.append(f"{topic} ({len(filtered_images)} found)")
				continue

			selected_images = random.sample(filtered_images, IMAGES_PER_TOPIC)

			# Add custom intro file or use first image
			if i < len(self.custom_intro_files):
				self.intro_images.append(self.custom_intro_files[i])
			else:
				self.intro_images.append(selected_images[0])

			# Always use TOPIC_IMAGES_PER_SUBPART middle images and 1 final as conclusion
			start_index = 1 if i >= len(self.custom_intro_files) else 0
			self.main_topic_images.extend(selected_images[start_index:start_index + TOPIC_IMAGES_PER_SUBPART])
			self.conclusion_images.append(selected_images[-1])

			print(f"✅ Topic {i+1} ({topic}) → Intro: {self.intro_images[-1]}, Main: {TOPIC_IMAGES_PER_SUBPART}, Conclusion: {selected_images[-1]}")

		# 🔴 VALIDATION
		if self.missing_topics:
			print("\n❌ ERROR: The following topics are missing images or do not have enough images:")
			for topic in self.missing_topics:
				print(f"   - {topic}")
			raise ValueError("❌ Aborting due to missing topic images.")

		expected_main_image_count = len(self.main_points) * TOPIC_IMAGES_PER_SUBPART
		if len(self.main_topic_images) != expected_main_image_count:
			raise ValueError(
				f"❌ Expected {expected_main_image_count} main topic images "
				f"({len(self.main_points)} topics × {TOPIC_IMAGES_PER_SUBPART}), but got {len(self.main_topic_images)}"
			)

		if len(self.intro_images) != len(self.main_points):
			raise ValueError(
				f"❌ Expected {len(self.main_points)} intro images (1 per topic), but got {len(self.intro_images)}"
			)

		if len(self.intro_images) < INTRO_IMAGE_COUNT:
			raise ValueError(
				f"❌ Not enough intro images selected for full intro section! "
				f"Expected {INTRO_IMAGE_COUNT}, got {len(self.intro_images)}"
			)

		print("🧠 Final selected intro images/videos:")
		for img in self.intro_images:
			print("   →", img)

		print(f"self.main_topic_images size: {len(self.main_topic_images)}")
		print(f"self.intro_images size: {len(self.intro_images)}")
		print(f"self.conclusion_images size: {len(self.conclusion_images)}")

		return self.intro_images, self.main_topic_images, self.conclusion_images


	def _get_images_for_topic(self, topic_key):
		normalized_db = {normalize_text(k): (k, v) for k, v in self.image_database.items()}

		if topic_key in normalized_db:
			original_key, images = normalized_db[topic_key]
			return [os.path.join(LOCAL_IMAGE_DB, original_key, img) for img in images]

		for stored_key, images in self.image_database.items():
			stored_variants = [normalize_text(v) for v in stored_key.split(" - ")]
			if topic_key in stored_variants:
				return [os.path.join(LOCAL_IMAGE_DB, stored_key, img) for img in images]

		return []
