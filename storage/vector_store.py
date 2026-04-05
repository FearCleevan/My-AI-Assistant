import logging, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

log = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, storage_path: str | None = None):
        """
        storage_path: base data directory (e.g. E:\\my_data).
        ChromaDB files are stored at storage_path/vector_db/.
        Falls back to config.VECTOR_DB_DIR when None.
        """
        import chromadb
        from chromadb.config import Settings

        if storage_path:
            db_path = os.path.join(os.path.normpath(storage_path), "vector_db")
        else:
            db_path = config.VECTOR_DB_DIR

        os.makedirs(db_path, exist_ok=True)
        self.db_path = db_path
        self.client  = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )

    # ── Collections ────────────────────────────────────────────────────────

    @staticmethod
    def _safe_name(topic: str) -> str:
        """Convert any topic string to a valid ChromaDB collection name.

        ChromaDB requires: 3-512 chars, [a-zA-Z0-9._-], must start and end
        with [a-zA-Z0-9].  We prefix with 'topic_' and strip anything illegal.
        """
        import re
        safe = topic.lower()
        safe = re.sub(r"[^a-z0-9._-]+", "_", safe)  # replace invalid chars with _
        safe = re.sub(r"_+", "_", safe)               # collapse consecutive underscores
        safe = safe.strip("_.-")                       # strip leading/trailing separators
        if not safe:
            safe = "default"
        return f"topic_{safe}"

    def _get_collection(self, topic: str):
        return self.client.get_or_create_collection(
            name=self._safe_name(topic),
            metadata={"topic": topic},
        )

    # ── Write ──────────────────────────────────────────────────────────────

    def save_chunks(self, chunks: list, topic: str) -> int:
        collection = self._get_collection(topic)
        existing   = set(collection.get()["ids"])
        new_chunks = [c for c in chunks if c["chunk_id"] not in existing]

        if not new_chunks:
            return 0

        collection.add(
            ids        = [c["chunk_id"] for c in new_chunks],
            embeddings = [c["embedding"] for c in new_chunks],
            documents  = [c["text"]      for c in new_chunks],
            metadatas  = [{
                "url":        c["url"],
                "title":      c["title"],
                "topic":      c["topic"],
                "scraped_at": c.get("scraped_at", ""),
                "version":    c.get("version", 1),
            } for c in new_chunks],
        )
        return len(new_chunks)

    # ── Read ───────────────────────────────────────────────────────────────

    def search(self, query_embedding: list, topic: str, top_k: int | None = None) -> list:
        top_k      = top_k or config.RAG_TOP_K
        collection = self._get_collection(topic)
        count      = collection.count()
        if count == 0:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1 / (1 + dist)
            if similarity >= config.RAG_MIN_SIMILARITY:
                out.append({
                    "text":       doc,
                    "url":        meta["url"],
                    "title":      meta["title"],
                    "similarity": round(similarity, 3),
                    "scraped_at": meta.get("scraped_at", ""),
                })
        return out

    def list_topics(self) -> list:
        return [c.metadata.get("topic", c.name) for c in self.client.list_collections()]

    def get_topic_stats(self, topic: str) -> dict:
        col   = self._get_collection(topic)
        count = col.count()
        last  = ""
        try:
            res = col.get(limit=1, include=["metadatas"])
            if res["metadatas"]:
                last = res["metadatas"][0].get("scraped_at", "")[:10]
        except Exception:
            pass
        return {
            "topic":           topic,
            "chunks":          count,
            "estimated_pages": max(1, count // 5),
            "last_scraped":    last,
        }

    def delete_topic(self, topic: str) -> bool:
        try:
            self.client.delete_collection(self._safe_name(topic))
            return True
        except Exception:
            return False
