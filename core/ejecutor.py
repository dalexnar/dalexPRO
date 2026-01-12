"""Ejecutor de planes de DALEX."""

import re
import time
from dataclasses import dataclass
from typing import Optional, Dict, List

from core.planificador import Plan, PasoPlan, TipoPaso, EstadoPlan
from core.autocorreccion import Autocorrector


@dataclass
class ResultadoEjecucion:
    """Resultado de ejecutar un plan."""
    exito: bool
    respuesta_final: str
    pasos_ejecutados: int
    pasos_fallidos: int
    pasos_autocorregidos: int
    tiempo_total: float
    explicacion: str


@dataclass
class ResultadoPaso:
    """Resultado de ejecutar un paso."""
    exito: bool
    resultado: str
    tiempo: float
    error: Optional[str] = None
    autocorregido: bool = False


class EjecutorPlan:
    """Ejecuta planes paso a paso."""
    
    def __init__(self, selector_llm, catalogo_skills, gestor_memoria=None):
        self.selector_llm = selector_llm
        self.catalogo = catalogo_skills
        self.gestor_memoria = gestor_memoria
        self.autocorrector = Autocorrector(selector_llm, catalogo_skills, gestor_memoria)
    
    def ejecutar_plan(self, plan: Plan, contexto: dict = None) -> ResultadoEjecucion:
        """Ejecuta un plan completo."""
        if plan.estado != EstadoPlan.APROBADO:
            return ResultadoEjecucion(
                exito=False,
                respuesta_final="Plan no aprobado",
                pasos_ejecutados=0,
                pasos_fallidos=0,
                pasos_autocorregidos=0,
                tiempo_total=0,
                explicacion="El plan debe ser aprobado antes de ejecutar",
            )

        plan.estado = EstadoPlan.EN_EJECUCION
        inicio = time.time()

        # Inicializar contexto si no existe
        if contexto is None:
            contexto = {}

        # Buscar contexto de memoria UNA vez por plan (modo pro)
        if self.gestor_memoria and self.gestor_memoria.activo:
            try:
                contexto_memoria = self.gestor_memoria.buscar_contexto(
                    plan.intencion_original,
                    plan_id=plan.id
                )
                contexto['contexto_memoria'] = contexto_memoria
            except Exception as e:
                # No romper ejecución si falla la búsqueda
                print(f"⚠️ Error buscando contexto de memoria: {e}")
                contexto['contexto_memoria'] = None
        else:
            contexto['contexto_memoria'] = None

        resultados_pasos = {}
        respuesta_final = ""
        pasos_ok = 0
        pasos_fail = 0
        pasos_auto = 0
        
        for paso in plan.pasos:
            resultado = self._ejecutar_con_recuperacion(paso, plan, contexto or {}, resultados_pasos)
            
            if resultado.exito:
                pasos_ok += 1
                resultados_pasos[paso.id] = resultado.resultado
                
                if paso.tipo == TipoPaso.RESPUESTA:
                    respuesta_final = resultado.resultado
                
                if resultado.autocorregido:
                    pasos_auto += 1
            else:
                pasos_fail += 1
                # En caso de fallo, intentar generar respuesta de error
                if not respuesta_final:
                    respuesta_final = f"Error en paso {paso.numero}: {resultado.error}"
        
        tiempo_total = time.time() - inicio
        exito = pasos_fail == 0
        plan.estado = EstadoPlan.COMPLETADO if exito else EstadoPlan.FALLIDO

        # Si no hay respuesta, generar una
        if not respuesta_final and exito:
            respuesta_final = "Plan ejecutado correctamente."

        # Sanitizar idioma: eliminar caracteres CJK si existen
        respuesta_final = self._sanitizar_idioma(respuesta_final)

        # Registrar en memoria avanzada (modo pro) - CENTRALIZADO
        if self.gestor_memoria and self.gestor_memoria.activo:
            try:
                skills = [p.skill for p in plan.pasos if p.skill]
                self.gestor_memoria.registrar_tarea(
                    sesion_id=plan.sesion_id,
                    intencion=plan.intencion_original,
                    plan_id=plan.id,
                    plan_resumen=plan.resumen,
                    total_pasos=len(plan.pasos),
                    skills=skills,
                    exito=exito,
                    respuesta=respuesta_final,
                    tiempo=tiempo_total,
                    autocorregidos=pasos_auto,
                )
            except Exception as e:
                # No romper ejecución si falla el registro
                print(f"⚠️ Error registrando en memoria: {e}")

        return ResultadoEjecucion(
            exito=exito,
            respuesta_final=respuesta_final,
            pasos_ejecutados=pasos_ok,
            pasos_fallidos=pasos_fail,
            pasos_autocorregidos=pasos_auto,
            tiempo_total=tiempo_total,
            explicacion=f"Ejecutados {pasos_ok}/{len(plan.pasos)} pasos en {tiempo_total:.2f}s",
        )
    
    def _ejecutar_con_recuperacion(
        self,
        paso: PasoPlan,
        plan: Plan,
        contexto: dict,
        resultados_previos: dict,
    ) -> ResultadoPaso:
        """Ejecuta un paso con capacidad de recuperación."""
        intentos = 0
        max_intentos = 3
        autocorregido = False
        diagnostico_actual = None
        estrategia_actual = None
        
        while intentos < max_intentos:
            intentos += 1
            
            resultado = self._ejecutar_paso(paso, plan, contexto, resultados_previos)
            
            if resultado.exito:
                # Registrar éxito si hubo autocorrección
                if autocorregido and diagnostico_actual and estrategia_actual:
                    self.autocorrector.registrar_resultado(diagnostico_actual, estrategia_actual, True)
                
                resultado.autocorregido = autocorregido
                return resultado
            
            # Diagnosticar error
            diagnostico = self.autocorrector.diagnosticar(
                error=resultado.error or "Error desconocido",
                skill=paso.skill,
                parametros=paso.parametros,
            )
            diagnostico_actual = diagnostico
            
            if not diagnostico.recuperable:
                self._registrar_error(diagnostico, None, False)
                break
            
            # Generar estrategia
            estrategia = self.autocorrector.generar_estrategia(diagnostico, intentos)
            estrategia_actual = estrategia
            
            if not estrategia or estrategia.accion in ("abortar", "escalar"):
                self._registrar_error(diagnostico, estrategia, False)
                break
            
            if estrategia.accion == "pedir_input":
                # Requiere intervención del usuario
                return ResultadoPaso(
                    exito=False,
                    resultado="",
                    tiempo=0,
                    error=estrategia.parametros.get("mensaje", "Se necesita más información"),
                )
            
            # Aplicar corrección
            autocorregido = True
            if estrategia.accion == "reintentar":
                if "parametros_corregidos" in estrategia.parametros:
                    paso.parametros = estrategia.parametros["parametros_corregidos"]
        
        # Falló todos los intentos
        if diagnostico_actual and estrategia_actual:
            self._registrar_error(diagnostico_actual, estrategia_actual, False)
        
        return ResultadoPaso(
            exito=False,
            resultado="",
            tiempo=0,
            error="Se agotaron los intentos de recuperación",
            autocorregido=autocorregido,
        )
    
    def _ejecutar_paso(
        self,
        paso: PasoPlan,
        plan: Plan,
        contexto: dict,
        resultados_previos: dict,
    ) -> ResultadoPaso:
        """Ejecuta un paso individual."""
        inicio = time.time()
        
        try:
            if paso.tipo == TipoPaso.RESPUESTA:
                resultado = self._ejecutar_respuesta(paso, plan, contexto, resultados_previos)
            elif paso.tipo == TipoPaso.RAZONAMIENTO:
                resultado = self._ejecutar_razonamiento(paso, plan, contexto)
            elif paso.tipo == TipoPaso.SKILL:
                resultado = self._ejecutar_skill(paso, plan, contexto)
            else:
                resultado = f"Tipo de paso no soportado: {paso.tipo}"
            
            return ResultadoPaso(
                exito=True,
                resultado=resultado,
                tiempo=time.time() - inicio,
            )
            
        except Exception as e:
            return ResultadoPaso(
                exito=False,
                resultado="",
                tiempo=time.time() - inicio,
                error=str(e),
            )
    
    def _ejecutar_respuesta(
        self,
        paso: PasoPlan,
        plan: Plan,
        contexto: dict,
        resultados_previos: dict,
    ) -> str:
        """Genera una respuesta usando el LLM."""
        # Construir contexto de pasos previos
        ctx_previos = ""
        if resultados_previos:
            ctx_previos = "\n".join([
                f"- Paso anterior: {v[:200]}" for v in resultados_previos.values()
            ])

        # Inyectar contexto de memoria si existe (modo pro)
        ctx_memoria = ""
        if contexto.get('contexto_memoria'):
            try:
                mem = contexto['contexto_memoria']
                if mem:
                    ctx_memoria = f"\n\nCONTEXTO DE MEMORIA:\n{mem}"
            except Exception as e:
                # No romper si falla la inyección
                print(f"⚠️ Error inyectando contexto de memoria en respuesta: {e}")

        prompt = f"""Responde a la siguiente intención del usuario de forma clara y útil.

INTENCIÓN: {plan.intencion_original}
INSTRUCCIÓN DEL PASO: {paso.descripcion}

{f"CONTEXTO DE PASOS ANTERIORES:{ctx_previos}" if ctx_previos else ""}{ctx_memoria}

Responde directamente, sin explicar que eres una IA ni pedir disculpas."""

        respuesta = self.selector_llm.generar(
            prompt=prompt,
            sistema="Eres un asistente útil y directo. Responde SIEMPRE en español claro y natural.",
            temperatura=0.7,
        )

        if not respuesta.exito:
            raise Exception(respuesta.error or "Error generando respuesta")

        return respuesta.contenido
    
    def _ejecutar_razonamiento(self, paso: PasoPlan, plan: Plan, contexto: dict) -> str:
        """Ejecuta un paso de razonamiento."""
        prompt = f"""Analiza lo siguiente:

INTENCIÓN: {plan.intencion_original}
TAREA: {paso.descripcion}

Proporciona tu análisis de forma concisa."""

        respuesta = self.selector_llm.generar(
            prompt=prompt,
            sistema="Eres un analista preciso. Responde SIEMPRE en español claro y natural.",
            temperatura=0.3,
        )
        
        if not respuesta.exito:
            raise Exception(respuesta.error or "Error en razonamiento")
        
        return respuesta.contenido
    
    def _ejecutar_skill(self, paso: PasoPlan, plan: Plan, contexto: dict) -> str:
        """Ejecuta una skill."""
        skill = self.catalogo.obtener(paso.skill)
        if not skill:
            raise Exception(f"Skill no encontrada: {paso.skill}")

        # Inyectar contexto de memoria si existe (modo pro)
        ctx_memoria = ""
        if contexto.get('contexto_memoria'):
            try:
                mem = contexto['contexto_memoria']
                if mem:
                    ctx_memoria = f"\n\nCONTEXTO DE MEMORIA:\n{mem}"
            except Exception as e:
                # No romper si falla la inyección
                print(f"⚠️ Error inyectando contexto de memoria en skill: {e}")

        # Por ahora, las skills se ejecutan vía LLM
        # En el futuro, cada skill podría tener su propio ejecutor
        prompt = f"""Ejecuta la siguiente skill:

SKILL: {skill.nombre}
DESCRIPCIÓN: {skill.descripcion}
PARÁMETROS: {paso.parametros}
CONTEXTO: {plan.intencion_original}{ctx_memoria}

Proporciona el resultado de ejecutar esta skill."""

        respuesta = self.selector_llm.generar(
            prompt=prompt,
            sistema=f"Eres un ejecutor de la skill '{skill.nombre}'. Responde SIEMPRE en español claro y natural.",
            temperatura=0.5,
        )

        if not respuesta.exito:
            raise Exception(respuesta.error or f"Error ejecutando skill {paso.skill}")

        return respuesta.contenido
    
    def _registrar_error(self, diagnostico, estrategia, exito: bool):
        """Registra error en memoria (modo pro)."""
        if not self.gestor_memoria or not self.gestor_memoria.activo:
            return

        self.gestor_memoria.registrar_error(
            tipo=diagnostico.tipo.value,
            mensaje=diagnostico.mensaje,
            skill=diagnostico.contexto.get("skill"),
            parametros=diagnostico.contexto.get("parametros"),
            estrategia=estrategia.accion if estrategia else None,
            exito=exito,
            detalle=estrategia.parametros if estrategia else None,
        )

    def _sanitizar_idioma(self, respuesta: str) -> str:
        """Detecta y elimina caracteres CJK (chino/japonés/coreano) reescribiendo en español.

        Si la respuesta contiene caracteres CJK, hace un segundo llamado al LLM para
        reescribir completamente en español. Es tolerante a errores: si falla, retorna
        la respuesta original.
        """
        # Detectar caracteres CJK (rangos Unicode principales)
        patron_cjk = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')

        if not patron_cjk.search(respuesta):
            # No hay caracteres CJK, retornar sin cambios
            return respuesta

        try:
            # Hacer segundo llamado para reescribir en español puro
            prompt = f"""La siguiente respuesta contiene texto en chino u otros idiomas.
Reescríbela COMPLETAMENTE en español, eliminando cualquier texto en otros idiomas.
Mantén el significado y la información, pero usa SOLO español.
NO expliques que fue una reescritura ni añadas contenido nuevo.

RESPUESTA ORIGINAL:
{respuesta}

RESPUESTA REESCRITA EN ESPAÑOL:"""

            respuesta_sanitizada = self.selector_llm.generar(
                prompt=prompt,
                sistema="Eres un traductor especializado. Responde SOLO en español, sin mezclar otros idiomas.",
                temperatura=0.3,
            )

            if respuesta_sanitizada.exito and respuesta_sanitizada.contenido:
                return respuesta_sanitizada.contenido.strip()
            else:
                # Si falla, retornar original
                return respuesta

        except Exception:
            # Tolerante a errores: si algo falla, retornar original
            return respuesta
