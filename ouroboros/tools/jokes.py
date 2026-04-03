"""Jokes tool — simple random joke generator.

Tools module exports get_tools() → List[ToolEntry].
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ouroboros.utils import safe_relpath


@dataclass
class Joke:
    """Single joke entry."""

    text: str
    category: str
    added_at: str


JOKES_DB_PATH = "tools/jokes.txt"


def load_jokes() -> List[Joke]:
    """Load jokes from Drive, parse as TSV: text<tab>category<tab>timestamp."""
    # In tool context, repo_dir and drive_root are available
    try:
        # Import here to avoid circular dependency
        from ouroboros.tools.registry import ToolContext

        ctx = ToolContext.__dataclass_fields__["repo_dir"].default  # type: ignore[attr-defined]
        drive_root = ToolContext.__dataclass_fields__["drive_root"].default  # type: ignore[attr-defined]

        drive_path = (drive_root / safe_relpath(JOKES_DB_PATH)).resolve()
        if not drive_path.exists():
            return []

        with open(drive_path, "r", encoding="utf-8") as f:
            jokes = []
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t", 2)
                if len(parts) >= 2:
                    text = parts[0].strip()
                    category = parts[1].strip()
                    added_at = parts[2].strip() if len(parts) >= 3 else datetime.now.isoformat()
                    jokes.append(Joke(text=text, category=category, added_at=added_at))
            return jokes
    except Exception:
        return []


def save_jokes(jokes: List[Joke]) -> None:
    """Save jokes list to Drive (TSV format)."""
    try:
        from ouroboros.tools.registry import ToolContext

        ctx = ToolContext.__dataclass_fields__["repo_dir"].default  # type: ignore[attr-defined]
        drive_root = ToolContext.__dataclass_fields__["drive_root"].default  # type: ignore[attr-defined]

        drive_path = (drive_root / safe_relpath(JOKES_DB_PATH)).resolve()
        drive_path.parent.mkdir(parents=True, exist_ok=True)

        with open(drive_path, "w", encoding="utf-8") as f:
            for joke in jokes:
                f.write(f"{joke.text}\t{joke.category}\t{joke.added_at}\n")
    except Exception:
        pass  # Silently fail — early tool, not abort


def add_joke(text: str, category: str = "general") -> Joke:
    """Add a new joke to the database."""
    jokes = load_jokes()
    joke = Joke(text=text, category=category, added_at=datetime.now().isoformat())
    jokes.append(joke)
    save_jokes(jokes)
    return joke


def get_joke(category: Optional[str] = None) -> Dict[str, Any]:
    """Return a random joke.

    Args:
        category: Optional filter by category ("work", "tech", "programming", "general").

    Returns:
        Dict with keys: "joke" (text), "category" (str), "count" (int).
    """
    jokes = load_jokes()
    if not jokes:
        return {
            "joke": "Нет анекдотов в базе :( Добавь свой через bot.",
            "category": "general",
            "count": 0,
        }

    if category:
        filtered = [j for j in jokes if j.category.lower() == category.lower()]
    else:
        filtered = jokes

    if not filtered:
        return {
            "joke": f"Анекдоты с категорией '{category}' не найдены.",
            "category": category or "general",
            "count": 0,
        }

    joke = random.choice(filtered)
    return {"joke": joke.text, "category": joke.category, "count": len(filtered)}


def get_tools() -> List[Dict[str, Any]]:
    """Export tool descriptors for ToolRegistry."""

    schema = {
        "type": "function",
        "function": {
            "name": "/joke",
            "description": "Get a random joke. Optional category: 'work', 'tech', 'programming', 'general'",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["work", "tech", "programming", "general"],
                        "description": "Category filter (optional)",
                    }
                },
                "additionalProperties": False,
            },
        },
    }

    def handler(ctx: Any, **kwargs) -> str:
        category_arg = kwargs.get("category")
        results = get_joke(category=category_arg)
        return f'[Joke tool result]{results["joke"]} (Category: {results["category"]})'

    return [{"name": "/joke", "schema": schema, "handler": handler}]