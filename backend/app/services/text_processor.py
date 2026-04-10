import re
from app.utils.file_parser import FileParser


class TextProcessor:
    """Text extraction and chunking service."""

    @staticmethod
    def extract_from_files(file_paths: list[tuple[str, str]]) -> list[dict]:
        """Extract text from uploaded files.
        Args:
            file_paths: list of (filepath, filename) tuples
        Returns:
            list of {filename, content} dicts
        """
        return FileParser.parse_multiple(file_paths)

    @staticmethod
    def preprocess_text(text: str) -> str:
        """Normalize whitespace and newlines."""
        # Collapse multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Collapse multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        # Strip leading/trailing whitespace per line
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()

    @staticmethod
    def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """Split text into chunks with overlap, respecting sentence boundaries.

        Splits on sentence-ending punctuation (. ? ! and Chinese equivalents).
        """
        text = TextProcessor.preprocess_text(text)
        if not text:
            return []

        # Split into sentences
        sentence_pattern = r'(?<=[.!?\u3002\uff01\uff1f])\s+'
        sentences = re.split(sentence_pattern, text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            if current_length + sentence_len > chunk_size and current_chunk:
                # Save current chunk
                chunks.append(' '.join(current_chunk))

                # Calculate overlap: keep last sentences up to overlap chars
                overlap_chunk = []
                overlap_len = 0
                for s in reversed(current_chunk):
                    if overlap_len + len(s) > overlap:
                        break
                    overlap_chunk.insert(0, s)
                    overlap_len += len(s)

                current_chunk = overlap_chunk
                current_length = overlap_len

            current_chunk.append(sentence)
            current_length += sentence_len

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks
