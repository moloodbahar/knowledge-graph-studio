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
from fastapi.responses import Response, JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from whyhow_api import __version__
from whyhow_api.config import Settings
from whyhow_api.custom_logging import configure_logging
from whyhow_api.database import close_mongo_connection, connect_to_mongo
from whyhow_api.dependencies import get_db, get_settings
from whyhow_api.middleware import RateLimiter
from fastapi.responses import FileResponse
import os
from whyhow_api.routers import (
    chunks, documents, graphs, nodes, queries, rules,
    schemas, tasks, triples, users, workspaces,
)

logger = logging.getLogger("whyhow_api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Read environment (settings of the application)."""
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


app = FastAPI(
    title="WhyHow API",
    summary="RAG with knowledge graphs",
    version=__version__,
    lifespan=lifespan,
    openapi_url=get_settings().dev.openapi_url,
)
logfire.instrument_fastapi(app)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> Response:
    """Handle unhandled exceptions.

    The reason for this is to ensure that all exceptions
    have the correlation ID in the response headers.
    """
    return await http_exception_handler(
        request,
        HTTPException(
            500,
            "Internal Server Error",
            headers={"X-Request-ID": correlation_id.get() or ""},
        ),
    )


app.add_middleware(RateLimiter)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
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

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(
        os.path.join('static', 'favicon.ico'),  # Adjust path as needed
        media_type='image/x-icon'
    )


def locate() -> None:
    """Find absolute path to this file and format for uvicorn."""
    file_path = pathlib.Path(__file__).resolve()
    current_path = pathlib.Path.cwd()

    relative_path = file_path.relative_to(current_path)
    dotted_path = str(relative_path).strip(".py").strip("/").replace("/", ".")

    res = f"{dotted_path}:app"
    print(res)

@app.on_event("startup")
async def startup_event():
    print("\nAvailable routes:")
    for route in app.routes:
        if hasattr(route, "methods"):
            print(f"{route.methods} {route.path}")
    print("\n")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Request: {request.method} {request.url}")
    logger.debug(f"Headers: {request.headers}")
    try:
        response = await call_next(request)
        logger.debug(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.exception("Error processing request")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

@app.get("/workspaces")
async def get_workspaces():
    try:
        # Your existing code here
        logger.debug("Processing get_workspaces request")
        # ... rest of the code
    except Exception as e:
        logger.exception("Error in get_workspaces")
        raise
