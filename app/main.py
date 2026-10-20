from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.articles import router as articles_router
from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.community import router as community_router
from app.api.engagements import router as engagements_router
from app.api.experts import router as experts_router
from app.api.media import router as media_router

app = FastAPI(
    title="IN4 API",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(experts_router)
app.include_router(articles_router)
app.include_router(categories_router)
app.include_router(engagements_router)
app.include_router(community_router)
app.include_router(media_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError) -> JSONResponse:
    errors: dict[str, list[str]] = {}
    for error in exc.errors():
        location = error.get("loc", ())
        field = str(location[-1]) if location else "request"
        errors.setdefault(field, []).append(error["msg"])
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": "Validation failed.", "errors": errors},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "status": "error",
            "message": str(exc.detail),
            "errors": {},
        },
    )


@app.get("/api/health/", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
