"""Operaciones básicas de memoria (siempre activas)."""

import json
from datetime import datetime
from uuid import uuid4
from typing import Optional

from memoria.base import Sesion, Mensaje, RegistroAuditoria, get_session


def crear_sesion(metadata: dict = None) -> str:
    """Crea una nueva sesión."""
    sesion_id = str(uuid4())
    with get_session() as db:
        sesion = Sesion(
            id=sesion_id,
            metadata_json=json.dumps(metadata or {})
        )
        db.add(sesion)
        db.commit()
    return sesion_id


def obtener_sesion(sesion_id: str) -> Optional[dict]:
    """Obtiene una sesión por ID."""
    with get_session() as db:
        sesion = db.query(Sesion).filter(Sesion.id == sesion_id).first()
        if sesion:
            return {
                "id": sesion.id,
                "creada_en": sesion.creada_en.isoformat(),
                "estado": sesion.estado,
            }
    return None


def guardar_mensaje(sesion_id: str, rol: str, contenido: str, metadata: dict = None) -> str:
    """Guarda un mensaje en una sesión."""
    mensaje_id = str(uuid4())
    
    with get_session() as db:
        # Verificar/crear sesión
        sesion = db.query(Sesion).filter(Sesion.id == sesion_id).first()
        if not sesion:
            sesion = Sesion(id=sesion_id)
            db.add(sesion)
        
        mensaje = Mensaje(
            id=mensaje_id,
            sesion_id=sesion_id,
            rol=rol,
            contenido=contenido,
            metadata_json=json.dumps(metadata or {})
        )
        db.add(mensaje)
        
        # Actualizar timestamp de sesión
        sesion.actualizada_en = datetime.utcnow()
        db.commit()
    
    return mensaje_id


def obtener_ultimos_mensajes(sesion_id: str, n: int = 10) -> list[dict]:
    """Obtiene los últimos N mensajes de una sesión."""
    with get_session() as db:
        mensajes = db.query(Mensaje).filter(
            Mensaje.sesion_id == sesion_id
        ).order_by(Mensaje.creado_en.desc()).limit(n).all()
        
        resultado = []
        for m in reversed(mensajes):
            resultado.append({
                "rol": m.rol,
                "contenido": m.contenido,
                "creado_en": m.creado_en.isoformat(),
            })
        return resultado


def registrar_auditoria(
    accion: str,
    sesion_id: str = None,
    detalle: dict = None,
    duracion_ms: float = None,
    exito: bool = True,
    error: str = None,
) -> int:
    """Registra una acción en auditoría."""
    with get_session() as db:
        registro = RegistroAuditoria(
            sesion_id=sesion_id,
            accion=accion,
            detalle_json=json.dumps(detalle or {}),
            duracion_ms=duracion_ms,
            exito=1 if exito else 0,
            error=error,
        )
        db.add(registro)
        db.commit()
        return registro.id
