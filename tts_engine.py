import aiohttp
import asyncio
import edge_tts
import ffmpeg
import os
import subprocess
import sys
import time

from constants import ASSET_FOLDER, AUDIO_EXTENSION, SCRIPT_EXTENSION, SCRIPT_FOLDER, SUBTITLE_EXTENSION
from edge_tts import SubMaker

def split_text_by_bytes(text, max_bytes=5000):
	parts = []
	current_part = ''
	for char in text:
		if len((current_part + char).encode('utf-8')) > max_bytes:
			parts.append(current_part)
			current_part = char
		else:
			current_part += char
	if current_part:
		parts.append(current_part)
	return parts

def _srt_time_to_seconds(srt_time):
	h, m, s_ms = srt_time.split(":")
	s, ms = s_ms.split(",")
	return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def _seconds_to_srt_time(seconds):
	h = int(seconds // 3600)
	m = int((seconds % 3600) // 60)
	s = int(seconds % 60)
	ms = int((seconds - int(seconds)) * 1000)
	return f"{h:02}:{m:02}:{s:02},{ms:03}"


class TTSEngine:
	def __init__(self, category):
		self.category = category
		self.engine, self.voice = self._select_engine_and_voice(category)
		self.script_folder = SCRIPT_FOLDER
		os.makedirs(self.script_folder, exist_ok=True)

	def _select_engine_and_voice(self, category):
		mapping = {
			'gardening': ("edge", 'es-MX-JorgeNeural'),
			'health': ("edge", 'en-US-EmmaNeural'),
			# 'health': ("google", 'Gacrux'),
			# 'health': ("openvoice", 'ttsopenai-enus-mia.pth'),
			'diabetes': ("edge", 'en-US-SteffanNeural'),
			# 'diabetes': ("edge", 'en-US-RogerNeural'),
			'finance': ("edge", 'en-US-GuyNeural')
		}

		# Default fallback
		engine, voice = mapping.get(category, ("edge", 'en-US-GuyNeural'))

		# Add logic to confirm the embedding exists if using openvoice
		if engine == "openvoice":
			embedding_path = os.path.abspath(os.path.join(ASSET_FOLDER, OPEN_VOICE_EMBEDDINGS_FOLDER, voice))
			print(f"🔍 Checking if embedding exists at: {embedding_path}")
			if not os.path.isfile(embedding_path):
				raise FileNotFoundError(f"❌ Required OpenVoice embedding not found: {embedding_path}")
		return engine, voice

	async def get_tts_subparts(self, formatted_title, main_points_amount):
		print("⏱ STARTED calculating subparts durations!")
		durations_file_path = f"{self.script_folder}/{formatted_title}_durations{SCRIPT_EXTENSION}"
		subparts_durations = []

		if os.path.exists(durations_file_path):
			print(f"🔍 Found existing durations file for: {formatted_title}")
			with open(durations_file_path, 'r', encoding="utf-8") as f:
				subparts_durations = [float(d) for d in f.read().strip().split(",")]
			return subparts_durations

		subparts_paths = ["_intro"] + [f"_{i}" for i in range(1, main_points_amount + 1)] + ["_conclusion"]

		for sub in subparts_paths:
			subpart_script_path = os.path.join(self.script_folder, formatted_title + sub + SCRIPT_EXTENSION)
			subpart_audio_path = subpart_script_path.replace(SCRIPT_EXTENSION, ".mp3")
			subpart_audio_wav_path = subpart_script_path.replace(SCRIPT_EXTENSION, ".wav")

			if os.path.exists(subpart_audio_path) or os.path.exists(subpart_audio_wav_path):
				if os.path.exists(subpart_audio_path):
					existing_audio_path = subpart_audio_path
				elif os.path.exists(subpart_audio_wav_path):
					existing_audio_path = subpart_audio_wav_path
				else:
					raise FileNotFoundError("No existing subpart audio found for probe.")

				print(f"🔍 Found existing subpart audio {sub}")
				probe = ffmpeg.probe(existing_audio_path)
				subparts_durations.append(float(probe["format"]["duration"]))
				continue

			try:
				print(f"✅ Generating audio for subpart: {sub}")
				text = open(subpart_script_path, 'r', encoding='utf-8').read().strip()

				if self.engine == "edge":
					communicate = edge_tts.Communicate(text, self.voice)
					submaker = SubMaker()
					audio_bytes = bytearray()

					async for chunk in communicate.stream():
						if chunk["type"] == "audio":
							audio_bytes.extend(chunk["data"])
						elif chunk["type"] == "WordBoundary":
							submaker.feed(chunk)

					submaker.merge_cues(words=10)

					with open(subpart_audio_path, "wb") as f:
						f.write(audio_bytes)

					if sub == "_intro":
						amplified_path = subpart_audio_path.replace(".mp3", "_amplified.mp3")
						ffmpeg.input(subpart_audio_path).filter("volume", volume=3).output(amplified_path).overwrite_output().run()
						os.replace(amplified_path, subpart_audio_path)

					# ✅ Save individual subtitle file
					subpart_srt_path = subpart_audio_path.replace(".mp3", ".srt")
					with open(subpart_srt_path, "w", encoding="utf-8") as f:
						f.write(submaker.get_srt())

				elif self.engine == "openvoice":
					reference_speaker = OPENVOICE_SPEAKER_EMBEDDING
					cmd = [
						sys.executable,
						str(OPENVOICE_INFERENCE_SCRIPT),
						"--text", subpart_script_path,
						"--reference_speaker", reference_speaker,
						"--output", subpart_audio_path
					]
					subprocess.run(cmd, check=True)
				else:
					raise RuntimeError(f"❌ Unknown engine: {self.engine}")
				probe = ffmpeg.probe(subpart_audio_path)
				subparts_durations.append(float(probe["format"]["duration"]))
			except Exception as e:
				print(f"❌ TTS generation failed for subpart {sub}: {e}")
				raise(e)

		# Write subparts duration file at the end
		with open(durations_file_path, 'w', encoding='utf-8') as f:
			f.write(",".join(map(str, subparts_durations)))
		return subparts_durations

	async def generate_tts(self, script_path, formatted_title, main_points_amount, rate=None, pitch=None):
		print("🎤 STARTED tts/subtitles CREATION!")
		audio_path = script_path.replace(SCRIPT_EXTENSION, AUDIO_EXTENSION)
		srt_path = script_path.replace(SCRIPT_EXTENSION, SUBTITLE_EXTENSION)

		print(f"🔍 Checking for existing audio/subtitles for: {script_path}")
		if os.path.exists(audio_path) and os.path.exists(srt_path):
			print(f"🔍 Found existing audio/subtitles for: {script_path}")
			return audio_path, srt_path

		print(f"📢 Using engine: {self.engine} | Voice/Embedding: {self.voice}")

		text = open(script_path, 'r', encoding='utf-8').read().strip()
		if not text:
			raise ValueError("❌ Script is empty!")

		try:
			if self.engine == "edge":
				subparts = ["_intro"] + [f"_{i}" for i in range(1, main_points_amount+1)] + ["_conclusion"]

				audio_paths = []
				srt_entries = []
				current_offset = 0.0

				for sub in subparts:
					sub_audio = os.path.join(self.script_folder, formatted_title + sub + ".mp3")
					sub_srt = sub_audio.replace(".mp3", ".srt")

					if not os.path.exists(sub_audio) or not os.path.exists(sub_srt):
						break

					audio_paths.append(sub_audio)

					with open(sub_srt, "r", encoding="utf-8") as f:
						entries = f.read().strip().split("\n\n")
						for entry in entries:
							if not entry.strip():
								continue
							lines = entry.strip().splitlines()
							if len(lines) < 3:
								continue
							index = lines[0]
							times = lines[1]
							text = "\n".join(lines[2:])

							start, end = times.split(" --> ")
							start_sec = _srt_time_to_seconds(start) + current_offset
							end_sec = _srt_time_to_seconds(end) + current_offset

							srt_entries.append((start_sec, end_sec, text))

						# ✅ update offset
						probe = ffmpeg.probe(sub_audio)
						current_offset += float(probe["format"]["duration"])
				concat_txt_path = os.path.join(self.script_folder, f"{formatted_title}_concat_list.txt")
				with open(concat_txt_path, "w", encoding="utf-8") as f:
					for path in audio_paths:
						# use caminho absoluto e padronizado
						abs_path = os.path.abspath(path).replace("\\", "/")
						f.write(f"file '{abs_path}'\n")

				ffmpeg.input(concat_txt_path, format="concat", safe=0) \
					.output(audio_path, ar=44100, ac=2, acodec="libmp3lame", audio_bitrate="192k") \
					.global_args("-fflags", "+genpts") \
					.run(overwrite_output=True)

				# os.remove(concat_txt_path)

				with open(srt_path, "w", encoding="utf-8") as f:
					for i, (start, end, text) in enumerate(srt_entries, 1):
						f.write(f"{i}\n")
						f.write(f"{_seconds_to_srt_time(start)} --> {_seconds_to_srt_time(end)}\n")
						f.write(f"{text}\n\n")

			elif self.engine == "openvoice":
				audio_path = await self._generate_openvoice(script_path, audio_path)
				if not audio_path or not os.path.exists(audio_path):
					raise RuntimeError("❌ OpenVoice failed to produce audio. Aborting.")
				srt_path = script_path.replace(SCRIPT_EXTENSION, SUBTITLE_EXTENSION)
				with open(srt_path, "w", encoding="utf-8") as f:
					f.write("")  # OpenVoice doesn't generate subtitles
				return audio_path, srt_path

			elif self.engine == "google":
				audio_path = await self._generate_google(script_path, audio_path)
				srt_path = script_path.replace(SCRIPT_EXTENSION, SUBTITLE_EXTENSION)
				with open(srt_path, "w", encoding="utf-8") as f:
					f.write("")  # Optional: add subtitle support
				return audio_path, srt_path
			print(f"✅ Audio and subtitles saved using {self.engine} TTS.")
			return audio_path, srt_path

		except Exception as e:
			print(f"❌ TTS generation failed: {e}")
			raise e  # Fail fast and stop the pipeline

	async def _generate_kokoro(self, script_path, output_path):
		print(f"🧠 Kokoro - Reading text from: {script_path}")
		text = open(script_path, 'r', encoding='utf-8').read().strip()
		if not text:
			raise ValueError("❌ Script is empty. Cannot send to Kokoro.")

		timeout = aiohttp.ClientTimeout(total=300)
		async with aiohttp.ClientSession(timeout=timeout) as session:
			response = await session.post(
				f"{KOKORO_API_URL}/v1/audio/speech",
				json={"input": text, "voice": self.voice, "response_format": "mp3", "speed": 1.1}
			)
			if response.status != 200:
				raise RuntimeError(f"Kokoro TTS failed: {response.status} - {await response.text()}")
			with open(output_path, 'wb') as f:
				f.write(await response.read())
		print(f"🎧 Kokoro audio saved to {output_path}")
		return output_path

	async def _generate_openvoice(self, script_path, output_path):
		print(f"🧪 OpenVoice - Reading from: {script_path}")
		text = open(script_path, 'r', encoding='utf-8').read().strip()
		if not text:
			raise ValueError("❌ Script is empty. Cannot send to OpenVoice.")

		# Save raw text to temp txt file (if OpenVoice requires it)
		temp_text_path = script_path.replace(".txt", "_openvoice.txt")
		with open(temp_text_path, 'w', encoding='utf-8') as f:
			f.write(text)

		try:
			# Run inference using subprocess (you can adapt to your wrapper if needed)
			cmd = [
				sys.executable,
				str(OPENVOICE_INFERENCE_SCRIPT),
				"--text", temp_text_path,
				"--reference_speaker", OPENVOICE_SPEAKER_EMBEDDING,
				"--output", output_path,
				"--config_path", "C:/OpenVoice-main/checkpoints/converter/config.json",
				"--checkpoint_path", "C:/OpenVoice-main/checkpoints/converter/checkpoint.pth"
			]
			subprocess.run(cmd, check=True)
			print(f"🎧 OpenVoice audio saved to {output_path}")
			return output_path

		except subprocess.CalledProcessError as e:
			print(f"❌ OpenVoice failed: {e}")
			raise e  # force the engine to stop on failure

	async def _generate_google(self, script_path, output_path):
		print(f"🎧 Google TTS - Reading text from: {script_path}")
		text = open(script_path, 'r', encoding='utf-8').read().strip()
		if not text:
			raise ValueError("❌ Script is empty. Cannot send to Google TTS.")

		from google.cloud import texttospeech
		client = texttospeech.TextToSpeechClient.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)
		voice = texttospeech.VoiceSelectionParams(language_code="en-US", name=self.voice)
		audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

		# Split text into parts under 5000 bytes
		parts = split_text_by_bytes(text, max_bytes=5000)
		with open(output_path, "wb") as out:
			for idx, part in enumerate(parts):
				synthesis_input = texttospeech.SynthesisInput(text=part)
				response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
				out.write(response.audio_content)
				print(f"🎧 Part {idx+1}/{len(parts)} generated and written.")
		print(f"🎧 Google TTS audio saved to {output_path}")
		return output_path
