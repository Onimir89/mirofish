"""Regression tests for app.utils.validation.validate_id."""

import pytest

from app.utils.validation import validate_id


class TestValidateIdAcceptsValid:
    """validate_id must accept safe hex+dash strings of 6-36 chars."""

    def test_8_char_hex(self):
        assert validate_id("a1b2c3d4") is True

    def test_12_char_hex(self):
        assert validate_id("a1b2c3d4e5f6") is True

    def test_full_uuid_36_chars(self):
        assert validate_id("550e8400-e29b-41d4-a716-446655440000") is True

    def test_hex_with_dashes(self):
        assert validate_id("aabb-ccdd") is True

    def test_minimum_length_6(self):
        assert validate_id("abcdef") is True

    def test_maximum_length_36(self):
        assert validate_id("a" * 36) is True


class TestValidateIdRejectsInvalid:
    """validate_id must reject dangerous or malformed strings."""

    def test_path_traversal(self):
        assert validate_id("../../etc/passwd") is False

    def test_command_injection_semicolon(self):
        assert validate_id("abc;rm -rf") is False

    def test_special_chars_backtick(self):
        assert validate_id("abc`whoami`") is False

    def test_empty_string(self):
        assert validate_id("") is False

    def test_too_short_5_chars(self):
        assert validate_id("abcde") is False

    def test_too_long_37_chars(self):
        assert validate_id("a" * 37) is False

    def test_uppercase_hex_rejected(self):
        # Regex only allows lowercase a-f
        assert validate_id("AABBCCDD") is False

    def test_spaces_rejected(self):
        assert validate_id("aabb ccdd") is False

    def test_slash_rejected(self):
        assert validate_id("aabb/ccdd") is False
