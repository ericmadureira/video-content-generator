import google.auth
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import json
import os
import time

from constants import CREDENTIALS_FOLDER, PEOPLE_BLOGS_YOUTUBE_CATEGORY_ID, GOOGLE_OAUTH_PORT, MAX_PLAYLISTS_PER_REQUEST, PLAYLIST_FOLDER, THUMBNAIL_FOLDER
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload


class YouTubeUploader:
	def __init__(self, category):
		"""
		Initialize YouTube API client for a specific channel.
		:param category: Name of the YouTube channel (e.g., 'gardening', 'health', 'diabetes').
		"""
		self.category = category
		self.credentials_path = f"{CREDENTIALS_FOLDER}/{category}_client_secrets.json"
		self.token_path = f"{CREDENTIALS_FOLDER}/{category}_token.json"
		self.api_service_name = "youtube"
		self.api_version = "v3"
		self.scopes = [
			"https://www.googleapis.com/auth/youtube.upload",
			"https://www.googleapis.com/auth/youtube.force-ssl",
			"https://www.googleapis.com/auth/youtube.readonly",
			"https://www.googleapis.com/auth/youtube"
		]
		self.youtube = self.authenticate()


	def get_playlist_name(self, playlist_id):
		"""Fetch playlist name from the JSON file based on category and playlist ID."""
		playlist_file = f"{PLAYLIST_FOLDER}/{self.category}_playlists.json"
		if os.path.exists(playlist_file):
			with open(playlist_file, "r", encoding="utf-8") as f:
				playlists = json.load(f)
				return playlists.get(playlist_id, "Unknown Playlist")
		return "Unknown Playlist"


	def authenticate(self):
		"""Authenticate with OAuth 2.0, managing separate tokens per account."""
		credentials = None

		# Load token if it exists
		if os.path.exists(self.token_path):
			credentials = Credentials.from_authorized_user_file(self.token_path)

		# Refresh or authenticate if needed
		if not credentials or not credentials.valid:
			if credentials and credentials.expired and credentials.refresh_token:
				try:
					print(f"🔄 Refreshing YouTube API token for {self.category}...")
					credentials.refresh(google.auth.transport.requests.Request())
				except Exception as e:
					print(f"⚠️ Refresh failed for {self.category}: {e}")
					print("🔁 Attempting full re-authentication instead...")
					credentials = None
					if os.path.exists(self.token_path):
						os.remove(self.token_path)  # Clear invalid token

			if not credentials:
				print(f"🔑 Full authentication required for {self.category}. Please sign in.")
				flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
					self.credentials_path, self.scopes
				)
				credentials = flow.run_local_server(
					port=8080,
					access_type='offline', # ✅ Enables refresh token
					prompt='consent'       # ✅ Forces refresh token to be returned every time
				)
				with open(self.token_path, "w") as token_file:
					token_file.write(credentials.to_json())

		return googleapiclient.discovery.build(self.api_service_name, self.api_version, credentials=credentials)


	def upload_video(self, video_path, title, description, tags, privacy_status="private", category_id=PEOPLE_BLOGS_YOUTUBE_CATEGORY_ID, scheduled_time=None, thumbnail_path=None, playlist_ids=None):
		"""
		Uploads a video to YouTube with metadata, optional scheduling, and playlist associations.

		:param video_path: Path to the video file.
		:param title: Video title.
		:param description: Video description.
		:param tags: List of tags.
		:param privacy_status: Video visibility ("public", "unlisted", "private").
		:param category_id: YouTube category ID.
		:param scheduled_time: (Optional) ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ) to schedule the video.
		:param thumbnail_path: (Optional) Path to a custom thumbnail image.
		:param playlist_ids: (Optional) List of playlist IDs to add the video to.
		:return: Video ID or None if failed.
		"""
		print("🚀 Uploading video to YouTube...")
		upload_start_time = time.time()

		if not self.youtube:
			print("❌ YouTube API client is not authenticated.")
			return None

		# ✅ If scheduling, enforce "private" status and set publishAt
		status = {"privacyStatus": privacy_status}
		if scheduled_time:
			status["publishAt"] = scheduled_time
			status["privacyStatus"] = "private"  # Required for scheduling

		try:
			request = self.youtube.videos().insert(
				part="snippet,status",
				body={
					"snippet": {
						"title": title,
						"description": description,
						"tags": tags,
						"categoryId": category_id
					},
					"status": status
				},
				media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
			)

			response = request.execute()
			video_id = response["id"]
			print(f"✅ Upload successful! Video ID: {video_id}")

			# ✅ Set thumbnail if a valid path is provided
			if thumbnail_path and os.path.exists(thumbnail_path):
				self.set_thumbnail(video_id, thumbnail_path)

			if playlist_ids:
				if isinstance(playlist_ids, str):
					playlist_ids = [playlist_ids]  # ✅ Convert single string to list

				print(f"🎥 Video {video_id} is being added to playlists: {playlist_ids}")

				for playlist_id in playlist_ids:
					self.add_video_to_playlist(video_id, playlist_id)

			upload_end_time = time.time()
			print(f"🚀 YouTube upload time: {round(upload_end_time - upload_start_time, 1)} s")
			return video_id
		except googleapiclient.errors.HttpError as e:
			print(f"❌ Upload failed: {e}")
			return None


	def set_thumbnail(self, video_id, thumbnail_path):
		"""
		Sets a custom thumbnail for the uploaded video.
		:param video_id: The ID of the uploaded video.
		:param thumbnail_path: Path to the thumbnail image.
		"""
		if not self.youtube:
			print("❌ YouTube API client is not authenticated.")
			return None

		try:
			request = self.youtube.thumbnails().set(
				videoId=video_id,
				media_body=MediaFileUpload(thumbnail_path)
			)
			request.execute()
			print(f"✅ Thumbnail updated for video ID: {video_id}")
		except googleapiclient.errors.HttpError as e:
			print(f"❌ Failed to set thumbnail: {e}")


	def fetch_and_store_playlists(self):
		"""
		Fetches the full list of playlists from the channel and stores them in a JSON file, sorted alphabetically.
		"""
		playlists = {}
		next_page_token = None

		try:
			while True:
				request = self.youtube.playlists().list(
					part="snippet",
					mine=True,
					maxResults=MAX_PLAYLISTS_PER_REQUEST,
					pageToken=next_page_token
				)
				response = request.execute()

				for playlist in response.get("items", []):
					playlists[playlist["id"]] = playlist["snippet"]["title"]

				next_page_token = response.get("nextPageToken")
				if not next_page_token:
					break

			# ✅ Sort and save
			sorted_playlists = dict(sorted(playlists.items(), key=lambda item: item[1].lower()))
			playlist_file_path = os.path.join(PLAYLIST_FOLDER, f"{self.category}_playlists.json")

			with open(playlist_file_path, "w", encoding="utf-8") as f:
				json.dump(sorted_playlists, f, indent=4, ensure_ascii=False)

			print(f"✅ Fetched {len(sorted_playlists)} playlists and saved to {playlist_file_path}")
			return sorted_playlists

		except Exception as e:
			print(f"❌ ERROR fetching playlists: {e}")
			return None


	def add_video_to_playlist(self, video_id, playlist_id):
		"""
		Adds a video to the specified YouTube playlist.
		"""
		try:
			playlist_name = self.get_playlist_name(playlist_id)
			print(f"📝 Attempting to add video {video_id} to playlist {playlist_name}...")

			# Check if the video is already in the playlist
			existing_videos = self.youtube.playlistItems().list(
				part="snippet",
				playlistId=playlist_id,
				maxResults=MAX_PLAYLISTS_PER_REQUEST
			).execute()

			if any(item["snippet"]["resourceId"]["videoId"] == video_id for item in existing_videos.get("items", [])):
				print(f"⚠️ Video {video_id} is already in playlist {playlist_name}. Skipping...")
				return

			# Insert the video into the playlist
			request = self.youtube.playlistItems().insert(
				part="snippet",
				body={
					"snippet": {
						"playlistId": playlist_id,
						"resourceId": {
							"kind": "youtube#video",
							"videoId": video_id
						}
					}
				}
			)
			request.execute()
			print(f"✅ Successfully added video {video_id} to playlist {playlist_name}.")

		except googleapiclient.errors.HttpError as e:
			print(f"❌ ERROR adding video {video_id} to playlist {playlist_name}: {e}")


if __name__ == "__main__":
	# Example usage:
	gardening_uploader = YouTubeUploader("gardening")
	gardening_uploader.fetch_and_store_playlists()

	health_uploader = YouTubeUploader("health")
	health_uploader.fetch_and_store_playlists()

	diabetes_uploader = YouTubeUploader("diabetes")
	diabetes_uploader.fetch_and_store_playlists()
