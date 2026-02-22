"""Tests for main module"""

import pytest

from ai_content_analyzer.main import main
from ai_content_analyzer.config import config


def test_main_runs_without_error(capsys) -> None:
    """Test that main function runs without errors"""
    main()
    captured = capsys.readouterr()
    assert captured.out == "" or "Starting" in captured.out


def test_config_loaded() -> None:
    """Test that configuration is properly loaded"""
    assert config.APP_NAME == "ai-content-analyzer"
    assert config.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
