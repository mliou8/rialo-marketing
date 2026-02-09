"""
Configuration helper that reads from .env locally or st.secrets on Streamlit Cloud.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str, default: str = "") -> str:
    """
    Get a secret value, checking Streamlit secrets first, then environment.

    Args:
        key: The secret key name
        default: Default value if not found

    Returns:
        The secret value
    """
    # Try Streamlit secrets first (for Cloud deployment)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except (ImportError, Exception):
        pass

    # Fall back to environment variable
    return os.getenv(key, default)


# Export commonly used config values
DATABASE_URL = get_secret("DATABASE_URL")
APIFY_API_TOKEN = get_secret("APIFY_API_TOKEN")
NOTION_TOKEN = get_secret("NOTION_TOKEN")
ANTHROPIC_API_KEY = get_secret("ANTHROPIC_API_KEY")
