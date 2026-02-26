#!/usr/bin/env python3
"""
Dear PyGui front-end for imgtobitmap.

- Select an image file
- Choose bits-per-pixel (1..8)
- Optionally choose an output .py path
- Click "Convert" to generate the bitmap module
"""

from pathlib import Path

from PIL import Image
import dearpygui.dearpygui as dpg
import tkinter as tk
from tkinter import filedialog

def open_system_file_picker():
    # Hide the root Tk window
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Select image",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"),
            ("All files", "*.*")
        ]
    )

    root.destroy()

    if file_path:
        dpg.set_value("image_path_input", file_path)

        # Suggest output name
        suggested = str(Path(file_path).with_suffix(".py"))
        if not dpg.get_value("output_path_input"):
            dpg.set_value("output_path_input", suggested)
# -------- Core conversion logic (adapted from CLI script) --------

def convert_image_to_bitmap(image_file: str, bits_per_pixel: int, output: str | None = None) -> Path:
    """
    Convert an image to a Python module with bitmap data.

    :param image_file: Path to the source image.
    :param bits_per_pixel: Bits per pixel (1..8).
    :param output: Optional output .py path; if None, derive from image name.
    :return: Path to the written .py file.
    """
    if bits_per_pixel < 1 or bits_per_pixel > 8:
        raise ValueError("bits_per_pixel must be between 1 and 8")

    img_path = Path(image_file)
    if not img_path.is_file():
        raise FileNotFoundError(f"Image file not found: {img_path}")

    out_path = Path(output) if output else img_path.with_suffix(".py")

    # Ensure .py extension if user forgot it
    if out_path.suffix.lower() != ".py":
        out_path = out_path.with_suffix(".py")

    img = Image.open(img_path)
    bits = bits_per_pixel

    if bits == 1:
        # Force strict black/white threshold (same as original script)
        img = img.convert("L")  # grayscale
        img = img.point(lambda p: 255 if p > 127 else 0, mode='1')
        img = img.convert("P")

        # Force palette manually: index 0 = black, 1 = white
        img.putpalette(
            [
                0, 0, 0,       # black
                255, 255, 255  # white
            ] + [0, 0, 0] * 254
        )
    else:
        # Palette-based conversion with 2**bits colors
        img = img.convert("P", palette=Image.ADAPTIVE, colors=2**bits)

    palette = img.getpalette()

    colors = []
    for color in range(1 << bits):
        color565 = (
            ((palette[color * 3] & 0xF8) << 8)
            | ((palette[color * 3 + 1] & 0xFC) << 3)
            | (palette[color * 3 + 2] >> 3)
        )

        # swap bytes (endian swap)
        color565 = ((color565 & 0xff) << 8) + ((color565 & 0xff00) >> 8)
        colors.append(f'0x{color565:04x}')

    image_bitstring = ""

    for y in range(img.height):
        for x in range(img.width):
            pixel = img.getpixel((x, y))
            for bit in range(bits, 0, -1):
                image_bitstring += "1" if (pixel & (1 << bit - 1)) else "0"

    bitmap_bits = len(image_bitstring)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"HEIGHT = {img.height}\n")
        f.write(f"WIDTH = {img.width}\n")
        f.write(f"COLORS = {1 << bits}\n")
        f.write(f"BITS = {bitmap_bits}\n")
        f.write(f"BPP = {bits}\n")
        f.write("PALETTE = [")
        f.write(",".join(colors))
        f.write("]\n\n")

        f.write("_bitmap = \\\n")
        f.write("b'")

        for i in range(0, bitmap_bits, 8):
            if i and i % (16 * 8) == 0:
                f.write("'\\\nb'")
            value = image_bitstring[i:i + 8]
            color = int(value, 2)
            f.write(f"\\x{color:02x}")

        f.write("'\n")
        f.write("BITMAP = memoryview(_bitmap)\n")

    return out_path


# -------- Dear PyGui helpers --------

def append_log(message: str):
    """Append a line of text to the log widget."""
    previous = dpg.get_value("status_log")
    if previous:
        new_text = previous + "\n" + message
    else:
        new_text = message
    dpg.set_value("status_log", new_text)


def file_dialog_callback(sender, app_data):
    """
    Dear PyGui file dialog callback.

    app_data["file_path_name"] contains the full path.
    """
    path = app_data.get("file_path_name")
    if path:
        dpg.set_value("image_path_input", path)
        # If no explicit output path, suggest <image>.py
        out_path = str(Path(path).with_suffix(".py"))
        if not dpg.get_value("output_path_input"):
            dpg.set_value("output_path_input", out_path)


def convert_button_callback(sender, app_data):
    image_path = dpg.get_value("image_path_input").strip()
    output_path = dpg.get_value("output_path_input").strip()
    bpp = dpg.get_value("bpp_slider")

    dpg.set_value("status_log", "")  # clear log for this run

    if not image_path:
        append_log("ERROR: Please select an image file first.")
        return

    try:
        append_log(f"Converting:\n  Image: {image_path}\n  BPP: {bpp}")
        if output_path:
            append_log(f"  Output: {output_path}")
        else:
            append_log("  Output: <image>.py (auto)")

        out_path = convert_image_to_bitmap(
            image_file=image_path,
            bits_per_pixel=bpp,
            output=output_path if output_path else None,
        )

        append_log(f"SUCCESS: Wrote {out_path}")

    except FileNotFoundError as e:
        append_log(f"ERROR: {e}")
    except Exception as e:
        append_log(f"ERROR: {type(e).__name__}: {e}")


def main():
    dpg.create_context()

    with dpg.window(label="Image to .py Bitmap Converter", tag="Primary Window", width=600, height=400):
        dpg.add_text("Image to .py Bitmap Converter")
        dpg.add_separator()

        # Image file row
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                label="Image file",
                tag="image_path_input",
                width=360,
                hint="Choose an image (png/jpg/bmp/etc.)"
            )
            dpg.add_button(label="Browse...", callback=open_system_file_picker)

        # BPP slider
        dpg.add_slider_int(
            label="Bits per pixel (1..8)",
            tag="bpp_slider",
            min_value=1,
            max_value=8,
            default_value=4,
            width=300
        )

        # Output file
        dpg.add_input_text(
            label="Output .py file (optional)",
            tag="output_path_input",
            width=360,
            hint="Leave blank to use <image>.py"
        )

        dpg.add_spacing(count=2)
        dpg.add_button(label="Convert", width=120, callback=convert_button_callback)
        dpg.add_separator()
        dpg.add_text("Status / Log:")
        dpg.add_input_text(
            tag="status_log",
            multiline=True,
            readonly=True,
            height=140,
            width=-1
        )
        
        dpg.add_text("Outputs a .py file, but you can use the contents in arduino or whatever.")
        dpg.add_text("1 bit per pixel will be forced black & white, good for SSD1306 and similar displays.")
        dpg.add_text("Depending on your library, use in micropython will usually work along the lines of:")
        dpg.add_text("Upload file, bitmapimg.py for example, to your MCU, then code is something like")
        dpg.add_text("|    import bitmapimg")
        dpg.add_text("|    display.bitmap(bitmapimg, 90, 160)")
        dpg.add_text("Much love, Erin.")

    dpg.create_viewport(title="Image to .py Bitmap Converter", width=640, height=520)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()