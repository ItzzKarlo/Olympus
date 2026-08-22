from dataclasses import dataclass, field
import os
from pathlib import Path
import tomllib
from typing import Any
import logging


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TargetConfig:
    id: str
    name: str
    host: str
    port: int
    alert: bool = True


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    id: str
    name: str
    type: str
    host: str | None = None
    port: int | None = None
    url: str | None = None
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    enabled: bool = True
    poll_seconds: float = 5.0
    timeout_seconds: float = 2.0
    gateway: str = "10.10.0.1"
    gateway_port: int = 53
    internet_host: str = "1.1.1.1"
    internet_port: int = 443
    dns_hostname: str = "example.com"
    https_url: str = "https://www.cloudflare.com/cdn-cgi/trace"
    failure_threshold: int = 3
    recovery_threshold: int = 2
    targets: tuple[TargetConfig, ...] = ()


@dataclass(frozen=True, slots=True)
class MonitoringConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    services: tuple[ServiceConfig, ...] = ()
    service_poll_seconds: float = 10.0
    service_timeout_seconds: float = 3.0
    service_failure_threshold: int = 3
    service_recovery_threshold: int = 2
    core_host_poll_seconds: float = 5.0


def _positive(value: Any, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) and value > 0 else default


def _threshold(value: Any, default: int) -> int:
    return int(value) if isinstance(value, int) and value > 0 else default


def parse_monitoring_config(data: dict[str, Any]) -> MonitoringConfig:
    network_data = data.get("network") if isinstance(data.get("network"), dict) else {}
    targets: list[TargetConfig] = []
    for target in network_data.get("targets", []):
        if not isinstance(target, dict):
            continue
        try:
            targets.append(
                TargetConfig(
                    id=str(target["id"]),
                    name=str(target.get("name") or target["id"]),
                    host=str(target["host"]),
                    port=int(target["port"]),
                    alert=bool(target.get("alert", True)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    service_section = data.get("service_monitoring")
    service_section = service_section if isinstance(service_section, dict) else {}
    services: list[ServiceConfig] = []
    for service in data.get("services", []):
        if not isinstance(service, dict):
            continue
        try:
            services.append(
                ServiceConfig(
                    id=str(service["id"]),
                    name=str(service.get("name") or service["id"]),
                    type=str(service["type"]).lower(),
                    host=str(service["host"]) if service.get("host") else None,
                    port=int(service["port"]) if service.get("port") else None,
                    url=str(service["url"]) if service.get("url") else None,
                    severity=str(service.get("severity", "warning")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return MonitoringConfig(
        network=NetworkConfig(
            enabled=bool(network_data.get("enabled", True)),
            poll_seconds=_positive(network_data.get("poll_seconds"), 5.0),
            timeout_seconds=_positive(network_data.get("timeout_seconds"), 2.0),
            gateway=str(network_data.get("gateway", "10.10.0.1")),
            gateway_port=int(network_data.get("gateway_port", 53)),
            internet_host=str(network_data.get("internet_host", "1.1.1.1")),
            internet_port=int(network_data.get("internet_port", 443)),
            dns_hostname=str(network_data.get("dns_hostname", "example.com")),
            https_url=str(network_data.get("https_url", "https://www.cloudflare.com/cdn-cgi/trace")),
            failure_threshold=_threshold(network_data.get("failure_threshold"), 3),
            recovery_threshold=_threshold(network_data.get("recovery_threshold"), 2),
            targets=tuple(targets),
        ),
        services=tuple(services),
        service_poll_seconds=_positive(service_section.get("poll_seconds"), 10.0),
        service_timeout_seconds=_positive(service_section.get("timeout_seconds"), 3.0),
        service_failure_threshold=_threshold(service_section.get("failure_threshold"), 3),
        service_recovery_threshold=_threshold(service_section.get("recovery_threshold"), 2),
        core_host_poll_seconds=_positive(data.get("core_host_poll_seconds"), 5.0),
    )


def load_monitoring_config(path: Path | None = None) -> MonitoringConfig:
    config_path = path or Path(os.getenv("OLYMPUS_CONFIG", "config.toml"))
    if not config_path.exists():
        return MonitoringConfig()
    try:
        with config_path.open("rb") as file:
            return parse_monitoring_config(tomllib.load(file))
    except (OSError, tomllib.TOMLDecodeError) as error:
        logger.warning("Monitoring configuration is invalid; using defaults: %s", error)
        return MonitoringConfig()
