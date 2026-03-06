"""Text chunking with configurable size and overlap."""

from __future__ import annotations


def chunk_text(pages: list[dict], chunk_size: int = 500) -> list[dict]:
    if not pages:
        return []

    if "slide_number" in pages[0]:
        return _chunk_slides(pages)

    return _chunk_pages(pages, chunk_size)


def _chunk_slides(slides: list[dict]) -> list[dict]:
    chunks: list[dict] = []
    for idx, slide in enumerate(slides):
        chunks.append({
            "chunk_index": idx,
            "text": slide["text"],
            "page_number": slide.get("slide_number", idx + 1),
            "section_title": slide.get("title", ""),
        })
    return chunks


def _chunk_pages(pages: list[dict], chunk_size: int) -> list[dict]:
    overlap = chunk_size // 5
    chunks: list[dict] = []
    chunk_idx = 0

    for page in pages:
        words = page["text"].split()
        if not words:
            continue

        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text_str = " ".join(words[start:end])

            chunks.append({
                "chunk_index": chunk_idx,
                "text": chunk_text_str,
                "page_number": page.get("page_number", page.get("paragraph_index", 0)),
                "section_title": page.get("section_title", page.get("style", "")),
            })
            chunk_idx += 1

            if end >= len(words):
                break
            start = end - overlap

    return chunks
