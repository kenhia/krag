"""Path reduction utilities for displaying shortened paths."""

from pathlib import Path


class PathReducer:
    """Reduces absolute paths to more readable forms using configured aliases.

    Applies path aliases in longest-match-first order to show the most
    specific reduction possible.
    """

    def __init__(self, path_aliases: list[str] | None = None):
        """Initialize path reducer.

        Args:
            path_aliases: List of "full_path:alias" strings, e.g.,
                ["/home/ken:~", "/home/ken/src:src"]
        """
        self.aliases: list[tuple[Path, str]] = []

        if path_aliases:
            # Parse and sort by path length (longest first)
            for alias_str in path_aliases:
                if ":" not in alias_str:
                    continue  # Skip invalid entries
                full_path_str, alias = alias_str.split(":", 1)
                full_path = Path(full_path_str).resolve()
                self.aliases.append((full_path, alias))

            # Sort by path length descending for longest-match-first
            self.aliases.sort(key=lambda x: len(str(x[0])), reverse=True)

    def reduce(self, path: Path) -> str:
        """Reduce an absolute path using configured aliases.

        Args:
            path: Absolute path to reduce

        Returns:
            Reduced path string, or original path if no match
        """
        if not self.aliases:
            return str(path)

        resolved_path = path.resolve()

        # Try each alias (already sorted longest-first)
        for full_path, alias in self.aliases:
            try:
                # Check if path starts with this prefix
                relative = resolved_path.relative_to(full_path)
                # Build the reduced path
                if relative == Path("."):
                    # Path is exactly the alias directory
                    return alias
                else:
                    # Path is under the alias directory
                    return f"{alias}/{relative}"
            except ValueError:
                # Not relative to this path, try next
                continue

        # No match found, return original
        return str(path)
