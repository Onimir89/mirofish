import re
import json
from openai import OpenAI, APIConnectionError, RateLimitError, APITimeoutError
from app.config import Config
from app.utils.retry import retry_with_backoff

_TRANSIENT_ERRORS = (APIConnectionError, RateLimitError, APITimeoutError)


class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
        )
        self.model = Config.LLM_MODEL_NAME

    def chat(self, messages: list, temperature: float = None) -> str:
        """Send chat messages and return text response."""
        if temperature is None:
            temperature = Config.TEMPERATURE

        response = retry_with_backoff(
            lambda: self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            ),
            exceptions=_TRANSIENT_ERRORS,
        )
        content = response.choices[0].message.content or ""
        return self._strip_think_blocks(content)

    def chat_json(self, messages: list, temperature: float = None) -> dict:
        """Send chat messages and return parsed JSON response."""
        if temperature is None:
            temperature = Config.TEMPERATURE

        response = retry_with_backoff(
            lambda: self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            ),
            exceptions=_TRANSIENT_ERRORS,
        )
        content = response.choices[0].message.content or ""
        content = self._strip_think_blocks(content)
        content = self._clean_json(content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {}

    @staticmethod
    def _strip_think_blocks(text: str) -> str:
        """Remove <think>...</think> blocks from response."""
        return re.sub(r'<think>[\s\S]*?</think>', '', text).strip()

    @staticmethod
    def _clean_json(text: str) -> str:
        """Remove markdown code block wrappers from JSON responses."""
        text = text.strip()
        # Remove ```json ... ``` or ``` ... ```
        if text.startswith('```'):
            lines = text.split('\n')
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            text = '\n'.join(lines)
        return text.strip()
