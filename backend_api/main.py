from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers.terminacao_router import router as terminacao_router
from routers.imagens_router import router as imagens_router
from routers.dashboard_router import router as dashboard_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API Python (FastAPI) de suporte ao Aplicativo Mobile AgroTop e integração com Supabase.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuração de CORS para permitir acesso seguro do aplicativo Flutter
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos roteadores da API v1
app.include_router(terminacao_router, prefix=settings.API_V1_STR)
app.include_router(imagens_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)

@app.get("/", summary="Health check da API")
async def root():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
