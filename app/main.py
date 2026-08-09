from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.api.apis import router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (correct way for async)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Clean up on shutdown
    await engine.dispose()

app = FastAPI(
    title="Cookie-based Auth System",
    description="HTTP-only cookie + Access/Refresh tokens + Role-based access",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/")
def root():
    return {"message": "FastAPI Cookie Auth is running"}