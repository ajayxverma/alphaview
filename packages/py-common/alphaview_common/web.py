from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alphaview_common.settings import get_common_settings


def create_app(title: str, lifespan=None) -> FastAPI:
    s = get_common_settings()
    app = FastAPI(
        title=title,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if s.env != "production" else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": title}

    return app
