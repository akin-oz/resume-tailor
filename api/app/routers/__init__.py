from fastapi import APIRouter

from . import render, tailor

api_router = APIRouter()
api_router.include_router(tailor.router)
api_router.include_router(render.router)
