from app.routers import all_routers

def register_routers(app):
    for router in all_routers:
        app.include_router(router)