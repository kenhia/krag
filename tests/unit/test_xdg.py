"""Tests for XDG Base Directory utilities."""

import os
from pathlib import Path
from unittest.mock import patch

from krag.config.xdg import (
    get_krag_cache_dir,
    get_krag_config_dir,
    get_krag_state_dir,
    get_xdg_cache_home,
    get_xdg_config_home,
    get_xdg_state_home,
    migrate_from_legacy,
    should_migrate_from_legacy,
)


class TestXDGDirectories:
    """Test XDG directory resolution."""

    def test_get_xdg_config_home_default(self) -> None:
        """Test XDG_CONFIG_HOME defaults to ~/.config."""
        with patch.dict(os.environ, {}, clear=True):
            config_home = get_xdg_config_home()
            assert config_home == Path.home() / ".config"

    def test_get_xdg_config_home_from_env(self) -> None:
        """Test XDG_CONFIG_HOME reads from environment."""
        custom_path = "/custom/config"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_path}):
            config_home = get_xdg_config_home()
            assert config_home == Path(custom_path)

    def test_get_xdg_cache_home_default(self) -> None:
        """Test XDG_CACHE_HOME defaults to ~/.cache."""
        with patch.dict(os.environ, {}, clear=True):
            cache_home = get_xdg_cache_home()
            assert cache_home == Path.home() / ".cache"

    def test_get_xdg_cache_home_from_env(self) -> None:
        """Test XDG_CACHE_HOME reads from environment."""
        custom_path = "/custom/cache"
        with patch.dict(os.environ, {"XDG_CACHE_HOME": custom_path}):
            cache_home = get_xdg_cache_home()
            assert cache_home == Path(custom_path)

    def test_get_xdg_state_home_default(self) -> None:
        """Test XDG_STATE_HOME defaults to ~/.local/state."""
        with patch.dict(os.environ, {}, clear=True):
            state_home = get_xdg_state_home()
            assert state_home == Path.home() / ".local" / "state"

    def test_get_xdg_state_home_from_env(self) -> None:
        """Test XDG_STATE_HOME reads from environment."""
        custom_path = "/custom/state"
        with patch.dict(os.environ, {"XDG_STATE_HOME": custom_path}):
            state_home = get_xdg_state_home()
            assert state_home == Path(custom_path)


class TestKragDirectories:
    """Test krag-specific directory resolution."""

    def test_get_krag_config_dir_default(self) -> None:
        """Test krag config dir follows XDG."""
        with patch.dict(os.environ, {}, clear=True):
            krag_config = get_krag_config_dir()
            assert krag_config == Path.home() / ".config" / "krag"

    def test_get_krag_config_dir_legacy(self) -> None:
        """Test krag config dir with legacy flag."""
        krag_config = get_krag_config_dir(legacy=True)
        assert krag_config == Path.home() / ".krag"

    def test_get_krag_cache_dir_default(self) -> None:
        """Test krag cache dir follows XDG."""
        with patch.dict(os.environ, {}, clear=True):
            krag_cache = get_krag_cache_dir()
            assert krag_cache == Path.home() / ".cache" / "krag"

    def test_get_krag_cache_dir_legacy(self) -> None:
        """Test krag cache dir with legacy flag."""
        krag_cache = get_krag_cache_dir(legacy=True)
        assert krag_cache == Path.home() / ".krag"

    def test_get_krag_state_dir_default(self) -> None:
        """Test krag state dir follows XDG."""
        with patch.dict(os.environ, {}, clear=True):
            krag_state = get_krag_state_dir()
            assert krag_state == Path.home() / ".local" / "state" / "krag"

    def test_get_krag_state_dir_legacy(self) -> None:
        """Test krag state dir with legacy flag."""
        krag_state = get_krag_state_dir(legacy=True)
        assert krag_state == Path.home() / ".krag"


