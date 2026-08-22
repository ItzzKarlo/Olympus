from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


RESERVED_PREFIXES = ("api", "ws")


def install_display_routes(app: FastAPI, directory: Path | None) -> None:
    """Serve one built Display without allowing SPA fallback to consume APIs."""
    display_dir = directory.resolve() if directory is not None else None
    assets_dir = display_dir / "assets" if display_dir is not None else None
    if assets_dir is not None:
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir, check_dir=False),
            name="display-assets",
        )

    def index_response() -> Response:
        index = display_dir / "index.html" if display_dir is not None else None
        if index is None or not index.is_file():
            return JSONResponse(
                status_code=503,
                content={"detail": "Olympus Display production assets are not installed"},
            )
        return FileResponse(index, media_type="text/html")

    @app.get("/", include_in_schema=False, response_model=None)
    async def display_index() -> Response:
        return index_response()

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    async def display_spa(path: str) -> Response:
        first_segment = path.partition("/")[0]
        if first_segment in RESERVED_PREFIXES:
            raise HTTPException(status_code=404, detail="Not found")
        if display_dir is not None:
            requested = (display_dir / path).resolve()
            if requested.is_relative_to(display_dir) and requested.is_file():
                return FileResponse(requested)
        return index_response()
