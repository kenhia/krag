"""Unit tests for ServiceConfiguration defaults, validation, and [service] TOML parsing.

T005: Tests written before implementation (TDD Red phase).
"""

from pathlib import Path

import pytest
from pydantic import ValidationError


class TestServiceConfigurationDefaults:
    """Test ServiceConfiguration model default values."""

    def test_default_host(self) -> None:
        """Default host is 0.0.0.0 for LAN access."""
        from krag.models.configuration import ServiceConfiguration

        config = ServiceConfiguration()
        assert config.host == "0.0.0.0"

    def test_default_port(self) -> None:
        """Default port is 8742 (KRAG on phone keypad)."""
        from krag.models.configuration import ServiceConfiguration

        config = ServiceConfiguration()
        assert config.port == 8742

    def test_default_primary_llm(self) -> None:
        """Default primary_llm is 'text'."""
        from krag.models.configuration import ServiceConfiguration

        config = ServiceConfiguration()
        assert config.primary_llm == "text"

    def test_default_idle_timeout(self) -> None:
        """Default idle_timeout is 300 seconds."""
        from krag.models.configuration import ServiceConfiguration

        config = ServiceConfiguration()
        assert config.idle_timeout == 300

    def test_default_log_requests(self) -> None:
        """Default log_requests is True."""
        from krag.models.configuration import ServiceConfiguration

        config = ServiceConfiguration()
        assert config.log_requests is True


class TestServiceConfigurationValidation:
    """Test ServiceConfiguration validation rules."""

    def test_port_min_boundary(self) -> None:
        """Port must be at least 1."""
        from krag.models.configuration import ServiceConfiguration

        with pytest.raises(ValidationError):
            ServiceConfiguration(port=0)

    def test_port_max_boundary(self) -> None:
        """Port must be at most 65535."""
        from krag.models.configuration import ServiceConfiguration

        with pytest.raises(ValidationError):
            ServiceConfiguration(port=65536)

    def test_valid_port_boundaries(self) -> None:
        """Port 1 and 65535 are both valid."""
        from krag.models.configuration import ServiceConfiguration

        c1 = ServiceConfiguration(port=1)
        assert c1.port == 1
        c2 = ServiceConfiguration(port=65535)
        assert c2.port == 65535

    def test_primary_llm_valid_values(self) -> None:
        """primary_llm accepts 'text', 'code', or None."""
        from krag.models.configuration import ServiceConfiguration

        assert ServiceConfiguration(primary_llm="text").primary_llm == "text"
        assert ServiceConfiguration(primary_llm="code").primary_llm == "code"
        assert ServiceConfiguration(primary_llm=None).primary_llm is None

    def test_primary_llm_invalid_value(self) -> None:
        """primary_llm rejects invalid values."""
        from krag.models.configuration import ServiceConfiguration

        with pytest.raises(ValidationError):
            ServiceConfiguration(primary_llm="invalid")

    def test_idle_timeout_non_negative(self) -> None:
        """idle_timeout must be >= 0."""
        from krag.models.configuration import ServiceConfiguration

        with pytest.raises(ValidationError):
            ServiceConfiguration(idle_timeout=-1)

    def test_idle_timeout_zero_means_never_unload(self) -> None:
        """idle_timeout=0 is valid (means never unload)."""
        from krag.models.configuration import ServiceConfiguration

        config = ServiceConfiguration(idle_timeout=0)
        assert config.idle_timeout == 0

    def test_custom_host(self) -> None:
        """Custom host is accepted."""
        from krag.models.configuration import ServiceConfiguration

        config = ServiceConfiguration(host="127.0.0.1")
        assert config.host == "127.0.0.1"


class TestServiceConfigurationOnConfiguration:
    """Test that Configuration has a service field."""

    def test_configuration_has_service_field(self) -> None:
        """Configuration includes service: ServiceConfiguration with defaults."""
        from krag.models.configuration import Configuration

        config = Configuration(directory_paths=[Path("/test/path").absolute()])
        assert hasattr(config, "service")
        assert config.service.host == "0.0.0.0"
        assert config.service.port == 8742

    def test_configuration_service_custom_values(self) -> None:
        """Configuration can accept custom service configuration."""
        from krag.models.configuration import Configuration, ServiceConfiguration

        svc = ServiceConfiguration(host="127.0.0.1", port=9000, primary_llm="code")
        config = Configuration(
            directory_paths=[Path("/test/path").absolute()],
            service=svc,
        )
        assert config.service.host == "127.0.0.1"
        assert config.service.port == 9000
        assert config.service.primary_llm == "code"


class TestServiceConfigurationTomlParsing:
    """Test [service] section parsing through ConfigManager."""

    def test_load_service_section_from_toml(self, tmp_path: Path) -> None:
        """ConfigManager parses [service] TOML section."""
        from krag.config.settings import ConfigManager

        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[directories]\npaths = ["/test/path"]\n\n'
            "[service]\n"
            'host = "192.168.1.100"\n'
            "port = 9999\n"
            'primary_llm = "code"\n'
            "idle_timeout = 600\n"
            "log_requests = false\n"
        )
        config = ConfigManager.load(config_file)
        assert config.service.host == "192.168.1.100"
        assert config.service.port == 9999
        assert config.service.primary_llm == "code"
        assert config.service.idle_timeout == 600
        assert config.service.log_requests is False

    def test_load_without_service_section_uses_defaults(self, tmp_path: Path) -> None:
        """Missing [service] section uses all defaults."""
        from krag.config.settings import ConfigManager

        config_file = tmp_path / "config.toml"
        config_file.write_text('[directories]\npaths = ["/test/path"]\n')
        config = ConfigManager.load(config_file)
        assert config.service.host == "0.0.0.0"
        assert config.service.port == 8742

    def test_load_partial_service_section(self, tmp_path: Path) -> None:
        """Partial [service] section fills missing fields with defaults."""
        from krag.config.settings import ConfigManager

        config_file = tmp_path / "config.toml"
        config_file.write_text('[directories]\npaths = ["/test/path"]\n\n[service]\nport = 5555\n')
        config = ConfigManager.load(config_file)
        assert config.service.host == "0.0.0.0"  # default
        assert config.service.port == 5555  # custom
        assert config.service.primary_llm == "text"  # default
