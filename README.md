# Content Creation API

## Setting Up the Project

### Step 1: Install Python and Virtual Environment

`python -m venv venv`  # Create a virtual environment.
`venv\Scripts\activate`  # Activate the virtual environment (Windows).

### Step 2: Install Dependencies

Once you have your virtual environment active, install the required dependencies by running:
`pip install -r requirements.txt`
or try this if first fails:
`pip install python-dotenv flask openai requests numpy edge_tts ffmpeg-python Pillow`

### Step 3: Add environment variables

Make sure to have a .env file filled correctly. Check `.example.env` if necessary.

### Step 4: Add GCP credentials

Make sure to have correct `client_secrets.json` and `token.json` files for each channel in `/credentials` folder.

### Step 3: Run the app

Run the following commands to run API locally:

1. Activate venv with `venv\Scripts\activate` (windows commands)
2. Run the application with `python app.py`
Then app will be available on <http://127.0.0.1:5000/dashboard>

## Commands and tools

### Update image summary

`python generate_image_summary.py`

### Rename images

`python rename_images.py`
