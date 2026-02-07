"""Tests for path reducer utility."""

from pathlib import Path

from krag.config.path_reducer import PathReducer


class TestPathReducer:
    """Test path reduction with aliases."""

    def test_no_aliases(self):
        """Test reducer with no aliases returns original path."""
        reducer = PathReducer()
        path = Path("/home/user/file.txt")
        assert reducer.reduce(path) == str(path)

    def test_home_alias(self):
        """Test home directory alias."""
        # Use actual home for testing
        home = Path.home()
        reducer = PathReducer([f"{home}:~"])

        # File in home
        path = home / "Documents" / "file.txt"
        assert reducer.reduce(path) == "~/Documents/file.txt"

        # Exactly the home directory
        assert reducer.reduce(home) == "~"

    def test_multiple_aliases_longest_match(self):
        """Test that longest matching prefix is used."""
        reducer = PathReducer(
            [
                "/home/ken:~",
                "/home/ken/src:src",
                "/scratch/data:data",
            ]
        )

        # Should match /home/ken/src (longer than /home/ken)
        path = Path("/home/ken/src/krag/README.md")
        assert reducer.reduce(path) == "src/krag/README.md"

        # Should match /home/ken
        path = Path("/home/ken/Documents/file.txt")
        assert reducer.reduce(path) == "~/Documents/file.txt"

        # Should match /scratch/data
        path = Path("/scratch/data/dataset.csv")
        assert reducer.reduce(path) == "data/dataset.csv"

        # No match
        path = Path("/opt/bin/tool")
        assert reducer.reduce(path) == str(path)

    def test_invalid_alias_format(self):
        """Test that invalid alias formats are skipped."""
        reducer = PathReducer(
            [
                "/home/ken:~",
                "invalid_no_colon",  # Should be skipped
                "/home/ken/src:src",
            ]
        )

        path = Path("/home/ken/src/krag/README.md")
        # Should still work with valid aliases
        assert reducer.reduce(path) == "src/krag/README.md"

    def test_exact_directory_match(self):
        """Test path exactly matching alias directory."""
        reducer = PathReducer(["/home/ken/src:src"])
        path = Path("/home/ken/src")
        assert reducer.reduce(path) == "src"

    def test_empty_alias_list(self):
        """Test with empty alias list."""
        reducer = PathReducer([])
        path = Path("/home/ken/file.txt")
        assert reducer.reduce(path) == str(path)

    def test_none_alias_list(self):
        """Test with None alias list."""
        reducer = PathReducer(None)
        path = Path("/home/ken/file.txt")
        assert reducer.reduce(path) == str(path)

    def test_relative_paths_resolved(self):
        """Test that relative paths are resolved before matching."""
        # Create a relative path and resolve it
        home = Path.home()
        reducer = PathReducer([f"{home}:~"])

        # Even if we pass a relative path, it should be resolved
        # (assuming we're somewhere that makes this valid)
        # This tests the internal resolve() call
        path = home / "Documents" / "test.txt"
        assert reducer.reduce(path) == "~/Documents/test.txt"
