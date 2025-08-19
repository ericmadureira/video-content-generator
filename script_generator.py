import os
import time

from channels_presets import PROMPT_JARDINAGEM

from constants import SCRIPT_FOLDER


class ScriptGenerator:
	def __init__(self, category, title, main_points_amount, formatted_title, mainpoints, client):
		self.category = category
		self.title = title
		self.main_points_amount = main_points_amount
		self.formatted_title = formatted_title
		self.mainpoints = mainpoints
		self.client = client
		self.script_folder = SCRIPT_FOLDER

	def generate_script(self):
		"""
		Generate the video script using Chat GPT-4 based on the title/idea, but only if it doesn't already exist.
		"""

		print("📜 STARTED script CREATION!")
		# Start time tracking.
		start_time = time.time()

		script_path = os.path.join(self.script_folder, f"{self.formatted_title}.txt")

		# ✅ Check if script already exists (Early return)
		if os.path.exists(script_path):
			print(f"🔍 Found existing script for: {self.formatted_title}")
			# End time tracking early
			end_time = time.time()
			total_time = end_time - start_time
			print(f"Script found in: {round(total_time, 1)} s")
			return script_path  # Return existing script PATH.

		print(f"🚀 Generating new script for: {self.formatted_title}")

		title_and_mainpoints = self.formatted_title + self.mainpoints
		final_script = ""

		format_data = {
			"main_points_amount": self.main_points_amount
		}

		script_start_instructions = {"role": "user", "content": f"Now grab the {self.main_points_amount} main points for the theme {title_and_mainpoints} and list them separated by '/'."}
		if self.category == 'gardening':
			configuration_prompt = PROMPT_JARDINAGEM
			words_per_main_point = 450

		# Define the system instructions (this is where we input the behavior described in the custom GPT)
		configuration_instructions = {
			"role": "system",
			"content": configuration_prompt
		}

		# We keep track of conversation_history because the GPT API is stateless and doesn't remember what you asked before, unlike the website model.
		conversation_history = [configuration_instructions, script_start_instructions]
		# GPT gets instructions on its role, and the first task to list main points.
		response_main_points = self.client.chat.completions.create(
			model="gpt-4o",
			messages=conversation_history,
		)
		# Holds the list of main points/arguments for the script.
		main_points = response_main_points.choices[0].message.content.strip()
		# Updates conversation history.
		conversation_history.append({"role": "assistant", "content": main_points})
		print(f"Main points: {main_points}")

		intro_prompt = f"Write an intro with 60 words for the title {title_and_mainpoints}, using instructions from the cofiguration prompt to convince the viewer to stay until the end of video. You should only write the intro and then wait for more instructions."
		conversation_history.append({"role": "user", "content": intro_prompt})
		# GPT writes intro.
		intro_response = self.client.chat.completions.create(
			model="gpt-4o",
			messages=conversation_history
		)
		intro = intro_response.choices[0].message.content.strip()
		conversation_history.append({"role": "assistant", "content": intro})
		intro_script_path = os.path.join(self.script_folder, f"{self.formatted_title}_intro.txt")
		print(f"Saving intro script to: {intro_script_path}")
		with open(intro_script_path, 'w', encoding="utf-8") as f:
			f.write(intro)

		# Adds intro to final script.
		final_script += intro + "\n\n\n\n"

		# Defines how many main points will be generated.
		counter = 1
		while counter <= self.main_points_amount:
			conversation_history.append({"role": "user", "content": f"Now write {words_per_main_point} words for main point {counter}."})
			# GPT writes main points one at a time.
			partial_response = self.client.chat.completions.create(
				model="gpt-4o",
				messages=conversation_history
			)
			current_script = partial_response.choices[0].message.content.strip()
			conversation_history.append({"role": "assistant", "content": current_script})
			current_script_path = os.path.join(self.script_folder, f"{self.formatted_title}_{counter}.txt")
			print(f"Saving MAIN POINT {counter} to: {current_script_path}")
			with open(current_script_path, 'w', encoding="utf-8") as f:
				f.write(current_script)

			final_script = final_script + current_script + "\n\n\n\n"
			counter += 1

		conversation_history.append({"role": "user", "content": "Now write the conclusion following instructions from the cofiguration prompt."})
		conclusion_response = self.client.chat.completions.create(
			model="gpt-4o",
			messages=conversation_history

		)
		conclusion_script = conclusion_response.choices[0].message.content.strip()
		conversation_history.append({"role": "assistant", "content": conclusion_script})
		conclusion_script_path = os.path.join(self.script_folder, f"{self.formatted_title}_conclusion.txt")
		print(f"Saving conclusion to: {conclusion_script_path}")
		with open(conclusion_script_path, 'w', encoding="utf-8") as f:
			f.write(conclusion_script)

		final_script = final_script + conclusion_script
		sanitized_script = final_script.replace('*', '')

		# End time tracking
		end_time = time.time()

		# Calculate the total time taken
		total_time = end_time - start_time
		print(f"Script writing time: {round(total_time, 1)} s")

		print(f"Saving final_script to a text file...")
		with open(script_path, 'w', encoding="utf-8") as f:
			f.write(sanitized_script)

		return script_path
