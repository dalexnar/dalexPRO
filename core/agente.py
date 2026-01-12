"""Agente principal de DALEX."""

import time
from dataclasses import dataclass
from typing import Optional, List

from config.settings import config
from integraciones.llm.selector import selector_llm
from memoria import guardar_mensaje, obtener_ultimos_mensajes, registrar_auditoria
from memoria.avanzada import gestor_memoria
from skills.catalogo import CatalogoSkills
from core.planificador import Planificador, Plan, EstadoPlan
from core.ejecutor import EjecutorPlan
from core.gestor_planes import gestor_planes


@dataclass
class ResultadoAgente:
    """Resultado de procesar un mensaje."""
    respuesta: str
    exito: bool
    plan_id: Optional[str] = None
    requiere_aprobacion: bool = False
    skills_usadas: List[str] = None
    tiempo: float = 0


class AgenteDALEX:
    """
    Agente principal de DALEX.
    
    Soporta dos modos:
    - lite: Sin memoria avanzada (Fase 3)
    - pro: Con memoria avanzada (Fase 4)
    """
    
    PALABRAS_APROBACION = ["sí", "si", "yes", "ok", "dale", "adelante", "apruebo", "ejecuta"]
    PALABRAS_RECHAZO = ["no", "cancelar", "rechazar", "cancel", "otro"]
    
    def __init__(self):
        self.catalogo = CatalogoSkills()
        self.planificador = None
        self.ejecutor = None
        self._inicializado = False
    
    def inicializar(self) -> bool:
        """Inicializa el agente."""
        print(f"🚀 Inicializando {config.nombre} v{config.version} (modo: {config.modo})")
        
        # Inicializar LLM
        if not selector_llm.inicializar():
            print("✗ No se pudo conectar con el LLM")
            return False
        
        # Cargar skills
        n_skills = self.catalogo.escanear()
        print(f"✓ Skills cargadas: {n_skills}")
        
        # Inicializar memoria avanzada (solo modo pro)
        if config.es_modo_pro:
            gestor_memoria.inicializar()
        
        # Crear planificador y ejecutor
        memoria = gestor_memoria if config.es_modo_pro else None
        self.planificador = Planificador(selector_llm, self.catalogo)
        self.ejecutor = EjecutorPlan(selector_llm, self.catalogo, memoria)
        
        self._inicializado = True
        print(f"✓ {config.nombre} listo")
        return True
    
    def procesar(self, sesion_id: str, mensaje: str) -> ResultadoAgente:
        """Procesa un mensaje del usuario."""
        if not self._inicializado:
            return ResultadoAgente(
                respuesta="El agente no está inicializado",
                exito=False,
            )
        
        inicio = time.time()
        
        # Guardar mensaje del usuario
        guardar_mensaje(sesion_id, "usuario", mensaje)
        
        # Verificar si hay plan pendiente
        plan_pendiente = gestor_planes.obtener_plan_activo(sesion_id)
        
        if plan_pendiente:
            resultado = self._procesar_respuesta_plan(sesion_id, mensaje, plan_pendiente)
        else:
            resultado = self._generar_y_presentar_plan(sesion_id, mensaje)
        
        resultado.tiempo = time.time() - inicio
        
        # Guardar respuesta del agente
        guardar_mensaje(sesion_id, "agente", resultado.respuesta)
        
        return resultado
    
    def _generar_y_presentar_plan(self, sesion_id: str, mensaje: str) -> ResultadoAgente:
        """Genera un plan y lo presenta al usuario."""
        historial = obtener_ultimos_mensajes(sesion_id, n=10)
        
        # Buscar contexto de memoria (modo pro)
        contexto_memoria = ""
        if config.es_modo_pro and gestor_memoria.activo:
            contexto_memoria = gestor_memoria.buscar_contexto(mensaje)
        
        # Generar plan
        plan = self.planificador.generar_plan(
            sesion_id=sesion_id,
            intencion=mensaje,
            historial=historial[:-1],
            contexto_adicional=contexto_memoria,
        )
        
        gestor_planes.registrar_plan(plan)
        
        registrar_auditoria(
            accion="plan_generado",
            sesion_id=sesion_id,
            detalle={"plan_id": plan.id, "pasos": len(plan.pasos)},
        )
        
        # Verificar si es plan simple (auto-aprobar)
        if self._es_plan_simple(plan):
            gestor_planes.aprobar_plan(plan.id)
            return self._ejecutar_plan(sesion_id, plan)
        
        # Presentar para aprobación
        texto_plan = self.planificador.plan_a_texto(plan)
        
        return ResultadoAgente(
            respuesta=texto_plan,
            exito=True,
            plan_id=plan.id,
            requiere_aprobacion=True,
        )
    
    def _procesar_respuesta_plan(
        self,
        sesion_id: str,
        mensaje: str,
        plan: Plan,
    ) -> ResultadoAgente:
        """Procesa respuesta del usuario a un plan pendiente."""
        mensaje_lower = mensaje.lower().strip()
        
        # Verificar aprobación
        if any(p in mensaje_lower for p in self.PALABRAS_APROBACION):
            gestor_planes.aprobar_plan(plan.id)
            return self._ejecutar_plan(sesion_id, plan)
        
        # Verificar rechazo
        if any(p in mensaje_lower for p in self.PALABRAS_RECHAZO):
            gestor_planes.rechazar_plan(plan.id)
            gestor_planes.limpiar_sesion(sesion_id)
            return ResultadoAgente(
                respuesta="Plan cancelado. ¿En qué más puedo ayudarte?",
                exito=True,
            )
        
        # No es ni aprobación ni rechazo, generar nuevo plan
        gestor_planes.limpiar_sesion(sesion_id)
        return self._generar_y_presentar_plan(sesion_id, mensaje)
    
    def _ejecutar_plan(self, sesion_id: str, plan: Plan) -> ResultadoAgente:
        """Ejecuta un plan aprobado."""
        inicio = time.time()
        
        historial = obtener_ultimos_mensajes(sesion_id, n=10)
        contexto = {"historial": historial}
        
        resultado = self.ejecutor.ejecutar_plan(plan, contexto)

        gestor_planes.limpiar_sesion(sesion_id)

        # Extraer skills usadas
        skills = [p.skill for p in plan.pasos if p.skill]

        # NOTA: El registro en memoria avanzada ahora está centralizado
        # en core/ejecutor.py para funcionar tanto desde el flujo
        # conversacional como desde el endpoint /planes/{id}/aprobar

        return ResultadoAgente(
            respuesta=resultado.respuesta_final,
            exito=resultado.exito,
            plan_id=plan.id,
            skills_usadas=skills,
        )
    
    def _es_plan_simple(self, plan: Plan) -> bool:
        """Determina si un plan es simple (auto-aprobar)."""
        if len(plan.pasos) > 1:
            return False
        
        paso = plan.pasos[0]
        if paso.skill:
            return False
        
        from core.planificador import TipoPaso
        return paso.tipo == TipoPaso.RESPUESTA
    
    def estado(self) -> dict:
        """Estado actual del agente."""
        base = {
            "inicializado": self._inicializado,
            "nombre": config.nombre,
            "version": config.version,
            "modo": config.modo,
            "skills": len(self.catalogo.skills),
            "llm": selector_llm.verificar_disponibilidad(),
        }
        
        if config.es_modo_pro:
            base["memoria"] = gestor_memoria.stats()
        
        if self.ejecutor:
            base["autocorreccion"] = self.ejecutor.autocorrector.stats()
        
        return base


# Instancia global
agente = AgenteDALEX()
