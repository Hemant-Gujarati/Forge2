"""AI provider factory for Forge."""

from forge.providers.base import BaseProvider


def create_provider(name: str, config) -> BaseProvider:
    """Create a provider instance by name."""
    provider_config = config.get_provider_config(name)

    match name:
        case "openai":
            from forge.providers.openai_provider import OpenAIProvider

            return OpenAIProvider(provider_config)
        case "anthropic":
            from forge.providers.anthropic_provider import AnthropicProvider

            return AnthropicProvider(provider_config)
        case "gemini":
            from forge.providers.gemini_provider import GeminiProvider

            return GeminiProvider(provider_config)
        case "ollama":
            from forge.providers.ollama_provider import OllamaProvider

            return OllamaProvider(provider_config)
        case _:
            raise ValueError(
                f"Unknown provider: '{name}'. Available: openai, anthropic, gemini, ollama"
            )


def list_providers() -> list[str]:
    """List available provider names."""
    return ["openai", "anthropic", "gemini", "ollama"]
