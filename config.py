import os, json, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

_DEFAULTS = {
    "DATA_DIR":                os.path.join(BASE_DIR, "data"),
    "OLLAMA_BASE_URL":         "http://localhost:11434",
    "LLM_MODEL":               "llama3.2",
    "LLM_TEMPERATURE":         0.2,
    "LLM_MAX_TOKENS":          1024,
    "EMBEDDING_MODEL":         "all-MiniLM-L6-v2",
    "CRAWLER_MAX_PAGES":       150,
    "CRAWLER_MAX_DEPTH":       3,
    "CRAWLER_DELAY_SECONDS":   1.5,
    "CRAWLER_TIMEOUT_SECONDS": 10,
    "CHUNK_SIZE":              500,
    "CHUNK_OVERLAP":           50,
    "RAG_TOP_K":               5,
    "RAG_MIN_SIMILARITY":      0.3,
    "STORAGE_LIMIT_GB":        5,
    "SCHEDULES":               {},
}

CRAWLER_USER_AGENT = "LocalAILearner/2.0 (personal research bot)"
ALLOWED_DOMAINS_ALWAYS = [
    # General dev references
    "github.com", "developer.mozilla.org", "docs.python.org",
    "stackoverflow.com", "medium.com", "dev.to", "npmjs.com",
    "web.dev", "css-tricks.com", "javascript.info", "restfulapi.net",
    # Frontend
    "react.dev", "reactjs.org", "nextjs.org", "vitejs.dev",
    "vuejs.org", "svelte.dev", "kit.svelte.dev", "angular.dev",
    "tailwindcss.com", "typescriptlang.org",
    # Backend
    "expressjs.com", "fastapi.tiangolo.com", "docs.djangoproject.com",
    "flask.palletsprojects.com", "docs.nestjs.com",
    "www.django-rest-framework.org",
    # Databases
    "www.mongodb.com", "mongoosejs.com", "www.postgresql.org",
    "www.postgresqltutorial.com", "node-postgres.com",
    "www.prisma.io", "orm.drizzle.team", "redis.io",
    # Firebase
    "firebase.google.com",
    # Supabase
    "supabase.com",
    # Mobile
    "reactnative.dev", "reactnavigation.org", "docs.expo.dev",
    "docs.swmansion.com",
    # iOS / Apple
    "developer.apple.com", "docs.swift.org",
    # Android / Google Play
    "developer.android.com", "play.google.com",
    "support.google.com", "m3.material.io", "kotlinlang.org",
    # DevOps
    "docs.docker.com", "kubernetes.io", "docs.github.com",
    "docs.gitlab.com", "circleci.com", "nginx.org", "docs.nginx.com",
    "developer.hashicorp.com", "grafana.com", "prometheus.io",
    "aws.amazon.com", "docs.aws.amazon.com",
    "vercel.com", "linuxcommand.org", "www.gnu.org",
    # State / API
    "redux.js.org", "redux-toolkit.js.org",
    "zustand.docs.pmnd.rs", "graphql.org", "www.apollographql.com",
    "socket.io", "swagger.io",
]


def _load() -> dict:
    s = dict(_DEFAULTS)
    if os.path.exists(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE, encoding="utf-8") as f:
                s.update(json.load(f))
        except Exception:
            pass
    return s


def load_all() -> dict:
    return _load()


def save_all(settings: dict):
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    _apply(settings)


def save_setting(key: str, value):
    s = _load()
    s[key] = value
    save_all(s)


def _apply(s: dict):
    mod = sys.modules[__name__]
    for k, v in s.items():
        setattr(mod, k, v)
    # Derived paths
    data = s.get("DATA_DIR", _DEFAULTS["DATA_DIR"])
    mod.DATA_DIR = data
    mod.RAW_TEXT_DIR  = os.path.join(data, "raw_text")
    mod.VECTOR_DB_DIR = os.path.join(data, "vector_db")


# ── Module-level attribute exports (backward-compat) ──────────────────────
_cfg = _load()
DATA_DIR    = _cfg["DATA_DIR"]
RAW_TEXT_DIR  = os.path.join(DATA_DIR, "raw_text")
VECTOR_DB_DIR = os.path.join(DATA_DIR, "vector_db")

OLLAMA_BASE_URL         = _cfg["OLLAMA_BASE_URL"]
LLM_MODEL               = _cfg["LLM_MODEL"]
LLM_TEMPERATURE         = _cfg["LLM_TEMPERATURE"]
LLM_MAX_TOKENS          = _cfg["LLM_MAX_TOKENS"]
EMBEDDING_MODEL         = _cfg["EMBEDDING_MODEL"]
CRAWLER_MAX_PAGES       = _cfg["CRAWLER_MAX_PAGES"]
CRAWLER_MAX_DEPTH       = _cfg["CRAWLER_MAX_DEPTH"]
CRAWLER_DELAY_SECONDS   = _cfg["CRAWLER_DELAY_SECONDS"]
CRAWLER_TIMEOUT_SECONDS = _cfg["CRAWLER_TIMEOUT_SECONDS"]
CHUNK_SIZE              = _cfg["CHUNK_SIZE"]
CHUNK_OVERLAP           = _cfg["CHUNK_OVERLAP"]
RAG_TOP_K               = _cfg["RAG_TOP_K"]
RAG_MIN_SIMILARITY      = _cfg["RAG_MIN_SIMILARITY"]
STORAGE_LIMIT_GB        = _cfg["STORAGE_LIMIT_GB"]
SCHEDULES               = _cfg["SCHEDULES"]
