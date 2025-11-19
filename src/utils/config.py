"""Configuration management for Assembly API."""

import os

from dotenv import load_dotenv

load_dotenv()


def get_api_key() -> str:
    """Get API key from environment variable."""
    api_key = os.getenv("ASSEMBLY_API_KEY")
    if not api_key:
        raise ValueError("ASSEMBLY_API_KEY not found in environment variables")
    return api_key


BASE_URL = "https://open.assembly.go.kr/portal/openapi"
