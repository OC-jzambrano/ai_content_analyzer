"""Tests for models module"""

import pytest
from datetime import datetime

from ai_content_analyzer.models import Content


class TestContent:
    """Test cases for Content model"""

    def test_content_creation(self) -> None:
        """Test creating a content object"""
        content = Content(
            id="1",
            title="Test Title",
            text="Test content text"
        )
        assert content.id == "1"
        assert content.title == "Test Title"
        assert content.text == "Test content text"
        assert isinstance(content.created_at, datetime)
        assert isinstance(content.updated_at, datetime)
        assert content.tags == []
        assert content.metadata == {}

    def test_content_validation_empty_title(self) -> None:
        """Test that content validation fails with empty title"""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            Content(id="1", title="", text="Some text")

    def test_content_validation_empty_text(self) -> None:
        """Test that content validation fails with empty text"""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            Content(id="1", title="Title", text="")

    def test_add_tag(self) -> None:
        """Test adding tags to content"""
        content = Content(id="1", title="Title", text="Text")
        content.add_tag("python")
        content.add_tag("tutorial")
        assert "python" in content.tags
        assert "tutorial" in content.tags
        assert len(content.tags) == 2

    def test_add_duplicate_tag(self) -> None:
        """Test that duplicate tags are not added"""
        content = Content(id="1", title="Title", text="Text")
        content.add_tag("python")
        content.add_tag("python")
        assert len(content.tags) == 1

    def test_remove_tag(self) -> None:
        """Test removing tags from content"""
        content = Content(id="1", title="Title", text="Text")
        content.add_tag("python")
        content.add_tag("tutorial")
        content.remove_tag("python")
        assert "python" not in content.tags
        assert "tutorial" in content.tags
        assert len(content.tags) == 1

    def test_update_metadata(self) -> None:
        """Test updating metadata"""
        content = Content(id="1", title="Title", text="Text")
        initial_updated_at = content.updated_at
        content.update_metadata("author", "John Doe")
        assert content.metadata["author"] == "John Doe"
        assert content.updated_at > initial_updated_at
