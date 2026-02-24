"""Domain lexicon — project-specific terminology injection."""

from krag.lexicon.lexicon_injector import LexiconInjector
from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

__all__ = ["LexiconInjector", "LexiconStore", "LexiconValidationError"]
