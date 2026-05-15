from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Azure OpenAI ──────────────────────────────────────
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-08-01-preview"

    # ── Azure AI Project (Foundry) ────────────────────────
    azure_ai_project_endpoint: str = ""

    # ── Azure Content Safety ──────────────────────────────
    azure_content_safety_endpoint: str = ""

    # ── SerpAPI (unchanged) ───────────────────────────────
    serpapi_api_key: str = ""

    # ── SQLite (unchanged) ────────────────────────────────
    sqlite_db_path: str = "/tmp/finance_agent.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"
    )


settings = Settings()