"""Configuration management for the Jarvis personal assistant.

This module defines runtime settings using `pydantic-settings`.
Values can be overridden using environment variables prefixed with `JARVIS_`
or via a `.env` file in the working directory.

Example:
    To override the database path or model in the terminal:
    ```bash
    export JARVIS_FAST_MODEL="llama3.2:3b"
    export JARVIS_DB_PATH="data/test_jarvis.db"
    python -m jarvis.cli
    ```

    Or in code:
    ```python
    from jarvis.config import settings

    print(settings.fast_model)
    print(settings.db_path)
    ```
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables or .env file.

    Attributes:
        llm_base_url: Base URL for OpenAI-compatible LLM endpoint (default: local Ollama).
        llm_api_key: API key for the LLM endpoint (default: 'not-needed' for local servers).
        llm_timeout_s: HTTP request timeout in seconds when communicating with LLM.
        fast_model: Model name for quick/low-latency responses (e.g., qwen3:4b).
        smart_model: Model name for complex reasoning/thinking tasks.
        db_path: Path to the SQLite database file for conversation history.
        context_token: Maximum context window size in tokens allocated for the model.
        replay_reserve_tokens: Number of tokens reserved for generation/response buffer.
        max_parallel_generations: Concurrency limit for simultaneous LLM generations.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="JARVIS_")

    # LLM server connection details
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "not-needed"
    llm_timeout_s: int = 120

    # Model identifiers
    fast_model: str = "qwen3:4b"
    smart_model: str = "qwen3:4b"  # Can be pointed to a larger model later (e.g. qwen2.5:14b)

    # Persistence
    db_path: str = "data/jarvis.db"

    # Token budgeting: context_token should match the context window in 'ollama ps'
    context_token: int = 4096
    # Buffer left specifically for the model's output generation
    replay_reserve_tokens: int = 768

    # Concurrency control: on local CPU, 1 generation at a time avoids severe throttling
    max_parallel_generations: int = 1


# Singleton instance used throughout the application
settings = Settings()
