import os

BASE = os.path.dirname(os.path.abspath(__file__))

files = {

"config.py": '''
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_TEXT_DIR = os.path.join(DATA_DIR, "raw_text")
VECTOR_DB_DIR = os.path.join(DATA_DIR, "vector_db")
OLLAMA_BASE_URL = "http://localhost:11434"
LLM_MODEL = "llama3.2"
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 1024
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CRAWLER_MAX_PAGES = 150
CRAWLER_MAX_DEPTH = 3
CRAWLER_DELAY_SECONDS = 1.5
CRAWLER_TIMEOUT_SECONDS = 10
CRAWLER_USER_AGENT = "LocalAILearner/1.0 (personal research bot)"
ALLOWED_DOMAINS_ALWAYS = [
    "github.com","developer.mozilla.org","docs.python.org",
    "stackoverflow.com","medium.com","dev.to","npmjs.com",
]
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
RAG_TOP_K = 5
RAG_MIN_SIMILARITY = 0.3
'''.strip(),

"crawler/__init__.py": "",

"crawler/seed_urls.py": '''
TOPIC_SEEDS = {
    "react": [
        "https://react.dev/learn",
        "https://react.dev/reference/react",
        "https://react.dev/reference/react-dom",
        "https://github.com/facebook/react",
    ],
    "python": [
        "https://docs.python.org/3/tutorial/",
        "https://docs.python.org/3/library/",
    ],
    "typescript": [
        "https://www.typescriptlang.org/docs/handbook/intro.html",
    ],
    "nodejs": [
        "https://nodejs.org/en/docs/",
    ],
    "docker": [
        "https://docs.docker.com/get-started/",
    ],
    "nextjs": [
        "https://nextjs.org/docs",
        "https://nextjs.org/learn",
    ],
    "fastapi": [
        "https://fastapi.tiangolo.com/tutorial/",
    ],
}

def get_seed_urls(topic: str) -> list:
    normalized = topic.lower().strip()
    normalized = normalized.replace(" js","").replace("react js","react").replace("react.js","react")
    if normalized in TOPIC_SEEDS:
        return TOPIC_SEEDS[normalized]
    for key, urls in TOPIC_SEEDS.items():
        if key in normalized:
            return urls
    return []
'''.strip(),

"crawler/agent.py": '''
import time, logging
from urllib.parse import urljoin, urlparse
from collections import deque
import requests
from bs4 import BeautifulSoup
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

log = logging.getLogger(__name__)

class CrawlerAgent:
    def __init__(self, topic, seed_urls, extra_allowed_domains=None):
        self.topic = topic
        self.seed_urls = seed_urls
        self.allowed_domains = set(config.ALLOWED_DOMAINS_ALWAYS)
        for url in seed_urls:
            self.allowed_domains.add(urlparse(url).netloc)
        if extra_allowed_domains:
            self.allowed_domains.update(extra_allowed_domains)
        self.visited = set()
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.CRAWLER_USER_AGENT

    def _is_allowed(self, url):
        try:
            domain = urlparse(url).netloc
            return any(domain == a or domain.endswith("." + a) for a in self.allowed_domains)
        except:
            return False

    def _fetch_page(self, url):
        try:
            r = self.session.get(url, timeout=config.CRAWLER_TIMEOUT_SECONDS, allow_redirects=True)
            if r.status_code == 200 and "text/html" in r.headers.get("Content-Type",""):
                return r.text
        except Exception as e:
            log.warning(f"Failed: {url} — {e}")
        return None

    def _extract_links(self, html, base_url):
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for tag in soup.find_all("a", href=True):
            href = urljoin(base_url, tag["href"]).split("#")[0].split("?")[0]
            if href.startswith("http") and self._is_allowed(href):
                links.append(href)
        return links

    def _extract_text(self, html, url):
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside","form","noscript","iframe"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title else url
        main = (soup.find("main") or soup.find("article") or
                soup.find(id="content") or soup.find(class_="content") or soup.find("body"))
        if not main:
            return None
        text = main.get_text(separator="\\n", strip=True)
        words = text.split()
        if len(words) < 100:
            return None
        return {"url": url, "title": title, "text": text, "word_count": len(words)}

    def crawl(self):
        queue = deque([(url, 0) for url in self.seed_urls])
        pages_crawled = 0
        print(f"  Starting crawl — up to {config.CRAWLER_MAX_PAGES} pages")
        while queue and pages_crawled < config.CRAWLER_MAX_PAGES:
            url, depth = queue.popleft()
            if url in self.visited:
                continue
            self.visited.add(url)
            html = self._fetch_page(url)
            if not html:
                continue
            page_data = self._extract_text(html, url)
            if page_data:
                pages_crawled += 1
                yield page_data
                if depth < config.CRAWLER_MAX_DEPTH:
                    for link in self._extract_links(html, url):
                        if link not in self.visited:
                            queue.append((link, depth + 1))
            time.sleep(config.CRAWLER_DELAY_SECONDS)
        print(f"  Crawl complete — {pages_crawled} pages collected")
'''.strip(),

"pipeline/__init__.py": "",

"pipeline/chunker.py": '''
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def chunk_text(text, url, title, topic):
    words = text.split()
    chunks, start, idx = [], 0, 0
    while start < len(words):
        chunk_words = words[start:start + config.CHUNK_SIZE]
        chunks.append({
            "text": " ".join(chunk_words),
            "url": url, "title": title, "topic": topic,
            "chunk_id": _url_to_id(url) + f"_{idx}",
        })
        idx += 1
        start += config.CHUNK_SIZE - config.CHUNK_OVERLAP
    return chunks

def _url_to_id(url):
    return url.replace("https://","").replace("http://","").replace("/","_").replace(".","_").replace("-","_")[:80]
'''.strip(),

"pipeline/embedder.py": '''
import logging
from sentence_transformers import SentenceTransformer
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

log = logging.getLogger(__name__)
_model = None

def get_model():
    global _model
    if _model is None:
        print("  Loading embedding model (first run downloads ~90MB)...")
        _model = SentenceTransformer(config.EMBEDDING_MODEL)
        print("  Embedding model ready.")
    return _model

def embed_chunks(chunks):
    model = get_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=32)
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks

def embed_query(query):
    return get_model().encode([query])[0].tolist()
'''.strip(),

"storage/__init__.py": "",

"storage/vector_store.py": '''
import logging, os
import chromadb
from chromadb.config import Settings
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

log = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        os.makedirs(config.VECTOR_DB_DIR, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=config.VECTOR_DB_DIR,
            settings=Settings(anonymized_telemetry=False)
        )

    def _get_collection(self, topic):
        safe = topic.lower().replace(" ","_").replace("-","_")
        return self.client.get_or_create_collection(name=f"topic_{safe}", metadata={"topic": topic})

    def save_chunks(self, chunks, topic):
        collection = self._get_collection(topic)
        existing = set(collection.get()["ids"])
        new = [c for c in chunks if c["chunk_id"] not in existing]
        if not new:
            return 0
        collection.add(
            ids=[c["chunk_id"] for c in new],
            embeddings=[c["embedding"] for c in new],
            documents=[c["text"] for c in new],
            metadatas=[{"url": c["url"], "title": c["title"], "topic": c["topic"]} for c in new]
        )
        return len(new)

    def search(self, query_embedding, topic, top_k=None):
        if top_k is None:
            top_k = config.RAG_TOP_K
        collection = self._get_collection(topic)
        count = collection.count()
        if count == 0:
            return []
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents","metadatas","distances"]
        )
        output = []
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            similarity = 1 / (1 + dist)
            if similarity >= config.RAG_MIN_SIMILARITY:
                output.append({"text": doc, "url": meta["url"], "title": meta["title"], "similarity": round(similarity,3)})
        return output

    def list_topics(self):
        return [c.metadata.get("topic", c.name) for c in self.client.list_collections()]

    def get_topic_stats(self, topic):
        count = self._get_collection(topic).count()
        return {"topic": topic, "chunks": count, "estimated_pages": max(1, count // 5)}
'''.strip(),

"query/__init__.py": "",

"query/rag.py": '''
import logging, requests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.embedder import embed_query
from storage.vector_store import VectorStore

log = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        self.vector_store = VectorStore()

    def _call_ollama(self, prompt):
        try:
            r = requests.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={"model": config.LLM_MODEL, "prompt": prompt, "stream": False,
                      "options": {"temperature": config.LLM_TEMPERATURE, "num_predict": config.LLM_MAX_TOKENS}},
                timeout=120
            )
            if r.status_code == 200:
                return r.json().get("response","").strip()
            return f"[LLM Error: HTTP {r.status_code}]"
        except requests.ConnectionError:
            return "[Error] Cannot connect to Ollama. Make sure it is running."

    def _build_prompt(self, question, chunks):
        if not chunks:
            return f"Answer this question:\\n\\nQuestion: {question}\\n\\nAnswer:"
        context = "\\n\\n---\\n\\n".join([f"Source: {c[\'title\']} ({c[\'url\']})\\n{c[\'text\']}" for c in chunks])
        return f"""You are a helpful technical assistant. Answer using ONLY the context below. Cite your sources.

=== CONTEXT ===
{context}
=== END CONTEXT ===

Question: {question}

Answer:"""

    def ask(self, question, topic):
        query_vector = embed_query(question)
        chunks = self.vector_store.search(query_vector, topic)
        answer = self._call_ollama(self._build_prompt(question, chunks))
        sources = list({c["url"] for c in chunks})
        return {"answer": answer, "sources": sources, "chunks_found": len(chunks)}

    def check_ollama(self):
        try:
            r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models",[])]
                return any(config.LLM_MODEL in m for m in models)
        except:
            pass
        return False
'''.strip(),

"main.py": '''
import os, sys, logging
logging.basicConfig(level=logging.WARNING)

import config
from crawler.agent import CrawlerAgent
from crawler.seed_urls import get_seed_urls
from pipeline.chunker import chunk_text
from pipeline.embedder import embed_chunks
from storage.vector_store import VectorStore
from query.rag import RAGEngine

HELP_TEXT = """
╔══════════════════════════════════════════════════════════╗
║           Local AI Learning Agent — Commands             ║
╠══════════════════════════════════════════════════════════╣
║  learn <topic>               Start learning a topic      ║
║  ask <topic> <question>      Ask about a learned topic   ║
║  topics                      List all learned topics     ║
║  stats <topic>               Show storage stats          ║
║  help                        Show this message           ║
║  exit                        Quit                        ║
╠══════════════════════════════════════════════════════════╣
║  Examples:                                               ║
║    learn React JS                                        ║
║    ask React JS What is useState?                        ║
╚══════════════════════════════════════════════════════════╝
"""

def ensure_dirs():
    for d in [config.DATA_DIR, config.RAW_TEXT_DIR, config.VECTOR_DB_DIR]:
        os.makedirs(d, exist_ok=True)

def save_raw(page, topic):
    d = os.path.join(config.RAW_TEXT_DIR, topic.replace(" ","_"))
    os.makedirs(d, exist_ok=True)
    name = page["url"].replace("https://","").replace("/","_")[:80] + ".txt"
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        f.write(f"URL: {page[\'url\']}\\nTITLE: {page[\'title\']}\\n\\n{page[\'text\']}")

def run_learning(topic):
    print(f"\\n🌐 Learning: \\'{topic}\\'")
    seed_urls = get_seed_urls(topic)
    if not seed_urls:
        print(f"No pre-configured URLs for \\'{topic}\\'. Enter URLs (empty line to finish):")
        while True:
            url = input("  URL: ").strip()
            if not url: break
            seed_urls.append(url)
    if not seed_urls:
        print("No URLs provided.")
        return

    vector_store = VectorStore()
    crawler = CrawlerAgent(topic=topic, seed_urls=seed_urls)
    total_chunks, total_pages = 0, 0

    for page in crawler.crawl():
        total_pages += 1
        print(f"  ✓ [{total_pages}] {page[\'title\'][:55]}... ({page[\'word_count\']} words)")
        save_raw(page, topic)
        chunks = chunk_text(page["text"], page["url"], page["title"], topic)
        chunks = embed_chunks(chunks)
        total_chunks += vector_store.save_chunks(chunks, topic)

    print(f"\\n✅ Done! {total_pages} pages, {total_chunks} chunks saved.")
    print(f"   Now try: ask {topic} <your question>\\n")

def run_query(topic, question):
    rag = RAGEngine()
    if not rag.check_ollama():
        print(f"\\n❌ Ollama not running or model \\'{config.LLM_MODEL}\\' missing.")
        print(f"   Run: ollama pull {config.LLM_MODEL}")
        return
    print(f"\\n🔍 Searching knowledge base...")
    result = rag.ask(question, topic)
    print(f"\\n{\'─\'*60}")
    print(f"💬 Answer:\\n")
    print(result["answer"])
    if result["sources"]:
        print(f"\\n📚 Sources:")
        for s in result["sources"]:
            print(f"   • {s}")
    print(f"{\'─\'*60}\\n")

def main():
    ensure_dirs()
    print(HELP_TEXT)
    vector_store = VectorStore()
    while True:
        try:
            raw = input("agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\\nGoodbye!")
            break
        if not raw: continue
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("exit","quit","q"):
            print("Goodbye!"); break
        elif cmd == "help":
            print(HELP_TEXT)
        elif cmd == "topics":
            topics = vector_store.list_topics()
            if topics:
                print("\\n📚 Learned topics:")
                for t in topics:
                    s = vector_store.get_topic_stats(t)
                    print(f"   • {t} — {s[\'chunks\']} chunks (~{s[\'estimated_pages\']} pages)")
            else:
                print("  No topics yet. Use: learn <topic>")
            print()
        elif cmd == "stats":
            if not args: print("Usage: stats <topic>"); continue
            s = vector_store.get_topic_stats(args)
            print(f"\\n📊 {args}: {s[\'chunks\']} chunks, ~{s[\'estimated_pages\']} pages\\n")
        elif cmd == "learn":
            if not args: print("Usage: learn <topic>"); continue
            run_learning(args)
        elif cmd == "ask":
            if not args: print("Usage: ask <topic> <question>"); continue
            known = vector_store.list_topics()
            matched, question = None, args
            for t in sorted(known, key=len, reverse=True):
                if args.lower().startswith(t.lower()):
                    matched = t
                    question = args[len(t):].strip()
                    break
            if not matched:
                sub = args.split(maxsplit=1)
                matched = sub[0]
                question = sub[1] if len(sub) > 1 else ""
            if not question: print("Please include a question."); continue
            run_query(matched, question)
        else:
            print(f"Unknown command: \\'{cmd}\\'. Type \\'help\\'.")

if __name__ == "__main__":
    main()
'''.strip(),

"requirements.txt": """requests
beautifulsoup4
lxml
sentence-transformers
chromadb
tqdm""".strip(),

}

print("Creating project files...")
for filepath, content in files.items():
    full_path = os.path.join(BASE, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ {filepath}")

print("\n✅ All files created! Now run: python main.py")
