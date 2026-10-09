"""Eigener Endpunkt (OpenAI-kompatibel), z. B. lokale Modelle über Ollama oder LM Studio.
Ein Key ist hier optional."""

from .base import ProviderInfo

INFO = ProviderInfo(
    id="custom", name="Eigener Endpunkt (OpenAI-kompatibel)", kind="openai", default_model="llama3.2",
    base_url="http://localhost:11434/v1", order=90, url_editable=True,
)
