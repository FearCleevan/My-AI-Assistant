import logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

log = logging.getLogger(__name__)
_model = None


def get_model(on_status=None):
    global _model
    if _model is None:
        msg = "Loading embedding model (first run may download ~90 MB)..."
        if on_status:
            on_status(msg)
        else:
            print(f"  {msg}")
        _model = __import__("sentence_transformers").SentenceTransformer(config.EMBEDDING_MODEL)
        ready = "Embedding model ready."
        if on_status:
            on_status(ready)
        else:
            print(f"  {ready}")
    return _model


def embed_chunks(chunks, on_status=None):
    model = get_model(on_status=on_status)
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=32)
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks


def embed_query(query, on_status=None):
    return get_model(on_status=on_status).encode([query])[0].tolist()
