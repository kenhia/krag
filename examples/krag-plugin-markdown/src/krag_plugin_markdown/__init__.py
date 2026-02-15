"""krag plugin for indexing Markdown files.

This plugin provides support for indexing Markdown (.md) files with YAML frontmatter.
It uses krag's default text chunking strategy for simplicity.
"""

from krag_plugin_markdown.handler import MarkdownFileTypeHandler

__version__ = "1.0.0"
__all__ = ["MarkdownFileTypeHandler"]
