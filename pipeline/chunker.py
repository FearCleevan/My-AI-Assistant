import sys, os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def chunk_text(text, url, title, topic, chunk_size=None, chunk_overlap=None, version=1):
    chunk_size    = chunk_size    or config.CHUNK_SIZE
    chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP
    scraped_at    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    words = text.split()
    chunks, start, idx = [], 0, 0
    while start < len(words):
        chunk_words = words[start : start + chunk_size]
        chunks.append({
            "text":       " ".join(chunk_words),
            "url":        url,
            "title":      title,
            "topic":      topic,
            "chunk_id":   _url_to_id(url) + f"_{idx}",
            "scraped_at": scraped_at,
            "version":    version,
        })
        idx  += 1
        start += chunk_size - chunk_overlap
    return chunks


def _url_to_id(url: str) -> str:
    return (
        url.replace("https://", "")
           .replace("http://",  "")
           .replace("/",  "_")
           .replace(".",  "_")
           .replace("-",  "_")[:80]
    )
