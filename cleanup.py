import os
import sys
from PIL import Image
from xml.etree import ElementTree as ET

# Define the root directory to scan
# Based on your downloader script, the icons are in a folder called 'icons'
ICON_ROOT_DIR = "icons"

def check_png_corrupted(file_path):
    """Checks if a PNG file is corrupted using the Pillow library."""
    try:
        # Open the image file
        img = Image.open(file_path)
        # Verify that it is, in fact, an image by reading its header/footer
        # This will raise exceptions for many common corruptions
        img.verify()

        # Re-open and load the image content to catch deeper issues like truncated files
        # The verify() call closes the file, so we need to re-open it.
        img = Image.open(file_path)
        img.load()
        return False  # Not corrupted
    except (IOError, SyntaxError, FileNotFoundError, OSError) as e:
        # Catch common image-related errors indicating corruption
        print(f"    ❌ PNG corrupted or invalid: {e}")
        return True

def check_svg_corrupted(file_path):
    """Checks if an SVG file is valid XML and has the root <svg> tag."""
    try:
        # Parse the file as XML
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Check if the root tag is 'svg' (ignoring namespaces for a quick check)
        if 'svg' in root.tag.lower():
            # A minimal check for a valid-looking SVG
            return False
        else:
            print(f"    ❌ SVG invalid: Root tag is not <svg> (found: {root.tag})")
            return True
            
    except ET.ParseError as e:
        # Catch XML parsing errors, which indicate corruption or incomplete file
        print(f"    ❌ SVG corrupted (XML error): {e}")
        return True
    except FileNotFoundError:
        print(f"    ❌ SVG file not found.")
        return True

def delete_faulty_images(root_dir):
    """Walks through the root directory and deletes any faulty images."""
    if not os.path.isdir(root_dir):
        print(f"Error: Directory '{root_dir}' not found.")
        return

    total_deleted = 0
    
    print(f"--- Starting scan of '{root_dir}' for faulty images... ---\n")

    # os.walk traverses the directory tree, yielding (dirpath, dirnames, filenames)
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # We only care about files in the subdirectories, not the root 'icons' folder itself
        if dirpath == root_dir:
            continue
            
        print(f"Scanning folder: {os.path.basename(dirpath)}")

        for filename in filenames:
            file_path = os.path.join(dirpath, filename)

            is_corrupt = False
            
            if filename.lower().endswith(".png"):
                is_corrupt = check_png_corrupted(file_path)
            elif filename.lower().endswith(".svg"):
                is_corrupt = check_svg_corrupted(file_path)
            
            if is_corrupt:
                try:
                    os.remove(file_path)
                    total_deleted += 1
                    print(f"    ✅ DELETED: {os.path.join(os.path.basename(dirpath), filename)}")
                except OSError as e:
                    print(f"    ⚠️  Could not delete {file_path}: {e}")
    
    print(f"\n--- Scan complete. Total faulty images deleted: {total_deleted} ---")


if __name__ == "__main__":
    delete_faulty_images(ICON_ROOT_DIR)