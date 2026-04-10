"""Tests for TextProcessor chunking logic."""

from app.services.text_processor import TextProcessor


class TestSplitText:
    def test_empty_text_returns_empty(self):
        assert TextProcessor.split_text('') == []

    def test_whitespace_only_returns_empty(self):
        assert TextProcessor.split_text('   \n\n   ') == []

    def test_short_text_single_chunk(self):
        text = 'This is a short sentence.'
        chunks = TextProcessor.split_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert 'short sentence' in chunks[0]

    def test_long_text_multiple_chunks(self):
        # Build text with many sentences
        sentences = [f'Sentence number {i} is here.' for i in range(50)]
        text = ' '.join(sentences)
        chunks = TextProcessor.split_text(text, chunk_size=100, overlap=20)
        assert len(chunks) > 1

    def test_chunks_cover_all_content(self):
        sentences = [f'Unique word w{i}.' for i in range(20)]
        text = ' '.join(sentences)
        chunks = TextProcessor.split_text(text, chunk_size=80, overlap=20)
        combined = ' '.join(chunks)
        for i in range(20):
            assert f'w{i}' in combined

    def test_overlap_creates_shared_content(self):
        sentences = [f'Sentence {i} has content.' for i in range(20)]
        text = ' '.join(sentences)
        chunks = TextProcessor.split_text(text, chunk_size=80, overlap=30)
        if len(chunks) >= 2:
            # With overlap, some content from end of chunk N
            # should appear at start of chunk N+1
            words_end_0 = set(chunks[0].split()[-5:])
            words_start_1 = set(chunks[1].split()[:10])
            assert len(words_end_0 & words_start_1) > 0

    def test_custom_chunk_size(self):
        text = 'A. B. C. D. E. F. G. H. I. J.'
        chunks_small = TextProcessor.split_text(text, chunk_size=5, overlap=0)
        chunks_large = TextProcessor.split_text(text, chunk_size=500, overlap=0)
        assert len(chunks_small) >= len(chunks_large)


class TestPreprocessText:
    def test_collapses_multiple_newlines(self):
        text = 'Hello\n\n\n\n\nWorld'
        result = TextProcessor.preprocess_text(text)
        assert '\n\n\n' not in result
        assert 'Hello' in result
        assert 'World' in result

    def test_collapses_multiple_spaces(self):
        text = 'Hello     World'
        result = TextProcessor.preprocess_text(text)
        assert '  ' not in result

    def test_strips_line_whitespace(self):
        text = '  hello  \n  world  '
        result = TextProcessor.preprocess_text(text)
        lines = result.split('\n')
        for line in lines:
            assert line == line.strip()
