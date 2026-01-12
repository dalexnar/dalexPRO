"""Autocorrección de DALEX."""

import json
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class TipoError(str, Enum):
    SKILL_NO_ENCONTRADA = "skill_no_encontrada"
    PARAMETRO_FALTANTE = "parametro_faltante"
    PARAMETRO_INVALIDO = "parametro_invalido"
    TIMEOUT = "timeout"
    LLM_ERROR = "llm_error"
    DESCONOCIDO = "desconocido"


@dataclass
class DiagnosticoError:
    """Diagnóstico de un error."""
    tipo: TipoError
    mensaje: str
    recuperable: bool
    contexto: dict


@dataclass
class EstrategiaRecuperacion:
    """Estrategia para recuperarse de un error."""
    descripcion: str
    accion: str  # reintentar, skill_alternativa, pedir_input, escalar, abortar
    parametros: dict
    probabilidad_exito: float


class Autocorrector:
    """Analiza errores y genera estrategias de recuperación."""
    
    def __init__(self, selector_llm, catalogo_skills, gestor_memoria=None):
        self.selector_llm = selector_llm
        self.catalogo = catalogo_skills
        self.gestor_memoria = gestor_memoria  # Solo en modo pro
        self.historial_errores: List[DiagnosticoError] = []
        self.max_reintentos = 3
        
        # Estadísticas de memoria
        self._soluciones_memoria_aplicadas = 0
        self._soluciones_memoria_exitosas = 0
    
    def diagnosticar(
        self,
        error: str,
        skill: str = None,
        parametros: dict = None,
        paso: str = None,
    ) -> DiagnosticoError:
        """Diagnostica un error."""
        # Clasificación rápida sin LLM
        diagnostico = self._clasificacion_rapida(error, skill, parametros)
        if diagnostico:
            self.historial_errores.append(diagnostico)
            return diagnostico
        
        # Default
        diagnostico = DiagnosticoError(
            tipo=TipoError.DESCONOCIDO,
            mensaje=error,
            recuperable=False,
            contexto={"skill": skill, "parametros": parametros},
        )
        self.historial_errores.append(diagnostico)
        return diagnostico
    
    def generar_estrategia(
        self,
        diagnostico: DiagnosticoError,
        intentos_previos: int = 0,
    ) -> Optional[EstrategiaRecuperacion]:
        """Genera estrategia de recuperación."""
        if not diagnostico.recuperable:
            return None
        
        if intentos_previos >= self.max_reintentos:
            return EstrategiaRecuperacion(
                descripcion="Máximo de reintentos alcanzado",
                accion="escalar",
                parametros={},
                probabilidad_exito=0,
            )
        
        # Modo pro: consultar memoria de errores primero
        if self.gestor_memoria and self.gestor_memoria.activo:
            estrategia = self._buscar_en_memoria(diagnostico)
            if estrategia:
                self._soluciones_memoria_aplicadas += 1
                return estrategia
        
        # Estrategias por tipo de error
        if diagnostico.tipo == TipoError.SKILL_NO_ENCONTRADA:
            return EstrategiaRecuperacion(
                descripcion="Buscar skill alternativa",
                accion="skill_alternativa",
                parametros={},
                probabilidad_exito=0.5,
            )
        
        if diagnostico.tipo == TipoError.PARAMETRO_FALTANTE:
            return EstrategiaRecuperacion(
                descripcion="Solicitar parámetro al usuario",
                accion="pedir_input",
                parametros={"mensaje": f"Necesito más información: {diagnostico.mensaje}"},
                probabilidad_exito=0.9,
            )
        
        if diagnostico.tipo == TipoError.TIMEOUT:
            return EstrategiaRecuperacion(
                descripcion="Reintentar con más tiempo",
                accion="reintentar",
                parametros={"timeout_multiplicador": 2},
                probabilidad_exito=0.6,
            )
        
        # Default: reintentar una vez
        if intentos_previos == 0:
            return EstrategiaRecuperacion(
                descripcion="Reintentar",
                accion="reintentar",
                parametros={},
                probabilidad_exito=0.4,
            )
        
        return None
    
    def _clasificacion_rapida(
        self,
        error: str,
        skill: str,
        parametros: dict,
    ) -> Optional[DiagnosticoError]:
        """Clasifica errores comunes sin LLM."""
        error_lower = error.lower()
        
        if "no encontrada" in error_lower or "not found" in error_lower:
            return DiagnosticoError(
                tipo=TipoError.SKILL_NO_ENCONTRADA,
                mensaje=error,
                recuperable=True,
                contexto={"skill": skill},
            )
        
        if "falta" in error_lower or "requerido" in error_lower:
            return DiagnosticoError(
                tipo=TipoError.PARAMETRO_FALTANTE,
                mensaje=error,
                recuperable=True,
                contexto={"parametros": parametros},
            )
        
        if "timeout" in error_lower:
            return DiagnosticoError(
                tipo=TipoError.TIMEOUT,
                mensaje=error,
                recuperable=True,
                contexto={},
            )
        
        return None
    
    def _buscar_en_memoria(self, diagnostico: DiagnosticoError) -> Optional[EstrategiaRecuperacion]:
        """Busca solución en memoria de errores (modo pro)."""
        if not self.gestor_memoria:
            return None
        
        skill = diagnostico.contexto.get("skill")
        solucion = self.gestor_memoria.buscar_solucion_error(
            tipo=diagnostico.tipo.value,
            mensaje=diagnostico.mensaje,
            skill=skill
        )
        
        if solucion and solucion.get("confianza", 0) >= 0.5:
            return EstrategiaRecuperacion(
                descripcion=f"Solución conocida ({solucion['ocurrencias']} veces antes)",
                accion=solucion["estrategia"],
                parametros=solucion.get("detalle", {}),
                probabilidad_exito=solucion["confianza"],
            )
        
        return None
    
    def registrar_resultado(
        self,
        diagnostico: DiagnosticoError,
        estrategia: EstrategiaRecuperacion,
        exito: bool,
    ):
        """Registra resultado de estrategia en memoria (modo pro)."""
        if not self.gestor_memoria or not self.gestor_memoria.activo:
            return
        
        self.gestor_memoria.registrar_error(
            tipo=diagnostico.tipo.value,
            mensaje=diagnostico.mensaje,
            skill=diagnostico.contexto.get("skill"),
            parametros=diagnostico.contexto.get("parametros"),
            estrategia=estrategia.accion,
            exito=exito,
            detalle=estrategia.parametros,
        )
        
        if exito:
            self._soluciones_memoria_exitosas += 1
    
    def stats(self) -> dict:
        """Estadísticas de autocorrección."""
        base = {
            "total_errores": len(self.historial_errores),
            "recuperables": sum(1 for d in self.historial_errores if d.recuperable),
        }
        
        # Stats de memoria (modo pro)
        base["memoria"] = {
            "soluciones_aplicadas": self._soluciones_memoria_aplicadas,
            "soluciones_exitosas": self._soluciones_memoria_exitosas,
        }
        
        return base
    
    def limpiar(self):
        """Limpia historial."""
        self.historial_errores = []
        self._soluciones_memoria_aplicadas = 0
        self._soluciones_memoria_exitosas = 0
