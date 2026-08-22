import uvicorn

from olympus_core.config import load_core_config


def main() -> int:
    settings = load_core_config()
    uvicorn.run(
        "olympus_core.main:app",
        host=settings.server.host,
        port=settings.server.port,
        workers=1,
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
