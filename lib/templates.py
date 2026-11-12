"""
Template rendering for Tri-Agent Orchestrator.

Templates live in the repository's ``templates/`` directory and are the single
source of truth for the document formats that SKILL.md describes. Placeholders
use ``{{KEY}}`` syntax and are substituted literally (no str.format), so braces
inside user-supplied values are safe.
"""

import re
from pathlib import Path
from typing import Dict

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def render_template(name: str, values: Dict[str, str], templates_dir: Path = TEMPLATES_DIR) -> str:
    """Load ``templates/<name>`` and substitute every ``{{KEY}}`` from ``values``."""
    text = (templates_dir / name).read_text(encoding="utf-8")
    required = set(_PLACEHOLDER.findall(text))
    missing = sorted(required - set(values))
    if missing:
        raise ValueError(f"Template {name} is missing values for: {', '.join(missing)}")
    # Single pass over the template: values are never re-scanned for placeholders.
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], text)
