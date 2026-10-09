"""xAI (Grok)."""

from .base import ProviderInfo

INFO = ProviderInfo(
    id="xai", name="xAI (Grok)", kind="openai", default_model="grok-4",
    models=("grok-4",), base_url="https://api.x.ai/v1",
    prefixes=("xai-",), order=75, signup_url="https://console.x.ai",
)
