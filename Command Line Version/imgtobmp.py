#!/usr/bin/env python3
"""
Convert image file to python module for use with bitmap method.

Usage:
    python imgtobitmap.py image.png 4
    python imgtobitmap.py image.png 4 -o image.py
"""

from PIL import Image
import argparse
from pathlib import Path


def main():

    parser = argparse.ArgumentParser(
        prog='imgtobitmap',
        description='Convert image file to python module for use with bitmap method.')

    parser.add_argument(
        'image_file',
        help='Name of file containing image to convert')

    parser.add_argument(
        'bits_per_pixel',
        type=int,
        choices=range(1, 9),
        help='The number of bits to use per pixel (1..8)')

    parser.add_argument(
        '-o', '--output',
        help='Output .py filename (optional)')

    args = parser.parse_args()

    bits = args.bits_per_pixel
    img_path = Path(args.image_file)
    out_path = Path(args.output) if args.output else img_path.with_suffix(".py")

    img = Image.open(img_path)
    if bits == 1:
        # Force strict black/white threshold
        img = img.convert("L")  # grayscale
        img = img.point(lambda p: 255 if p > 127 else 0, mode='1')
        img = img.convert("P")

        # Force palette manually: index 0 = black, 1 = white
        img.putpalette([
            0, 0, 0,       # black
            255, 255, 255  # white
        ] + [0, 0, 0] * 254)

    else:
        img = img.convert("P", palette=Image.ADAPTIVE, colors=2**bits)

    palette = img.getpalette()

    colors = []
    for color in range(1 << bits):
        color565 = (
            ((palette[color*3] & 0xF8) << 8)
            | ((palette[color*3+1] & 0xFC) << 3)
            | (palette[color*3+2] >> 3)
        )

        # swap bytes
        color565 = ((color565 & 0xff) << 8) + ((color565 & 0xff00) >> 8)
        colors.append(f'0x{color565:04x}')

    image_bitstring = ''

    for y in range(img.height):
        for x in range(img.width):
            pixel = img.getpixel((x, y))
            for bit in range(bits, 0, -1):
                image_bitstring += '1' if (pixel & (1 << bit-1)) else '0'

    bitmap_bits = len(image_bitstring)

    with open(out_path, "w") as f:

        f.write(f'HEIGHT = {img.height}\n')
        f.write(f'WIDTH = {img.width}\n')
        f.write(f'COLORS = {1 << bits}\n')
        f.write(f'BITS = {bitmap_bits}\n')
        f.write(f'BPP = {bits}\n')
        f.write('PALETTE = [')
        f.write(','.join(colors))
        f.write(']\n\n')

        f.write("_bitmap = \\\n")
        f.write("b'")

        for i in range(0, bitmap_bits, 8):

            if i and i % (16*8) == 0:
                f.write("'\\\nb'")

            value = image_bitstring[i:i+8]
            color = int(value, 2)
            f.write(f'\\x{color:02x}')

        f.write("'\n")
        f.write("BITMAP = memoryview(_bitmap)\n")

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()