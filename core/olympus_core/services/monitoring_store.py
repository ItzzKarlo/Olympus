from olympus_core.models.monitoring import CoreHostState, NetworkState, ServiceState


class MonitoringStore:
    def __init__(self) -> None:
        self.core_host: CoreHostState | None = None
        self.network: NetworkState | None = None
        self.services: dict[str, ServiceState] = {}
