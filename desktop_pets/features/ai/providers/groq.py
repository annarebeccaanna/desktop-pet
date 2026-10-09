"""Groq."""

from .base import ProviderInfo

INFO = ProviderInfo(
    id="groq", name="Groq", kind="openai", default_model="llama-3.3-70b-versatile",
    models=("llama-3.3-70b-versatile",), base_url="https://api.groq.com/openai/v1",
    prefixes=("gsk_",), order=70, signup_url="https://console.groq.com/keys",
)
