"""OpenRouter (viele Modelle über einen Key)."""

from .base import ProviderInfo

INFO = ProviderInfo(
    id="openrouter", name="OpenRouter", kind="openai", default_model="openrouter/auto",
    models=("openrouter/auto",), base_url="https://openrouter.ai/api/v1",
    prefixes=("sk-or-",), order=60, signup_url="https://openrouter.ai/keys",
)
