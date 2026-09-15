import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")
    SEMANTIC_LAYER_PATH: str = "src/config/semantic_layer.yaml"
    TABLE_DESCRIPTIONS_PATH: str = "docs/table_descriptions.yaml"
    MSCHEMA_PATH: str = "src/config/mschema.yaml"
    POLICY_PATH: str = "policies/security_policies.yaml"
    DUCKDB_PATH: str = "data/bank.duckdb"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def llm_api_key(self) -> str:
        if self.LLM_PROVIDER.lower() == "openrouter" and self.OPENROUTER_API_KEY:
            return self.OPENROUTER_API_KEY
        return self.OPENAI_API_KEY

    @property
    def llm_base_url(self) -> str | None:
        if self.LLM_PROVIDER.lower() == "openrouter" and self.OPENROUTER_API_KEY:
            return self.OPENROUTER_BASE_URL
        return self.OPENAI_BASE_URL or None

    @property
    def llm_model(self) -> str:
        if self.LLM_PROVIDER.lower() == "openrouter" and self.OPENROUTER_API_KEY:
            return self.OPENROUTER_MODEL
        return self.OPENAI_MODEL

settings = Settings()
