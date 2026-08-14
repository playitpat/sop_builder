from __future__ import annotations

import io
import math
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont


def mermaid_labels(source: str) -> list[str]:
    return [
        match.group(1)
        for match in re.finditer(r'^\s*S\d+\["(.+?)"\]\s*$', source, re.MULTILINE)
    ]


def _position(
    index: int,
    columns: int,
    box_width: int,
    horizontal_gap: int,
    top: int,
    row_pitch: int,
) -> tuple[int, int]:
    row, offset = divmod(index, columns)
    column = offset if row % 2 == 0 else columns - 1 - offset
    return 30 + column * (box_width + horizontal_gap), top + row * row_pitch


def _arrow(
    draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str
) -> None:
    draw.line((*start, *end), fill=color, width=5)
    if start[1] == end[1]:
        direction = 1 if end[0] > start[0] else -1
        tip = end
        draw.polygon(
            [
                tip,
                (tip[0] - direction * 16, tip[1] - 10),
                (tip[0] - direction * 16, tip[1] + 10),
            ],
            fill=color,
        )
    else:
        draw.polygon(
            [end, (end[0] - 10, end[1] - 16), (end[0] + 10, end[1] - 16)], fill=color
        )


def render_mermaid_png(source: str) -> bytes:
    """Render confirmed linear Mermaid steps as a readable, page-friendly snake chart."""
    labels = mermaid_labels(source)
    if not labels:
        raise ValueError("No supported Mermaid process steps were found")

    width, columns = 1200, 3
    box_width, box_height = 340, 108
    horizontal_gap, vertical_gap = 60, 38
    top = 80
    row_pitch = box_height + vertical_gap
    rows = math.ceil(len(labels) / columns)
    height = top + rows * box_height + max(0, rows - 1) * vertical_gap + 45
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=26)
    text_font = ImageFont.load_default(size=16)
    number_font = ImageFont.load_default(size=18)
    navy, blue, pale, purple = "#102a43", "#1769c2", "#edf5ff", "#7253a6"
    draw.text(
        (width // 2, 26),
        "Approved Process Flow",
        fill=navy,
        font=title_font,
        anchor="ma",
    )

    positions = [
        _position(index, columns, box_width, horizontal_gap, top, row_pitch)
        for index in range(len(labels))
    ]
    for index in range(len(positions) - 1):
        x1, y1 = positions[index]
        x2, y2 = positions[index + 1]
        if y1 == y2:
            if x2 > x1:
                start, end = (x1 + box_width, y1 + box_height // 2), (
                    x2 - 8,
                    y2 + box_height // 2,
                )
            else:
                start, end = (x1, y1 + box_height // 2), (
                    x2 + box_width + 8,
                    y2 + box_height // 2,
                )
        else:
            start, end = (x1 + box_width // 2, y1 + box_height), (
                x2 + box_width // 2,
                y2 - 8,
            )
        _arrow(draw, start, end, blue)

    for index, (label, (x, y)) in enumerate(zip(labels, positions), 1):
        draw.rounded_rectangle(
            (x, y, x + box_width, y + box_height),
            radius=16,
            fill=pale,
            outline=blue,
            width=3,
        )
        draw.ellipse((x + 13, y + 34, x + 53, y + 74), fill=purple)
        draw.text(
            (x + 33, y + 54), str(index), fill="white", font=number_font, anchor="mm"
        )
        wrapped = textwrap.wrap(label, width=34)[:4]
        line_y = y + box_height / 2 - (len(wrapped) - 1) * 10
        for line in wrapped:
            draw.text((x + 67, line_y), line, fill=navy, font=text_font, anchor="lm")
            line_y += 21

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def png_dimensions(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size
