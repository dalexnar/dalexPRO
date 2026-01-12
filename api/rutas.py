
"""Rutas de la API de DALEX."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.agente import agente
from core.gestor_planes import gestor_planes
from memoria import crear_sesion, obtener_sesion
from memoria.avanzada import gestor_memoria
from config.settings import config

router = APIRouter()


# === MODELOS ===

class MensajeRequest(BaseModel):
    mensaje: str
    sesion_id: Optional[str] = None


class MensajeResponse(BaseModel):
    respuesta: str
    sesion_id: str
    exito: bool
    plan_id: Optional[str] = None
    requiere_aprobacion: bool = False
    tiempo: float = 0


# === ENDPOINTS PRINCIPALES ===

@router.post("/mensajes", response_model=MensajeResponse, tags=["Chat"])
async def enviar_mensaje(request: MensajeRequest):
    """Envía un mensaje al agente."""
    # Obtener o crear sesión
    sesion_id = request.sesion_id
    if not sesion_id:
        sesion_id = crear_sesion()
    elif not obtener_sesion(sesion_id):
        sesion_id = crear_sesion()
    
    # Procesar mensaje
    resultado = agente.procesar(sesion_id, request.mensaje)
    
    return MensajeResponse(
        respuesta=resultado.respuesta,
        sesion_id=sesion_id,
        exito=resultado.exito,
        plan_id=resultado.plan_id,
        requiere_aprobacion=resultado.requiere_aprobacion,
        tiempo=resultado.tiempo,
    )


@router.get("/estado", tags=["Sistema"])
async def obtener_estado():
    """Estado actual del agente."""
    return agente.estado()


@router.get("/config", tags=["Sistema"])
async def obtener_config():
    """Configuración actual."""
    return config.resumen()


# === ENDPOINTS DE SKILLS ===

@router.get("/skills", tags=["Skills"])
async def listar_skills():
    """Lista las skills disponibles."""
    return {"skills": agente.catalogo.listar()}


# === ENDPOINTS DE PLANES ===

@router.get("/planes/{plan_id}", tags=["Planes"])
async def obtener_plan(plan_id: str):
    """Obtiene un plan por ID."""
    plan = gestor_planes.obtener_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return plan.to_dict()


@router.post("/planes/{plan_id}/aprobar", tags=["Planes"])
async def aprobar_plan(plan_id: str):
    """Aprueba un plan pendiente."""
    plan = gestor_planes.obtener_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    
    if plan.estado.value != "pendiente":
        raise HTTPException(status_code=400, detail=f"Plan no está pendiente: {plan.estado.value}")
    
    gestor_planes.aprobar_plan(plan_id)
    
    # Ejecutar plan
    resultado = agente.ejecutor.ejecutar_plan(plan)
    gestor_planes.limpiar_sesion(plan.sesion_id)
    
    return {
        "exito": resultado.exito,
        "respuesta": resultado.respuesta_final,
        "tiempo": resultado.tiempo_total,
    }


@router.post("/planes/{plan_id}/rechazar", tags=["Planes"])
async def rechazar_plan(plan_id: str, razon: str = None):
    """Rechaza un plan pendiente."""
    plan = gestor_planes.obtener_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    
    if plan.estado.value != "pendiente":
        raise HTTPException(status_code=400, detail=f"Plan no está pendiente: {plan.estado.value}")
    
    gestor_planes.rechazar_plan(plan_id, razon)
    gestor_planes.limpiar_sesion(plan.sesion_id)
    
    return {"mensaje": "Plan rechazado"}


# === ENDPOINTS DE MEMORIA (solo modo pro) ===

@router.get("/memoria/estadisticas", tags=["Memoria"])
async def estadisticas_memoria():
    """Estadísticas de memoria avanzada (solo modo pro)."""
    return gestor_memoria.stats()


@router.get("/memoria/buscar", tags=["Memoria"])
async def buscar_memoria(q: str, limite: int = 5):
    """Busca en memoria semántica (solo modo pro)."""
    if not config.es_modo_pro:
        return {"error": "Solo disponible en modo pro"}
    
    if not gestor_memoria.semantica or not gestor_memoria.semantica.habilitada:
        return {"error": "Memoria semántica no disponible"}
    
    resultados = gestor_memoria.semantica.buscar(q, limite)
    return {"consulta": q, "resultados": resultados}

@router.get("/llm/info", tags=["Sistema"])
async def obtener_info_llm():
    """Información del LLM configurado."""
    from integraciones.llm.selector import selector_llm

    info = {
        "proveedor": "ollama",
        "host": config.ollama_url,
        "modelo": config.ollama_modelo,
        "disponible": selector_llm.disponible,
        "habilitado": config.ollama_habilitado,
    }

    if selector_llm.disponible:
        disponibilidad = selector_llm.verificar_disponibilidad()
        info.update(disponibilidad)

    return info
