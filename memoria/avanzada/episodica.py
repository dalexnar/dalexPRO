"""Memoria episódica: registro de tareas ejecutadas (modo pro)."""

import json
from datetime import datetime
from uuid import uuid4
from typing import List, Optional

from memoria.base import EpisodioMemoria, get_session
from config.settings import config


class MemoriaEpisodica:
    """Registra tareas ejecutadas para aprender de la experiencia."""
    
    def __init__(self):
        self.max_registros = config.memoria_episodica_max
        self._habilitada = config.memoria_episodica_habilitada
    
    @property
    def habilitada(self) -> bool:
        return self._habilitada
    
    def registrar(
        self,
        sesion_id: str,
        intencion: str,
        plan_id: str,
        plan_resumen: str,
        total_pasos: int,
        skills_usadas: List[str],
        exito: bool,
        respuesta: str,
        tiempo: float,
        autocorregidos: int = 0,
        errores: List[str] = None,
    ) -> Optional[str]:
        """Registra un episodio de tarea ejecutada."""
        if not self._habilitada:
            return None
        
        ep_id = str(uuid4())
        
        try:
            with get_session() as db:
                ep = EpisodioMemoria(
                    id=ep_id,
                    sesion_id=sesion_id,
                    intencion=intencion,
                    plan_id=plan_id,
                    plan_resumen=plan_resumen,
                    total_pasos=total_pasos,
                    skills_usadas=json.dumps(skills_usadas),
                    exito=exito,
                    respuesta_resumen=respuesta[:500] if respuesta else "",
                    tiempo_total=tiempo,
                    pasos_autocorregidos=autocorregidos,
                    errores_json=json.dumps(errores or [])
                )
                db.add(ep)
                db.commit()
                self._limpiar_viejos(db)
            return ep_id
        except Exception as e:
            print(f"Error registrando episodio: {e}")
            return None
    
    def buscar_similares(self, intencion: str, limite: int = 5, solo_exito: bool = False) -> List[dict]:
        """Busca episodios similares por palabras clave."""
        if not self._habilitada:
            return []
        
        palabras = set(intencion.lower().split())
        
        try:
            with get_session() as db:
                query = db.query(EpisodioMemoria)
                if solo_exito:
                    query = query.filter(EpisodioMemoria.exito == True)
                
                eps = query.order_by(EpisodioMemoria.timestamp.desc()).limit(100).all()
                
                resultados = []
                for ep in eps:
                    palabras_ep = set(ep.intencion.lower().split())
                    score = len(palabras & palabras_ep)
                    if score > 0:
                        resultados.append({
                            "intencion": ep.intencion,
                            "skills": json.loads(ep.skills_usadas),
                            "exito": ep.exito,
                            "score": score
                        })
                
                resultados.sort(key=lambda x: x["score"], reverse=True)
                return resultados[:limite]
        except Exception as e:
            print(f"Error buscando episodios: {e}")
            return []
    
    def stats(self) -> dict:
        """Estadísticas de memoria episódica."""
        if not self._habilitada:
            return {"habilitada": False}
        
        try:
            with get_session() as db:
                total = db.query(EpisodioMemoria).count()
                ok = db.query(EpisodioMemoria).filter(EpisodioMemoria.exito == True).count()
                return {
                    "habilitada": True,
                    "total": total,
                    "exitosos": ok,
                    "tasa": ok / total if total else 0
                }
        except:
            return {"habilitada": True, "error": "Error obteniendo stats"}
    
    def _limpiar_viejos(self, db):
        """Limpia registros viejos si excede el máximo."""
        try:
            total = db.query(EpisodioMemoria).count()
            if total > self.max_registros:
                viejos = db.query(EpisodioMemoria).order_by(
                    EpisodioMemoria.timestamp.asc()
                ).limit(total - self.max_registros).all()
                for v in viejos:
                    db.delete(v)
                db.commit()
        except:
            pass
