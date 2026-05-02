from fastapi import APIRouter

from . import tailor

api_router = APIRouter()
api_router.include_router(tailor.router)
