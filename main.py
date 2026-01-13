"""
DALEX - Agente de Inteligencia Artificial
Soporta modo lite (Fase 3) y pro (Fase 4 con memoria avanzada)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.rutas import router
from api.rutas_documentos import router as router_documentos
from api.rutas_skills import router as router_skills
from config.settings import config
from core.agente import agente
from memoria.base import inicializar_base_datos


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación."""
    # Startup
    print("=" * 50)
    print(f"🚀 {config.nombre} v{config.version}")
    print(f"📋 Modo: {config.modo.upper()}")
    print("=" * 50)
    
    # Base de datos
    inicializar_base_datos()
    
    # Agente
    if not agente.inicializar():
        print("⚠ El agente no pudo inicializarse completamente")
    
    print(f"🌐 API en http://{config.api_host}:{config.api_puerto}")
    print(f"📚 Docs en http://{config.api_host}:{config.api_puerto}/docs")
    print("=" * 50)
    
    yield
    
    # Shutdown
    print(f"👋 Cerrando {config.nombre}...")


# Crear app
app = FastAPI(
    title=config.nombre,
    description=f"Agente de IA - Modo {config.modo}",
    version=config.version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(router, prefix="/api")
app.include_router(router_documentos, prefix="/api")
app.include_router(router_skills, prefix="/api")


@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "nombre": config.nombre,
        "version": config.version,
        "modo": config.modo,
        "estado": "activo",
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "modo": config.modo}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=config.api_host,
        port=config.api_puerto,
        reload=True,
    )
