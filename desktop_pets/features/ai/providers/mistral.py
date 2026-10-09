"""Mistral (Key ohne Präfix – Anbieter bitte auswählen)."""

from .base import ProviderInfo

INFO = ProviderInfo(
    id="mistral", name="Mistral", kind="openai", default_model="mistral-small-latest",
    models=("mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"),
    base_url="https://api.mistral.ai/v1", order=50, signup_url="https://console.mistral.ai/api-keys",
)
