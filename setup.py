"""
setup.py — makes `myai` available as a global CLI command.

Install with:
    pip install -e .

After installing, run from any folder:
    myai ask "How does useState work?"
    myai learn react
    myai chat
"""
from setuptools import setup, find_packages

setup(
    name        = "my-ai-agent",
    version     = "2.0.0",
    description = "Personal local AI agent with RAG, global CLI, and PyQt6 GUI",
    author      = "FearCleevan",
    python_requires = ">=3.10",
    packages    = find_packages(exclude=["tests*", "data*"]),
    install_requires = [
        "requests",
        "beautifulsoup4",
        "lxml",
        "sentence-transformers",
        "chromadb",
        "tqdm",
        "PyQt6",
        "schedule",
        "pypdf",
        "pygments",
    ],
    entry_points = {
        "console_scripts": [
            "myai=cli.main:main",
        ],
    },
    classifiers = [
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
