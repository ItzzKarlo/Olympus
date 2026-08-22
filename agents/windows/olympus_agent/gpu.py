from typing import Any


def collect_nvidia_gpu(nvml: Any | None = None) -> dict[str, Any] | None:
    """Collect the primary NVIDIA GPU when NVML is installed and available."""
    if nvml is None:
        try:
            import pynvml as nvml_module
        except ImportError:
            return None
        nvml = nvml_module

    initialized = False
    try:
        nvml.nvmlInit()
        initialized = True
        if nvml.nvmlDeviceGetCount() < 1:
            return None
        handle = nvml.nvmlDeviceGetHandleByIndex(0)
        name = nvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode(errors="replace")
        utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
        memory = nvml.nvmlDeviceGetMemoryInfo(handle)
        try:
            temperature = nvml.nvmlDeviceGetTemperature(
                handle, nvml.NVML_TEMPERATURE_GPU
            )
        except Exception:
            temperature = None
        return {
            "name": str(name),
            "utilization_percent": float(utilization.gpu),
            "memory_used_bytes": int(memory.used),
            "memory_total_bytes": int(memory.total),
            "temperature_celsius": float(temperature) if temperature is not None else None,
        }
    except Exception:
        return None
    finally:
        if initialized:
            try:
                nvml.nvmlShutdown()
            except Exception:
                pass
