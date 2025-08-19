from upload_defaults import (
	DIABETES_BASE_DESCRIPTION, DIABETES_HASHTAGS, DIABETES_TAGS,
	GARDENING_BASE_DESCRIPTION, GARDENING_HASHTAGS, GARDENING_TAGS,
	HEALTH_BASE_DESCRIPTION, HEALTH_HASHTAGS, HEALTH_TAGS,
)

import re

class MetadataCreator:
	def __init__(self, ai_client, category, title_and_mainpoints):
		"""
		Initializes metadata creator with video details.
		:param category: Video category (gardening, health, diabetes, etc.).
		"""
		self.ai_client = ai_client
		self.category = category
		self.title_and_mainpoints = title_and_mainpoints

	def generate_seo_description(self):
		print(f"🔍 Generating SEO description for: {self.title_and_mainpoints}")

		conversation_history = []
		seo_description_prompt = f"""Write a YouTube video description (under 180 words) that:
		- Starts with a bold hook in the first line
		- Includes the exact title and main points: {self.title_and_mainpoints}
		- Uses SEO keywords related to blood sugar, diabetes-friendly foods, and care after 50
		- Has 2 short paragraphs, uses emojis tastefully, and ends with a CTA to subscribe
		"""

		conversation_history.append({"role": "user", "content": seo_description_prompt})
		seo_description_response = self.ai_client.chat.completions.create(
			model="gpt-4o",
			messages=conversation_history
		)
		seo_description = seo_description_response.choices[0].message.content.strip()
		return seo_description

	def generate_description(self):
		"""
		Creates an SEO-optimized YouTube video description.
		:return: Description text.
		"""
		print(f"✍🏾 Generating description for video...")
		seo_description = ""
		if self.category == "diabetes":
			base_description = DIABETES_BASE_DESCRIPTION
			description_hashtags = DIABETES_HASHTAGS
			seo_description = self.generate_seo_description()
		elif self.category == "gardening":
			base_description = GARDENING_BASE_DESCRIPTION
			description_hashtags = GARDENING_HASHTAGS
		elif self.category == "health":
			base_description = HEALTH_BASE_DESCRIPTION
			description_hashtags = HEALTH_HASHTAGS
			seo_description = self.generate_seo_description()

		description = seo_description + base_description + "\n" + description_hashtags
		return description

	def generate_tags(self):
		"""
		Creates a list of SEO-friendly tags.
		:return: List of tags.
		"""
		tags = []
		if self.category == "diabetes":
			tags = DIABETES_TAGS
		elif self.category == "gardening":
			tags = GARDENING_TAGS
		elif self.category == "health":
			tags = HEALTH_TAGS

		return tags
