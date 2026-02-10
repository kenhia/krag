"""Shared pytest fixtures for all tests."""

import pytest

from tests.fixtures.mock_plugin import MockFileTypeHandler


@pytest.fixture
def mock_file_handler() -> MockFileTypeHandler:
    """Provide a mock FileTypeHandler for testing."""
    return MockFileTypeHandler()
