from fastapi import FastAPI
from .store import VeraStore
from .routes.system import router as system_router
from .routes.context import router as context_router
from .routes.tick import router as tick_router
from .routes.reply import router as reply_router

def create_app():
    app=FastAPI(title='Vera',version='0.2.0')
    app.state.store=VeraStore()
    app.include_router(system_router)
    app.include_router(context_router)
    app.include_router(tick_router)
    app.include_router(reply_router)
    return app
app=create_app()