class TestMigration:
    """Test migration from legacy ~/.krag to XDG directories."""

    def test_should_migrate_when_legacy_exists_and_xdg_doesnt(self, tmp_path: Path) -> None:
        """Test migration detection when legacy exists but XDG doesn't."""
        legacy_path = tmp_path / ".krag"
        legacy_path.mkdir()

        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            assert should_migrate_from_legacy() is True

    def test_should_not_migrate_when_xdg_exists(self, tmp_path: Path) -> None:
        """Test no migration when XDG directory already exists."""
        legacy_path = tmp_path / ".krag"
        legacy_path.mkdir()

        xdg_config = tmp_path / ".config" / "krag"
        xdg_config.mkdir(parents=True)

        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            assert should_migrate_from_legacy() is False

    def test_should_not_migrate_when_legacy_doesnt_exist(self, tmp_path: Path) -> None:
        """Test no migration when legacy directory doesn't exist."""
        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            assert should_migrate_from_legacy() is False

    def test_migrate_from_legacy_config_files(self, tmp_path: Path) -> None:
        """Test migration of configuration files."""
        legacy_path = tmp_path / ".krag"
        legacy_path.mkdir()

        # Create test config files
        (legacy_path / "config.toml").write_text("test config toml")
        (legacy_path / "config.yaml").write_text("test config yaml")

        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            migrations = migrate_from_legacy()

            # Check files were moved
            xdg_config = tmp_path / ".config" / "krag"
            assert (xdg_config / "config.toml").read_text() == "test config toml"
            assert (xdg_config / "config.yaml").read_text() == "test config yaml"
            assert not (legacy_path / "config.toml").exists()
            assert not (legacy_path / "config.yaml").exists()

            # Check migrations dict
            assert len(migrations) == 2

    def test_migrate_from_legacy_storage(self, tmp_path: Path) -> None:
        """Test migration of vector store storage."""
        legacy_path = tmp_path / ".krag"
        legacy_path.mkdir()

        # Create test storage directory with a file
        (legacy_path / "storage").mkdir()
        (legacy_path / "storage" / "test.db").write_text("vector data")

        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            migrations = migrate_from_legacy()

            # Check storage was moved
            xdg_cache = tmp_path / ".cache" / "krag"
            assert (xdg_cache / "storage" / "test.db").read_text() == "vector data"
            assert not (legacy_path / "storage").exists()

            assert len(migrations) == 1

    def test_migrate_from_legacy_logs(self, tmp_path: Path) -> None:
        """Test migration of logs directory."""
        legacy_path = tmp_path / ".krag"
        legacy_path.mkdir()

        # Create test logs directory with a file
        (legacy_path / "logs").mkdir()
        (legacy_path / "logs" / "krag.log").write_text("log content")

        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            migrations = migrate_from_legacy()

            # Check logs were moved
            xdg_state = tmp_path / ".local" / "state" / "krag"
            assert (xdg_state / "logs" / "krag.log").read_text() == "log content"
            assert not (legacy_path / "logs").exists()

            assert len(migrations) == 1

    def test_migrate_from_legacy_metadata(self, tmp_path: Path) -> None:
        """Test migration of metadata file."""
        legacy_path = tmp_path / ".krag"
        legacy_path.mkdir()

        # Create test metadata file
        (legacy_path / "metadata.json").write_text('{"test": "data"}')

        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            migrations = migrate_from_legacy()

            # Check metadata was moved
            xdg_state = tmp_path / ".local" / "state" / "krag"
            assert (xdg_state / "metadata.json").read_text() == '{"test": "data"}'
            assert not (legacy_path / "metadata.json").exists()

            assert len(migrations) == 1

    def test_migrate_from_legacy_removes_empty_directory(self, tmp_path: Path) -> None:
        """Test migration removes empty legacy directory."""
        legacy_path = tmp_path / ".krag"
        legacy_path.mkdir()
        (legacy_path / "config.toml").write_text("test")

        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            migrate_from_legacy()

            # Legacy directory should be removed if empty
            assert not legacy_path.exists()

    def test_migrate_from_legacy_preserves_non_empty_directory(self, tmp_path: Path) -> None:
        """Test migration preserves legacy directory if not empty."""
        legacy_path = tmp_path / ".krag"
        legacy_path.mkdir()
        (legacy_path / "config.toml").write_text("test")
        (legacy_path / "other_file.txt").write_text("keep me")

        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            migrate_from_legacy()

            # Legacy directory should be preserved
            assert legacy_path.exists()
            assert (legacy_path / "other_file.txt").read_text() == "keep me"

    def test_migrate_from_legacy_no_op_when_legacy_missing(self, tmp_path: Path) -> None:
        """Test migration is no-op when legacy directory doesn't exist."""
        with (
            patch("krag.config.xdg.Path.home", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            migrations = migrate_from_legacy()

            assert migrations == {}
