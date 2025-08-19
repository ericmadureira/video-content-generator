import os
from PIL import Image, ImageFilter


BLUR_RATE = 20  # 0 to 100%
CURRENT_FOLDER = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLDER = os.path.join(CURRENT_FOLDER, "horizontal_images")
TARGET_RATIO = 16 / 9

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def is_vertical(img):
	return img.height > img.width

def is_square(img):
	return (img.height == img.width)

def is_wide_but_small_and_out_of_target_ratio(img):
	return (img.height < img.width) and (img.width < 1920) and ((img.width / img.height) < TARGET_RATIO)

def convert_to_horizontal(img, base_name):
	width, height = img.size
	new_width = int(height * TARGET_RATIO)

	if new_width <= width:
		new_width = width + 300  # fallback if width is already wide

	bg = img.resize((new_width, height), Image.LANCZOS)
	bg = bg.filter(ImageFilter.GaussianBlur(BLUR_RATE))
	bg.paste(img, ((new_width - width) // 2, 0))

	output_path = os.path.join(OUTPUT_FOLDER, base_name)
	bg.save(output_path)

def convert_all_in_folder(folder_path):
	converted = 0
	skipped = 0

	for filename in os.listdir(folder_path):
		filepath = os.path.join(folder_path, filename)
		if os.path.isdir(filepath) or not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
			continue

		try:
			with Image.open(filepath) as img:
				if is_vertical(img) or is_square(img):
					width, height = img.size
					new_width = int(height * TARGET_RATIO)
					new_width = max(new_width, width + 300)

					bg = img.resize((new_width, height), Image.LANCZOS)
					bg = bg.filter(ImageFilter.GaussianBlur(20))
					bg.paste(img, ((new_width - width) // 2, 0))

					bg.save(filepath)
					converted += 1
				else:
					skipped += 1
		except Exception as e:
			print(f"❌ Error: {filename} → {e}")

	return converted, skipped


# ✅ CLI fallback
if __name__ == "__main__":
	# Use current folder (where script is) as input
	current_dir = os.path.dirname(os.path.abspath(__file__))
	print(f"📂 Running vertical converter on: {current_dir}")
	converted, skipped = convert_all_in_folder(current_dir)
	print(f"✅ Done: {converted} converted, {skipped} skipped.")
