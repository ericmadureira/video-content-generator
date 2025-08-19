import re
import unicodedata

def normalize_text(text):
	text = unicodedata.normalize('NFD', text)
	return ''.join(char for char in text if unicodedata.category(char) != 'Mn').lower().strip()

def sanitize_filename(name):
	return re.sub(r'[^\w\-_\. ]', '_', name)
