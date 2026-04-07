# My AI Assistant

> **Your personal, fully local AI coding assistant** — powered by Ollama, ChromaDB, and your own knowledge base. No subscriptions, no cloud, no data leaving your machine.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Interfaces](#interfaces)
  - [Desktop GUI](#-desktop-gui)
  - [CLI](#-command-line-interface-cli)
  - [TUI](#-terminal-ui-tui)
  - [VS Code Extension](#-vs-code-extension)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Learning Topics](#learning-topics)
- [Project Indexing](#project-indexing)
- [VS Code Extension Setup](#vs-code-extension-setup)
- [Configuration](#configuration)
- [Supported Topics](#supported-topics)
- [Tech Stack](#tech-stack)

---

## Overview

My AI Assistant is a multi-interface AI system that lets you build, query, and manage your own private knowledge base of technical documentation. You crawl official docs, index your own codebases, and then chat with an AI that has direct access to everything you've taught it — all running locally on your hardware.

```
┌──────────────────────────────────────────────────────────────────┐
│                        My AI Assistant                           │
│                                                                  │
│   Desktop GUI  ·  CLI  ·  TUI  ·  VS Code Extension            │
│                         │                                        │
│                   FastAPI Server (:8765)                         │
│                         │                                        │
│          ┌──────────────┴──────────────┐                        │
│     RAG Engine                    ChromaDB                       │
│     (Ollama LLM)              (Vector Store)                     │
│          │                            │                          │
│     Sentence                    Web Crawler                      │
│   Transformers                 + Project Indexer                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Architecture

| Layer | Component | Description |
|---|---|---|
| **LLM** | Ollama | Local inference — llama3.2, mistral, codellama, gemma2, etc. |
| **Embeddings** | sentence-transformers | `all-MiniLM-L6-v2` converts text to vectors |
| **Vector DB** | ChromaDB | Persistent local vector store for semantic search |
| **Crawler** | `crawler/agent.py` | Web scraper with 69+ pre-seeded topic URLs |
| **Pipeline** | `pipeline/` | Chunker (500 tokens, 50 overlap) + Embedder |
| **RAG** | `query/rag.py` | Retrieval-Augmented Generation — finds relevant chunks, builds prompt, calls Ollama |
| **API** | `api/server.py` | FastAPI with SSE streaming — used by VS Code extension |
| **GUI** | `gui/app.py` | PyQt6 desktop app |
| **CLI** | `cli/main.py` | `myai` command installed globally via pip |
| **TUI** | `tui/app.py` | Textual terminal UI |

---

## Features

### Core AI
- **RAG-powered answers** — responses grounded in your private knowledge base, not just the model's training data
- **Streaming responses** — tokens stream live in all interfaces
- **Multi-turn chat** — full conversation history maintained per session
- **Source citations** — every answer cites the documents it used
- **Code blocks with Copy** — AI-generated code rendered with syntax highlighting and one-click copy

### Knowledge Base
- **Web crawling** — scrapes official documentation from 69+ pre-seeded topics
- **Custom URLs** — crawl any website by providing your own seed URLs
- **PDF / text file ingestion** — learn from local `.pdf` and `.txt` files
- **Storage management** — configurable size limit with live storage monitor
- **Scheduled learning** — auto-crawl topics on a cron-like schedule

### Project Indexing
- **Full codebase indexing** — scan any local folder into ChromaDB
- **Framework auto-detection** — detects React, Next.js, Laravel, Django, FastAPI, Vue, Angular, Rust, Go, and more
- **`.gitignore` aware** — respects your ignore rules during scanning
- **Project-aware chat** — the AI automatically loads the right project context when you ask about it

### VS Code Extension
- **Sidebar chat panel** — always accessible from the Activity Bar (like Copilot/Claude Code)
- **`@` file picker** — type `@` in the chat input to attach any workspace file as context
- **AI file proposals** — AI can create or edit files; shows Accept / View Diff / Reject per file
- **Native VS Code diff** — proposed changes open in VS Code's built-in diff viewer
- **Right-click code commands** — Explain, Fix, Generate Tests, Refactor, Ask about file
- **Auto file context** — your active editor file is silently attached to every message
- **Project auto-detection** — matches open workspace to indexed projects automatically
- **Auto-reconnect** — retries the backend every 15 s; manual Retry button also available

---

## Interfaces

### 🖥️ Desktop GUI

Launch with:
```bash
python main.py
```

**Tabs:**

| Tab | What it does |
|---|---|
| **Learn** | Enter a topic name → crawls official docs or your own URLs → stores in ChromaDB |
| **Chat** | Multi-turn streaming chat with your knowledge base |
| **Ask** | Single-turn RAG question with numbered source citations |
| **Projects** | Scan & index a local codebase folder; manage indexed projects |
| **Topics** | Browse all stored topics with chunk counts and stats |
| **Schedule** | Set up recurring learning jobs (daily/hourly/weekly) |
| **Settings** | Configure model, storage path, chunk size, crawler limits |

---

### ⌨️ Command Line Interface (CLI)

Install the `myai` command globally:
```bash
pip install -e .
```

**Commands:**

```bash
# Ask a single question
myai ask "What is React's useEffect hook?"
myai ask "How do I handle errors in FastAPI?" --topic fastapi

# Ask with a file for context
myai ask "What does this file do?" --file ./src/app.py

# Learn a topic (crawl official docs)
myai learn react
myai learn "React Native + Expo"
myai learn --folder ./my-project        # index a codebase
myai learn --file ./notes.pdf           # ingest a local file
myai learn --url https://example.com/docs

# Start an interactive chat session
myai chat
myai chat --topic nextjs

# List all learned topics
myai topics

# List available Ollama models
myai models

# Start the API server (used by VS Code extension)
myai serve
myai serve --port 9000
```

---

### 🖥️ Terminal UI (TUI)

A keyboard-driven interface that runs in any terminal:
```bash
python -m tui.app
```

Navigate between tabs with arrow keys. No mouse needed — ideal for SSH sessions or minimal environments.

---

### 🧩 VS Code Extension

A full sidebar chat panel that lives in the Activity Bar, identical in feel to GitHub Copilot or Claude Code.

See [VS Code Extension Setup](#vs-code-extension-setup) for installation.

**How to use the `@` file picker:**
1. Type `@` in the chat input
2. A fuzzy-search popup appears above the input with all workspace files
3. Use `↑` `↓` to navigate, `Enter` or click to attach, `Esc` to cancel
4. Multiple files can be attached — each shown as a chip with a `✕` to remove
5. Hit **Send** — all attached file contents are included in context

**How AI file proposals work:**
1. Attach a file (`@`) and ask the AI to modify it
2. The AI responds with changes wrapped in `<file_write path="...">` blocks
3. A proposal card appears with:
   - File path + NEW FILE / EDIT badge
   - 15-line code preview
   - **✓ Accept** — writes the file to disk and opens it
   - **⊟ View Diff** — opens VS Code's native diff (current ↔ proposed)
   - **✕ Reject** — dismisses the proposal

---

## Installation

### Prerequisites

| Requirement | How to get it |
|---|---|
| **Python 3.10+** | [python.org](https://python.org) |
| **Ollama** | [ollama.com](https://ollama.com) — then `ollama pull llama3.2` |
| **Node.js 18+** | Only needed to rebuild the VS Code extension from source |

### Python dependencies

```bash
git clone https://github.com/FearCleevan/My-AI-Assistant.git
cd My-AI-Assistant
pip install -r requirements.txt
pip install -e .          # installs the `myai` CLI globally
```

`requirements.txt` includes:
```
requests, beautifulsoup4, lxml
sentence-transformers, chromadb
PyQt6, schedule, pypdf
pygments, pathspec
fastapi, uvicorn[standard]
```

---

## Quick Start

**1. Start Ollama**
```bash
ollama serve
ollama pull llama3.2
```

**2. Learn your first topic**
```bash
myai learn react
# or launch the GUI and use the Learn tab
python main.py
```

**3. Ask a question**
```bash
myai ask "How do I use useState in React?"
```

**4. Start the VS Code backend** (in a separate terminal)
```bash
myai serve
```

**5. Open VS Code** → install the `.vsix` → click the chat icon in the Activity Bar.

---

## Learning Topics

The Learn system accepts:

| Input type | Example |
|---|---|
| Topic name (auto-seeded) | `react`, `laravel`, `mysql`, `typescript` |
| Natural language | `"Learn everything about React Native + Expo"` |
| Any alias | `"bash scripting"`, `"next auth"`, `"shadcn ui"` |
| Local folder | `--folder ./my-project` |
| Local file | `--file ./notes.pdf` |
| Custom URL | `--url https://docs.example.com` |

The crawler:
- Follows links up to depth 3 (configurable)
- Respects `robots.txt` and crawl delays
- Deduplicates pages across sessions
- Chunks text into 500-token segments with 50-token overlap
- Embeds each chunk using `all-MiniLM-L6-v2`
- Stores everything in ChromaDB under the topic name

---

## Project Indexing

Index a codebase for project-aware chat:

**Via GUI** (Projects tab):
1. Enter the folder path or click **Browse**
2. Click **Index Project**
3. Progress bar shows file-by-file status
4. When done, the project appears in the table

**Via CLI:**
```bash
myai learn --folder ./my-react-app
```

**What gets indexed:**
- 40+ file extensions: `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.php`, `.go`, `.rs`, `.java`, `.vue`, `.svelte`, `.html`, `.css`, `.json`, `.md`, and more
- Skips: `node_modules`, `.git`, `dist`, `build`, `.next`, `.venv`, `vendor`, files > 500 KB
- Respects `.gitignore`

**Auto-detection** reads `package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, `pom.xml` to identify framework and language.

---

## VS Code Extension Setup

### Install from VSIX

1. Open VS Code → **Extensions** panel → `···` menu → **Install from VSIX...**
2. Select `vscode-extension/myai-assistant-1.1.0.vsix`
3. Reload VS Code when prompted

### Start the backend

```bash
myai serve          # default port 8765
myai serve --port 9000
```

### Open the chat panel

- Click the **My AI Assistant** icon in the Activity Bar
- Or press `Ctrl+Shift+A` / `Cmd+Shift+A`

### Settings

In VS Code Settings (`Ctrl+,`), search for **My AI**:

| Setting | Default | Description |
|---|---|---|
| `myai.serverPort` | `8765` | Port where `myai serve` is running |
| `myai.defaultTopic` | *(blank)* | Knowledge-base topic (blank = auto-detect from project) |

### Right-click commands

Select code in any file → right-click → **My AI Assistant**:

| Command | What it does |
|---|---|
| Explain this | Step-by-step explanation of the selected code |
| Fix this | Identifies bugs and shows corrected version |
| Generate tests | Writes unit tests covering edge cases |
| Refactor this | Cleans up the code with explanations |
| Ask about this file | Summarises the purpose and structure of the open file |

---

## Configuration

All settings are stored in `settings.json` (auto-created on first run).

| Setting | Default | Description |
|---|---|---|
| `DATA_DIR` | `./data` | Where ChromaDB and raw text are stored |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `LLM_MODEL` | `llama3.2` | Ollama model to use |
| `LLM_TEMPERATURE` | `0.2` | Response creativity (0 = deterministic) |
| `LLM_MAX_TOKENS` | `1024` | Max tokens per response |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model for embeddings |
| `CRAWLER_MAX_PAGES` | `150` | Max pages to crawl per topic |
| `CRAWLER_MAX_DEPTH` | `3` | Link-following depth |
| `CRAWLER_DELAY_SECONDS` | `1.5` | Polite delay between requests |
| `CHUNK_SIZE` | `500` | Tokens per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between consecutive chunks |
| `RAG_TOP_K` | `5` | Number of chunks retrieved per query |
| `RAG_MIN_SIMILARITY` | `0.3` | Minimum cosine similarity threshold |
| `STORAGE_LIMIT_GB` | `5` | Storage warning threshold |

---

## Supported Topics

69 pre-seeded topics with official documentation URLs. A topic can be referenced by name or any of its aliases (e.g. `"bash scripting"` → `linux`, `"next auth"` → `nextauth`).

**Frontend**
`react` · `nextjs` · `typescript` · `javascript` · `vue` · `angular` · `svelte` · `tailwind` · `css` · `html`

**Mobile**
`react native` · `expo` · `ios` · `android` · `swift` · `kotlin`

**Backend**
`nodejs` · `express` · `fastapi` · `django` · `flask` · `nestjs` · `php` · `laravel`

**Databases**
`mongodb` · `postgresql` · `mysql` · `sqlite` · `redis` · `prisma` · `drizzle` · `supabase` · `firebase`

**DevOps & Cloud**
`docker` · `kubernetes` · `github actions` · `nginx` · `aws` · `terraform` · `grafana` · `cloudflare`

**Languages**
`python` · `go` · `rust` · `java` · `c#`

**Testing**
`testing` · `jest` · `vitest` · `cypress` · `playwright`

**Meta-frameworks & Runtimes**
`astro` · `remix` · `hono` · `bun` · `deno`

**Auth & Payments**
`nextauth` · `stripe`

**Validation & Forms**
`zod` · `react hook form`

**UI Libraries**
`shadcn` · `radix ui` · `react native paper`

**Tools**
`git` · `linux` · `electron` · `threejs` · `graphql` · `redux` · `zustand`

---

## Tech Stack

| Component | Technology |
|---|---|
| LLM inference | [Ollama](https://ollama.com) |
| Embeddings | [sentence-transformers](https://www.sbert.net/) — all-MiniLM-L6-v2 |
| Vector database | [ChromaDB](https://www.trychroma.com/) |
| Web crawling | requests + BeautifulSoup4 |
| PDF parsing | pypdf |
| Desktop UI | PyQt6 |
| Terminal UI | Textual |
| API server | FastAPI + uvicorn (SSE streaming) |
| CLI | argparse (`pip install -e .`) |
| VS Code extension | TypeScript + VS Code Webview API |
| Syntax highlighting | Pygments (Monokai theme) |
| Scheduling | schedule library |

---

## Project Structure

```
my_ai_mark_1/
├── api/                  # FastAPI server (myai serve)
│   └── server.py
├── cli/                  # myai CLI command
│   └── main.py
├── core/                 # Scheduler, storage monitor, NLP parser
├── crawler/              # Web scraper + 69 seed URL topics
│   ├── agent.py
│   └── seed_urls.py
├── gui/                  # PyQt6 desktop app
│   └── app.py
├── indexer/              # Codebase scanner + project indexer
├── pipeline/             # Text chunker + sentence-transformer embedder
├── query/                # RAG engine — retrieval + Ollama chat
│   └── rag.py
├── storage/              # ChromaDB vector store wrapper
├── tui/                  # Textual terminal UI
├── vscode-extension/     # VS Code extension (TypeScript)
│   ├── src/
│   ├── media/
│   └── myai-assistant-1.1.0.vsix
├── config.py             # All settings with settings.json persistence
├── main.py               # Desktop GUI entry point
├── requirements.txt
└── setup.py              # pip install -e . entry point
```

---

*Built with [Ollama](https://ollama.com) · [ChromaDB](https://www.trychroma.com/) · [sentence-transformers](https://www.sbert.net/) · [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) · [FastAPI](https://fastapi.tiangolo.com/)*
