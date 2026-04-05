"""
Project file scanner — recursively finds all indexable source files.
Respects .gitignore (via pathspec if installed) and skips noise directories.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Iterator

# ── Directories always skipped ────────────────────────────────────────────────
_SKIP_DIRS = frozenset({
    "node_modules", "__pycache__", ".git", ".svn", ".hg",
    ".venv", "venv", "env", ".env",
    "dist", "build", ".next", ".nuxt", ".output", "out",
    "coverage", ".coverage", ".cache", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox",
    "target",           # Rust / Java / Maven
    "vendor",           # Go / PHP
    ".idea", ".vscode",
    "eggs", ".eggs",
    "storybook-static", ".storybook",
    "tmp", "temp", "logs",
})

# ── File extensions that get indexed ─────────────────────────────────────────
INDEXABLE_EXTS = frozenset({
    # Python
    ".py", ".pyi",
    # JavaScript / TypeScript
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # Web
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    # Config / data
    ".json", ".yaml", ".yml", ".toml",
    # Docs
    ".md", ".mdx", ".txt", ".rst",
    # Shell / SQL
    ".sh", ".bash", ".zsh", ".sql",
    # Systems languages
    ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    # JVM
    ".java", ".kt", ".scala",
    # Mobile
    ".swift", ".dart",
    # Other
    ".rb", ".php",
    ".vue", ".svelte",
    ".graphql", ".gql",
    ".prisma",
    ".dockerfile",
})

_MAX_FILE_BYTES = 500_000   # skip files larger than 500 KB (generated, minified)

_EXT_TO_LANG: dict[str, str] = {
    ".py": "Python",     ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".html": "HTML",     ".htm": "HTML",
    ".css": "CSS",       ".scss": "CSS",
    ".sass": "CSS",      ".less": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",     ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",   ".mdx": "Markdown",
    ".txt": "Text",      ".rst": "reStructuredText",
    ".sh": "Shell",      ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",           ".cpp": "C++",
    ".h": "C/C++",       ".hpp": "C++",
    ".java": "Java",     ".kt": "Kotlin", ".scala": "Scala",
    ".swift": "Swift",   ".dart": "Dart",
    ".rb": "Ruby",       ".php": "PHP",
    ".vue": "Vue",       ".svelte": "Svelte",
    ".graphql": "GraphQL", ".gql": "GraphQL",
    ".prisma": "Prisma",
    ".dockerfile": "Dockerfile",
}


def _ext_to_language(ext: str) -> str:
    return _EXT_TO_LANG.get(ext, "Text")


def _load_gitignore(root: Path):
    """Return a pathspec.PathSpec for root/.gitignore, or None."""
    gi = root / ".gitignore"
    if not gi.exists():
        return None
    try:
        import pathspec
        return pathspec.PathSpec.from_lines(
            "gitwildmatch",
            gi.read_text(encoding="utf-8", errors="replace").splitlines(),
        )
    except ImportError:
        return None
    except Exception:
        return None


def scan_project(root: str) -> Iterator[dict]:
    """
    Yield a dict for every indexable source file under root:
      {path, rel_path, ext, size_bytes, language}
    """
    root_path = Path(root).resolve()
    gitignore  = _load_gitignore(root_path)

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune dirs in-place so os.walk doesn't recurse into them
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            ext   = fpath.suffix.lower()

            # Also allow files named exactly "Dockerfile", "Makefile", etc.
            if ext not in INDEXABLE_EXTS and fname.lower() not in ("dockerfile", "makefile", ".env.example"):
                continue

            try:
                rel  = fpath.relative_to(root_path)
                size = fpath.stat().st_size
            except Exception:
                continue

            if size == 0 or size > _MAX_FILE_BYTES:
                continue

            # Check .gitignore
            if gitignore and gitignore.match_file(str(rel)):
                continue

            yield {
                "path":       str(fpath),
                "rel_path":   str(rel),
                "ext":        ext,
                "size_bytes": size,
                "language":   _ext_to_language(ext),
            }


def detect_project_type(root: str) -> dict:
    """
    Inspect manifest files and return project metadata:
      {name, root, framework, language, entry_points, description}
    """
    root_path = Path(root).resolve()
    info: dict = {
        "name":         root_path.name,
        "root":         str(root_path),
        "framework":    "—",
        "language":     "—",
        "entry_points": [],
        "description":  "",
    }

    # ── package.json (Node / JS / TS) ─────────────────────────────────────
    pkg = root_path / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
            info["language"]    = "JavaScript / TypeScript"
            info["description"] = data.get("description", "")
            deps = {
                **data.get("dependencies",    {}),
                **data.get("devDependencies", {}),
            }
            if "next" in deps:
                info["framework"] = "Next.js"
            elif "react" in deps or "react-dom" in deps:
                info["framework"] = "React"
            elif "vue" in deps or "@vue/core" in deps:
                info["framework"] = "Vue"
            elif "svelte" in deps:
                info["framework"] = "Svelte"
            elif "@angular/core" in deps:
                info["framework"] = "Angular"
            elif "express" in deps:
                info["framework"] = "Express"
            elif "fastify" in deps:
                info["framework"] = "Fastify"
            elif "nestjs" in deps or "@nestjs/core" in deps:
                info["framework"] = "NestJS"
            elif "expo" in deps:
                info["framework"] = "Expo"
            elif "react-native" in deps:
                info["framework"] = "React Native"
            if main := data.get("main", ""):
                info["entry_points"].append(main)
            for s in ["dev", "start", "build"]:
                if s in data.get("scripts", {}):
                    info["entry_points"].append(f"npm run {s}")
        except Exception:
            pass

    # ── Python manifests ──────────────────────────────────────────────────
    _py_markers = (
        root_path / "requirements.txt",
        root_path / "pyproject.toml",
        root_path / "setup.py",
        root_path / "setup.cfg",
    )
    if any(p.exists() for p in _py_markers):
        info["language"] = "Python"
        if (root_path / "manage.py").exists():
            info["framework"] = "Django"
            info["entry_points"].append("manage.py")
        else:
            for candidate in ("main.py", "app.py", "run.py", "server.py"):
                if (root_path / candidate).exists():
                    info["entry_points"].append(candidate)
                    break
            try:
                req_text = ""
                for rfile in ("requirements.txt", "pyproject.toml"):
                    rp = root_path / rfile
                    if rp.exists():
                        req_text += rp.read_text(encoding="utf-8", errors="replace").lower()
                if "fastapi" in req_text:
                    info["framework"] = "FastAPI"
                elif "flask" in req_text:
                    info["framework"] = "Flask"
                elif "django" in req_text:
                    info["framework"] = "Django"
            except Exception:
                pass

    # ── Rust ─────────────────────────────────────────────────────────────
    if (root_path / "Cargo.toml").exists():
        info["language"]  = "Rust"
        info["framework"] = "Cargo"
        if (root_path / "src" / "main.rs").exists():
            info["entry_points"].append("src/main.rs")

    # ── Go ────────────────────────────────────────────────────────────────
    if (root_path / "go.mod").exists():
        info["language"] = "Go"
        for candidate in ("main.go", "cmd/main.go"):
            if (root_path / candidate).exists():
                info["entry_points"].append(candidate)
                break

    # ── Java / Kotlin ────────────────────────────────────────────────────
    if (root_path / "pom.xml").exists() or (root_path / "build.gradle").exists():
        info["language"]  = "Java / Kotlin"
        info["framework"] = "Maven/Gradle"

    return info
