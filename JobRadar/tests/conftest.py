"""Pytest configuration and fixtures."""

import pytest
import pytest_asyncio

# Ensure asyncio mode is set
pytest_asyncio.plugin.pytest_configure = lambda config: None

# Register asyncio mode
def pytest_configure(config):
    config.option.asyncio_mode = "auto"