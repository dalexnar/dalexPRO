"""Memoria de errores: autocorrección inteligente (modo pro)."""

import json
import hashlib
from datetime import datetime
from uuid import uuid4
from typing import Optional, Dict

from memoria.base import RegistroErrorMemoria, get_session
from config.settings import config


class MemoriaErrores:
    """Registra errores y soluciones para autocorrección automática."""
    
    def __init__(self):
        self._habilitada = config.memoria_errores_habilitada
        self.max_registros = config.memoria_errores_max
        self.umbral = config.memoria_errores_umbral
    
    @property
    def habilitada(self) -> bool:
        return self._habilitada
    
    def registrar(
        self,
        tipo: str,
        mensaje: str,
        skill: str = None,
        parametros: dict = None,
        estrategia: str = None,
        exito: bool = False,
        detalle: dict = None,
    ) -> Optional[str]:
        """Registra un error y su resultado."""
        if not self._habilitada:
            return None
        
        # Hash para identificar errores similares
        hash_base = f"{tipo}:{skill}:{mensaje[:100]}"
        hash_error = hashlib.sha256(hash_base.encode()).hexdigest()[:64]
        
        try:
            with get_session() as db:
                # Buscar si ya existe
                existe = db.query(RegistroErrorMemoria).filter(
                    RegistroErrorMemoria.hash_error == hash_error
                ).first()
                
                if existe:
                    existe.ocurrencias += 1
                    existe.timestamp = datetime.utcnow()
                    if exito and estrategia:
                        existe.estrategia_usada = estrategia
                        existe.solucion_exitosa = True
                        existe.solucion_detalle_json = json.dumps(detalle or {})
                    db.commit()
                    return existe.id
                
                # Crear nuevo registro
                reg_id = str(uuid4())
                reg = RegistroErrorMemoria(
                    id=reg_id,
                    tipo_error=tipo,
                    mensaje_error=mensaje,
                    hash_error=hash_error,
                    skill=skill,
                    parametros_json=json.dumps(parametros or {}),
                    estrategia_usada=estrategia or "",
                    solucion_exitosa=exito,
                    solucion_detalle_json=json.dumps(detalle or {})
                )
                db.add(reg)
                db.commit()
                self._limpiar_viejos(db)
                return reg_id
                
        except Exception as e:
            print(f"Error registrando en memoria de errores: {e}")
            return None
    
    def buscar_solucion(self, tipo: str, mensaje: str, skill: str = None) -> Optional[Dict]:
        """Busca una solución conocida para un error."""
        if not self._habilitada:
            return None
        
        hash_base = f"{tipo}:{skill}:{mensaje[:100]}"
        hash_error = hashlib.sha256(hash_base.encode()).hexdigest()[:64]
        
        try:
            with get_session() as db:
                reg = db.query(RegistroErrorMemoria).filter(
                    RegistroErrorMemoria.hash_error == hash_error,
                    RegistroErrorMemoria.solucion_exitosa == True
                ).first()
                
                if reg and reg.ocurrencias >= self.umbral:
                    return {
                        "estrategia": reg.estrategia_usada,
                        "detalle": json.loads(reg.solucion_detalle_json),
                        "ocurrencias": reg.ocurrencias,
                        "confianza": min(reg.ocurrencias / 10, 1.0)
                    }
        except Exception as e:
            print(f"Error buscando solución: {e}")
        
        return None
    
    def tiene_solucion(self, tipo: str, mensaje: str, skill: str = None) -> bool:
        """Verifica si hay solución conocida."""
        return self.buscar_solucion(tipo, mensaje, skill) is not None
    
    def stats(self) -> dict:
        """Estadísticas de memoria de errores."""
        if not self._habilitada:
            return {"habilitada": False}
        
        try:
            with get_session() as db:
                total = db.query(RegistroErrorMemoria).count()
                con_sol = db.query(RegistroErrorMemoria).filter(
                    RegistroErrorMemoria.solucion_exitosa == True
                ).count()
                return {
                    "habilitada": True,
                    "total": total,
                    "con_solucion": con_sol,
                    "tasa": con_sol / total if total else 0
                }
        except:
            return {"habilitada": True, "error": "Error obteniendo stats"}
    
    def _limpiar_viejos(self, db):
        """Limpia registros viejos con menos ocurrencias."""
        try:
            total = db.query(RegistroErrorMemoria).count()
            if total > self.max_registros:
                viejos = db.query(RegistroErrorMemoria).order_by(
                    RegistroErrorMemoria.ocurrencias.asc(),
                    RegistroErrorMemoria.timestamp.asc()
                ).limit(total - self.max_registros).all()
                for v in viejos:
                    db.delete(v)
                db.commit()
        except:
            pass
