import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'mirofish-secret')
    LLM_API_KEY = os.getenv('LLM_API_KEY', '')
    LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.getenv('LLM_MODEL_NAME', 'gpt-4o-mini')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50
    OASIS_DEFAULT_MAX_ROUNDS = 10
    REPORT_AGENT_MAX_TOOL_CALLS = 5
    MAX_REFLECTION_ROUNDS = 2
    TEMPERATURE = 0.5
    DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

    # Report agent
    SEARCH_RESULT_LIMIT = 15
    CONTEXT_MAX_CHARS = 6000
    SAMPLE_ENTITIES_LIMIT = 20

    # Profile generator
    PROFILE_BIO_MAX_LENGTH = 200
    PROFILE_PERSONA_MAX_LENGTH = 2000

    TWITTER_ACTIONS = [
        "CREATE_POST", "LIKE_POST", "REPOST",
        "QUOTE_POST", "DO_NOTHING",
    ]
    REDDIT_ACTIONS = [
        "CREATE_POST", "CREATE_COMMENT", "UPVOTE_POST",
        "DOWNVOTE_POST", "DO_NOTHING",
    ]

    @classmethod
    def validate(cls):
        if not cls.LLM_API_KEY:
            raise ValueError("LLM_API_KEY is required")
        os.makedirs(cls.DATA_DIR, exist_ok=True)
