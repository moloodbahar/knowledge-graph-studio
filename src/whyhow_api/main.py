"""Main entrypoint."""

import logging
import pathlib
from contextlib import asynccontextmanager
from logging import basicConfig
from typing import Annotated, Any

import logfire
from asgi_correlation_id import CorrelationIdMiddleware
from asgi_correlation_id.context import correlation_id
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from dotenv import load_dotenv
import os

from whyhow_api import __version__
from whyhow_api.config import Settings
from whyhow_api.custom_logging import configure_logging
from whyhow_api.database import close_mongo_connection, connect_to_mongo
from whyhow_api.dependencies import get_db, get_settings
from whyhow_api.middleware import RateLimiter
from whyhow_api.routers import (
    chunks, documents, graphs, nodes, queries, rules,
    schemas, tasks, triples, users, workspaces,
)

load_dotenv()
logger = logging.getLogger("whyhow_api.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.dependency_overrides.get(get_settings, get_settings)()
    configure_logging(project_log_level=settings.dev.log_level)
    basicConfig(handlers=[logfire.LogfireLoggingHandler()])
    logger.info("Settings loaded")
    logfire.instrument_pymongo(capture_statement=True)
    connect_to_mongo(uri=settings.mongodb.uri)
    try:
        yield
    finally:
        close_mongo_connection()
        logger.info("Database connection closed")

def create_app() -> FastAPI:
    app = FastAPI(
        title="WhyHow API",
        description="API for WhyHow Knowledge Graph",
        version="1.0.0",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RateLimiter)

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        logger.info("Docs endpoint accessed")
        return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head>
                <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
                <title>WhyHow API - Swagger UI</title>
            </head>
            <body>
                <div id="swagger-ui"></div>
                <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
                <script>
                    window.onload = function() {
                        window.ui = SwaggerUIBundle({
                            url: '/openapi.json',
                            dom_id: '#swagger-ui',
                            presets: [
                                SwaggerUIBundle.presets.apis,
                                SwaggerUIBundle.SwaggerUIStandalonePreset
                            ],
                            layout: "BaseLayout",
                            deepLinking: true
                        });
                    }
                </script>
            </body>
            </html>
        """)

    return app

app = create_app()
logfire.instrument_fastapi(app)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> Response:
    """Handle unhandled exceptions.

    The reason for this is to ensure that all exceptions
    have the correlation ID in the response headers.
    """
    # For debugging and in tests
    # import traceback

    # traceback.print_exception(exc)

    return await http_exception_handler(
        request,
        HTTPException(
            500,
            "Internal Server Error",
            headers={"X-Request-ID": correlation_id.get() or ""},
        ),
    )


app.add_middleware(CorrelationIdMiddleware)
app.include_router(workspaces.router)
app.include_router(schemas.router)
app.include_router(graphs.router)
app.include_router(triples.router)
app.include_router(nodes.router)
app.include_router(documents.router)
app.include_router(chunks.router)
app.include_router(users.router)
app.include_router(queries.router)
app.include_router(rules.router)
app.include_router(tasks.router)


@app.get("/")
def root() -> str:
    """Check if the API is ready to accept traffic."""
    logger.info("Root endpoint accessed")
    return f"Welcome to version {__version__} of the WhyHow API."


@app.get("/db")
async def database(db: AsyncIOMotorDatabase = Depends(get_db)) -> str:
    """Check if the database is connected."""
    ping_response = await db.command("ping")
    if int(ping_response["ok"]) != 1:
        return "Problem connecting to database cluster."
    else:
        return "Connected to database cluster."


@app.get("/settings")
def settings(settings: Annotated[Settings, Depends(get_settings)]) -> Any:
    """Get settings.

    The return type is Any not to put too much
    information in the OpenAPI schema.
    """
    return settings


def locate() -> None:
    """Find absolute path to this file and format for uvicorn."""
    file_path = pathlib.Path(__file__).resolve()
    current_path = pathlib.Path.cwd()

    relative_path = file_path.relative_to(current_path)
    dotted_path = str(relative_path).strip(".py").strip("/").replace("/", ".")

    res = f"{dotted_path}:app"
    print(res)

@app.middleware("http")
async def debug_middleware(request: Request, call_next):
    """Debug middleware to log all requests."""
    logger.info(f"Request path: {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response
