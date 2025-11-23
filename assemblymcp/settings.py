"""Settings management for AssemblyMCP"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    assembly_api_key: str = ""
    default_assembly_age: str = "22"

    def validate_api_key(self) -> None:
        """Validate that API key is provided"""
        if not self.assembly_api_key:
            raise ValueError(
                "ASSEMBLY_API_KEY is required. Set it via environment variable or .env file."
            )


# Global settings instance
settings = Settings()
