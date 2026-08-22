from olympus_core.models.weather import WeatherState


class WeatherStateStore:
    def __init__(self) -> None:
        self._state: WeatherState | None = None

    def get(self) -> WeatherState | None:
        return self._state

    def update(self, state: WeatherState) -> None:
        self._state = state
