from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings class.

    This class loads configuration values and secrets from environment variables
    and an optional .env file. Centralizing this here prevents hardcoding values
    in individual router or agent files.
    """
    # API Keys for the agents (with defaults as empty strings)
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    tavily_api_key: str = ""

    # Model Configurations (centralized as per code style guidelines)
    gemini_model: str = "gemini-2.5-flash"
    openrouter_model: str = "google/gemini-2.5-flash"

    # Model Configuration to read from .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate the settings object to be shared across the application.
settings = Settings()
