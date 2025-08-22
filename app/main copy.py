from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from app.routers import all_routers

from app.handlers.exception_handlers import (
    validation_exception_handler,
    custom_http_exception_handler,
    http_exception_handler,
    general_exception_handler,
    jwks_exception_handler,
    token_exception_handler
)
from app.middleware.response_middleware import ResponseMiddleware
from app.exceptions.custom_exceptions import CustomHTTPException
from app.exceptions.auth_exceptions import (
    JWKSException,
    TokenExpiredException,
    InvalidTokenException,
    TokenDecodeException,
    MissingTokenClaimException
)

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

# Register middleware
app.add_middleware(ResponseMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(CustomHTTPException, custom_http_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(JWKSException, jwks_exception_handler)
app.add_exception_handler(TokenExpiredException, token_exception_handler)
app.add_exception_handler(InvalidTokenException, token_exception_handler)
app.add_exception_handler(TokenDecodeException, token_exception_handler)
app.add_exception_handler(MissingTokenClaimException, token_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include your routers
# from app.routers import patient_route, authorizer_route
# app.include_router(authorizer_route.router)
# app.include_router(patient_route.router)
for router in all_routers:
    app.include_router(router)


# from fastapi import FastAPI, Depends
# from app.db.database import engine, Base
# from app.routers import authorizer_route
# from app.routers import patient_route

# app = FastAPI()
    
# app.include_router(authorizer_route.router)
# app.include_router(patient_route.router)

# # app.include_router(
# #     patient_route.router,
# #     claims=Depends(lambda: verify_token(email=request.email))
# # )

# # 
# # Startup event:DB connection
# @app.on_event("startup")
# async def startup_event():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#         print("✅ Database connected & tables ready")

