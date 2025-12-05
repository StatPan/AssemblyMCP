from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Core Settings
    assembly_api_key: str | None = Field(None, description="National Assembly API Key")
    default_assembly_age: str = Field("22", description="Default Assembly Age (e.g. 22)")

    # Logging Settings
    log_level: str = Field("INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    log_json: bool = Field(False, description="Enable JSON logging for Cloud Run")

    # Caching Settings
    enable_caching: bool = Field(False, description="Enable in-memory caching")
    cache_ttl_seconds: int = Field(300, description="Cache TTL in seconds")
    cache_max_size: int = Field(100, description="Maximum number of cached items")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASSEMBLY_", extra="ignore")


settings = Settings()
