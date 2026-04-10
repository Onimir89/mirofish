import os
import chardet


class FileParser:
    """Extract text content from uploaded files."""

    @staticmethod
    def parse(filepath: str, filename: str) -> dict:
        """Parse a single file and return {filename, content}."""
        ext = os.path.splitext(filename)[1].lower().lstrip('.')

        if ext == 'pdf':
            content = FileParser._parse_pdf(filepath)
        elif ext in ('md', 'markdown'):
            content = FileParser._parse_text(filepath)
        elif ext == 'txt':
            content = FileParser._parse_text(filepath)
        else:
            content = ''

        return {'filename': filename, 'content': content}

    @staticmethod
    def parse_multiple(file_paths: list[tuple[str, str]]) -> list[dict]:
        """Parse multiple files. Each item is (filepath, filename)."""
        results = []
        for filepath, filename in file_paths:
            result = FileParser.parse(filepath, filename)
            if result['content']:
                results.append(result)
        return results

    @staticmethod
    def _parse_pdf(filepath: str) -> str:
        """Extract text from PDF using PyMuPDF."""
        try:
            import fitz
            doc = fitz.open(filepath)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return '\n'.join(text_parts)
        except Exception as e:
            print(f"PDF parse error: {e}")
            return ''

    @staticmethod
    def _parse_text(filepath: str) -> str:
        """Read text file with charset detection."""
        try:
            with open(filepath, 'rb') as f:
                raw = f.read()

            detected = chardet.detect(raw)
            encoding = detected.get('encoding', 'utf-8') or 'utf-8'

            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                return raw.decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Text parse error: {e}")
            return ''
