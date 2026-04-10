"""Tests for Config class."""

import os
from unittest.mock import patch

import pytest

from app.config import Config


class TestConfigValidate:
    def test_raises_on_missing_api_key(self):
        with patch.object(Config, 'LLM_API_KEY', ''):
            with pytest.raises(ValueError, match='LLM_API_KEY'):
                Config.validate()

    def test_no_raise_with_api_key(self, tmp_path):
        with patch.object(Config, 'LLM_API_KEY', 'sk-test-key'), \
             patch.object(Config, 'DATA_DIR', str(tmp_path / 'data')):
            Config.validate()  # should not raise

    def test_creates_data_dir(self, tmp_path):
        data_dir = str(tmp_path / 'new_data_dir')
        with patch.object(Config, 'LLM_API_KEY', 'sk-test'), \
             patch.object(Config, 'DATA_DIR', data_dir):
            Config.validate()
            assert os.path.isdir(data_dir)


class TestConfigDefaults:
    def test_allowed_extensions(self):
        assert 'pdf' in Config.ALLOWED_EXTENSIONS
        assert 'txt' in Config.ALLOWED_EXTENSIONS
        assert 'md' in Config.ALLOWED_EXTENSIONS

    def test_chunk_defaults(self):
        assert Config.DEFAULT_CHUNK_SIZE > 0
        assert Config.DEFAULT_CHUNK_OVERLAP >= 0
        assert Config.DEFAULT_CHUNK_OVERLAP < Config.DEFAULT_CHUNK_SIZE

    def test_twitter_actions_defined(self):
        assert 'CREATE_POST' in Config.TWITTER_ACTIONS
        assert 'DO_NOTHING' in Config.TWITTER_ACTIONS

    def test_reddit_actions_defined(self):
        assert 'CREATE_POST' in Config.REDDIT_ACTIONS
        assert 'CREATE_COMMENT' in Config.REDDIT_ACTIONS
