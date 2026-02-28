"""krag plugin for indexing Obsidian vault content.

This plugin provides support for indexing Obsidian vault `.md` files with:
- Path-based ownership (claims files under configured vault paths)
- Mixed-content routing (prose → docs, fenced code → code collections)
- Virtual ``obsidian://`` path prefixes for clean attribution
- Obsidian-specific domain lexicon
"""

from krag_plugin_obsidian.config import ObsidianConfig
from krag_plugin_obsidian.handler import ObsidianFileTypeHandler

__version__ = "1.0.0"
__all__ = ["ObsidianConfig", "ObsidianFileTypeHandler"]
