from fastapi import FastAPI
from app.core.middleware import register_middleware
from app.core.exception_handlers import register_exception_handlers
from app.core.routers import register_routers

app = FastAPI(
    title="Your API",
    version="1.0.0",
    description="API for patient management and authorization",
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    }
)

register_middleware(app)
register_exception_handlers(app)
register_routers(app)
