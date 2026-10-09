"""OpenAI (ChatGPT)."""

from .base import ProviderInfo

INFO = ProviderInfo(
    id="openai", name="OpenAI (ChatGPT)", kind="openai", default_model="gpt-5-mini",
    models=("gpt-5-mini", "gpt-5", "gpt-5-nano"), base_url="https://api.openai.com/v1",
    prefixes=("sk-proj-", "sk-"), order=30, signup_url="https://platform.openai.com/api-keys",
)
