"""
Shared text utilities: cleaning and chunking.

Chunking uses a simple, deterministic sliding-window strategy over
whitespace-normalized text. This is intentionally straightforward so it is
easy to reason about, test, and explain.
"""

from __future__ import annotations

import re
import uuid


def clean_text(text: str) -> str:
    """Normalize whitespace and strip control characters from extracted text."""
    if not text:
        return ""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
) -> list[str]:
    """
    Split text into overlapping chunks of approximately `chunk_size`
    characters, breaking on sentence/paragraph boundaries where possible.
    """
    text = clean_text(text)
    if not text:
        return []

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 4)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
        # start next chunk with overlap tail of previous chunk
        overlap_tail = current[-chunk_overlap:] if current and chunk_overlap else ""
        current = f"{overlap_tail} {sentence}".strip()

        # Handle a single sentence longer than chunk_size on its own.
        while len(current) > chunk_size:
            chunks.append(current[:chunk_size])
            current = current[chunk_size - chunk_overlap :]

    if current:
        chunks.append(current)

    return [c.strip() for c in chunks if c.strip()]


def new_id(prefix: str = "") -> str:
    identifier = uuid.uuid4().hex[:12]
    return f"{prefix}{identifier}" if prefix else identifier
