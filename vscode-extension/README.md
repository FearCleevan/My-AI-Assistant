# My AI Assistant

**Your personal local AI assistant — powered by Ollama and your own knowledge base.**

No subscriptions. No cloud. Everything runs on your machine.

---

## Features

### 💬 Persistent Sidebar Chat
Chat with your AI directly from the Activity Bar — always one click away, just like GitHub Copilot or Claude Code. Conversations persist while VS Code is open.

### ⚡ Streaming Responses
Responses stream token-by-token in real time so you never wait for a full reply before reading.

### 📋 Code Blocks with Copy Button
AI responses automatically render fenced code blocks with syntax highlighting and a **Copy code** button — identical to ChatGPT / Claude.

### 📂 Automatic File Context
The active file in your editor is silently attached to every message. Ask "what does this function do?" without pasting anything — the AI already sees your code.

### 🗂️ Project-Aware Chat
Index an entire codebase with `myai learn --folder ./my-project`. The extension auto-detects indexed projects and switches context automatically when you open that workspace.

### 🔍 Right-Click Code Commands
Select any code → right-click → **My AI Assistant**:

| Command | What it does |
|---|---|
| **Explain this** | Step-by-step explanation of the selected code |
| **Fix this** | Finds bugs and shows the corrected version |
| **Generate tests** | Writes unit tests covering edge cases |
| **Refactor this** | Cleans up the code with explanations |
| **Ask about this file** | Summarises the purpose and structure of the open file |

### 🔒 100% Local & Private
- Uses **Ollama** for LLM inference (llama3.2, mistral, codellama, etc.)
- Uses **ChromaDB** + **sentence-transformers** for vector search
- No data ever leaves your machine

---

## Requirements

| Requirement | Notes |
|---|---|
| **Ollama** | Install from [ollama.com](https://ollama.com) — run `ollama pull llama3.2` |
| **Python 3.10+** | With the `my_ai_mark_1` project installed |
| **myai backend** | Run `myai serve` in a terminal before using the extension |

---

## Getting Started

**1. Start Ollama**
```bash
ollama serve
```

**2. Start the AI backend**
```bash
cd path/to/my_ai_mark_1
myai serve
```

**3. Open the chat panel**

Click the **My AI Assistant** icon in the Activity Bar (left sidebar), or press `Ctrl+Shift+A`.

---

## Extension Commands

| Command | Shortcut | Description |
|---|---|---|
| `My AI: Open Chat` | `Ctrl+Shift+A` | Focus the sidebar chat panel |
| `My AI: Explain this` | Right-click menu | Explain selected code |
| `My AI: Fix this` | Right-click menu | Fix bugs in selected code |
| `My AI: Generate tests` | Right-click menu | Write unit tests for selected code |
| `My AI: Refactor this` | Right-click menu | Refactor selected code |
| `My AI: Ask about this file` | Right-click menu | Summarise the open file |

---

## Settings

| Setting | Default | Description |
|---|---|---|
| `myai.serverPort` | `8765` | Port where `myai serve` is running |
| `myai.defaultTopic` | *(blank)* | Knowledge-base topic to use (blank = auto-detect) |

---

## Using Topics & Projects

**Learn from a document:**
```bash
myai learn path/to/notes.pdf --topic python-notes
```

**Index an entire codebase:**
```bash
myai learn --folder ./my-project
```

Then in the chat panel, type the topic name in the **Topic** field, or let the extension auto-detect it from your workspace.

---

## Architecture

```
VS Code Extension  ──HTTP/SSE──►  myai serve (FastAPI :8765)
                                        │
                              ┌─────────┴─────────┐
                         RAG Engine          ChromaDB
                         (Ollama)        (vector store)
```

---

## Troubleshooting

**Red dot / "Backend not running"**
→ Run `myai serve` in a terminal. Make sure Ollama is also running.

**"Ollama not running"**
→ Run `ollama serve`, then restart `myai serve`.

**Responses are empty**
→ Check that Ollama has a model: `ollama list`. Pull one: `ollama pull llama3.2`.

**Port conflict**
→ Change the port in Settings → `myai.serverPort`, and start the server with `myai serve --port <new-port>`.

---

## Tech Stack

- **LLM**: Ollama (llama3.2, mistral, codellama, gemma2, …)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Vector DB**: ChromaDB
- **Backend**: FastAPI + uvicorn (SSE streaming)
- **Extension**: TypeScript + VS Code Webview API
