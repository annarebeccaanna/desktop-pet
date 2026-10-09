"""Google (Gemini) über die OpenAI-kompatible Schnittstelle."""

from .base import ProviderInfo

INFO = ProviderInfo(
    id="gemini", name="Google (Gemini)", kind="openai", default_model="gemini-2.5-flash",
    models=("gemini-2.5-flash", "gemini-2.5-pro"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    prefixes=("AIza",), order=40, signup_url="https://aistudio.google.com/apikey",
)
