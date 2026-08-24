from olympus_core.config import FootballSettings
from olympus_core.integrations.football.api_football import ApiFootballProvider
from olympus_core.integrations.football.base import FootballProvider, FootballProviderError
from olympus_core.integrations.football.collector import FootballCollector
from olympus_core.integrations.football.fixture import FixtureFootballProvider
from olympus_core.integrations.football.football_data import FootballDataProvider


def create_football_provider(settings: FootballSettings) -> FootballProvider:
    provider = settings.provider
    if provider == "api-football":
        return ApiFootballProvider(settings)
    if provider == "football-data":
        return FootballDataProvider(settings)
    if provider == "fixture":
        return FixtureFootballProvider(settings)
    raise FootballProviderError(f"Unsupported football provider: {provider!r}")


__all__ = [
    "ApiFootballProvider",
    "FootballDataProvider",
    "FixtureFootballProvider",
    "FootballCollector",
    "create_football_provider",
]
