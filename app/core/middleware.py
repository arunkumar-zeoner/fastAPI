from fastapi.middleware.cors import CORSMiddleware
from app.middleware.response_middleware import ResponseMiddleware

def register_middleware(app):
    app.add_middleware(ResponseMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
