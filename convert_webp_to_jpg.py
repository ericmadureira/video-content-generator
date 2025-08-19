import os
from PIL import Image

def convert_webp_to_jpg_in_folder(folder_path):
	converted = 0
	skipped = 0

	for filename in os.listdir(folder_path):
		if filename.lower().endswith(".webp"):
			input_path = os.path.join(folder_path, filename)
			base_name = os.path.splitext(filename)[0]
			output_path = os.path.join(folder_path, f"{base_name}.jpg")

			try:
				with Image.open(input_path) as img:
					rgb_img = img.convert("RGB")
					rgb_img.save(output_path, "JPEG", quality=97)
					print(f"✅ Converted: {filename} → {base_name}.jpg")

				os.remove(input_path)
				print(f"🗑️ Deleted: {filename}")
				converted += 1

			except Exception as e:
				print(f"❌ Error converting {filename}: {e}")
		else:
			skipped += 1

	return converted, skipped


# CLI fallback
if __name__ == "__main__":
	current_dir = os.path.dirname(os.path.abspath(__file__))
	print(f"📂 Running .webp to .jpg conversion on: {current_dir}")
	converted, skipped = convert_webp_to_jpg_in_folder(current_dir)
	print(f"✅ Done: {converted} converted, {skipped} skipped.")
