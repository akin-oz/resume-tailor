from fastapi import APIRouter

from . import parse, render, tailor

api_router = APIRouter()
api_router.include_router(tailor.router)
api_router.include_router(render.router)
api_router.include_router(parse.router)
