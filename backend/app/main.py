from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.documents import router as documents_router
from app.config import get_settings
from app.db import init_db

settings = get_settings()
storage_dir = Path(__file__).resolve().parents[1] / 'storage'
storage_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='Wiring Diagram Extraction Platform', version=settings['api_version'])
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings['cors_origins'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

init_db()
app.mount('/storage', StaticFiles(directory=str(storage_dir)), name='storage')
app.include_router(documents_router)


@app.get('/')
async def root():
    return {'message': 'Wiring Diagram Extraction Platform'}
