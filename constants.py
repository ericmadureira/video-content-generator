import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
ASSET_FOLDER = "assets"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # Gets the base directory of the project
BGM_FOLDER = "assets/bgm"
CREDENTIALS_FOLDER = "credentials"
FONTS_FOLDER = "fonts"
IMAGE_SUMMARY_FILE = "image_summary.json"
LOCAL_IMAGE_DB = os.getenv("LOCAL_IMAGE_DB")
LOG_FILE = "renamed_images.json"
LOGO_FOLDER = "assets/logo"

PLAYLIST_FOLDER = "playlists"
SCRIPT_FOLDER = "scripts"
THUMBNAIL_FOLDER = "thumbnails"
VIDEO_OUTPUT_FOLDER = "video_output"

# Config variables
EDUCATION_YOUTUBE_CATEGORY_ID = "27"
PEOPLE_BLOGS_YOUTUBE_CATEGORY_ID = "22"
GOOGLE_OAUTH_PORT = 8765
TOPIC_IMAGES_PER_SUBPART = 15
IMAGES_PER_TOPIC = TOPIC_IMAGES_PER_SUBPART + 2  # (Includes 1 intro + 15 topic images + 1 conclusion).
MAX_PLAYLISTS_PER_REQUEST = 80

# Default extensions
AUDIO_EXTENSION = ".mp3"
SCRIPT_EXTENSION = ".txt"
SUBTITLE_EXTENSION = ".srt"
VIDEO_EXTENSION = ".mp4"
