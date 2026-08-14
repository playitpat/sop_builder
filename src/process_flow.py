from __future__ import annotations

import io
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont


def mermaid_labels(source: str) -> list[str]:
    return [
        match.group(1)
        for match in re.finditer(r'^\s*S\d+\["(.+?)"\]\s*$', source, re.MULTILINE)
    ]


def render_mermaid_png(source: str) -> bytes:
    """Render the MVP's linear Mermaid subset as a corporate-style process chart."""
    labels = mermaid_labels(source)
    if not labels:
        raise ValueError("No supported Mermaid process steps were found")
    width, box_width, box_height, gap = 1200, 980, 112, 62
    height = 100 + len(labels) * box_height + (len(labels) - 1) * gap + 60
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=24)
    small = ImageFont.load_default(size=20)
    navy, blue, pale, purple = "#102a43", "#1769c2", "#edf5ff", "#7253a6"
    draw.text(
        (width // 2, 28), "Approved Process Flow", fill=navy, font=font, anchor="ma"
    )
    x = (width - box_width) // 2
    y = 82
    for index, label in enumerate(labels, 1):
        draw.rounded_rectangle(
            (x, y, x + box_width, y + box_height),
            radius=20,
            fill=pale,
            outline=blue,
            width=4,
        )
        draw.ellipse((x + 24, y + 28, x + 80, y + 84), fill=purple)
        draw.text((x + 52, y + 56), str(index), fill="white", font=small, anchor="mm")
        wrapped = textwrap.wrap(label, width=82)[:3]
        line_y = y + box_height / 2 - (len(wrapped) - 1) * 14
        for line in wrapped:
            draw.text((x + 105, line_y), line, fill=navy, font=small, anchor="lm")
            line_y += 28
        if index < len(labels):
            center = width // 2
            draw.line(
                (center, y + box_height, center, y + box_height + gap - 12),
                fill=blue,
                width=5,
            )
            draw.polygon(
                [
                    (center - 12, y + box_height + gap - 24),
                    (center + 12, y + box_height + gap - 24),
                    (center, y + box_height + gap - 6),
                ],
                fill=blue,
            )
        y += box_height + gap
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
