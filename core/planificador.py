"""Planificador de DALEX."""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from uuid import uuid4


class EstadoPlan(str, Enum):
    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    EN_EJECUCION = "en_ejecucion"
    COMPLETADO = "completado"
    FALLIDO = "fallido"


class TipoPaso(str, Enum):
    RAZONAMIENTO = "razonamiento"
    SKILL = "skill"
    RESPUESTA = "respuesta"


@dataclass
class PasoPlan:
    """Un paso individual en el plan."""
    id: str
    numero: int
    tipo: TipoPaso
    descripcion: str
    skill: Optional[str] = None
    parametros: dict = field(default_factory=dict)
    requiere_aprobacion: bool = False
    estado: str = "pendiente"
    resultado: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "numero": self.numero,
            "tipo": self.tipo.value,
            "descripcion": self.descripcion,
            "skill": self.skill,
            "parametros": self.parametros,
            "estado": self.estado,
        }


@dataclass
class Plan:
    """Plan de ejecución completo."""
    id: str
    sesion_id: str
    intencion_original: str
    resumen: str
    pasos: List[PasoPlan]
    estado: EstadoPlan = EstadoPlan.PENDIENTE
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sesion_id": self.sesion_id,
            "intencion": self.intencion_original,
            "resumen": self.resumen,
            "estado": self.estado.value,
            "pasos": [p.to_dict() for p in self.pasos],
        }


class Planificador:
    """Genera planes de ejecución."""
    
    PROMPT_PLANIFICACION = """Genera un plan para ejecutar la siguiente intención del usuario.

INTENCIÓN: {intencion}

SKILLS DISPONIBLES:
{skills}

{contexto_adicional}

Responde SOLO con JSON válido:
{{
    "resumen": "descripción breve del plan",
    "pasos": [
        {{
            "tipo": "razonamiento|skill|respuesta",
            "descripcion": "qué hace este paso",
            "skill": "nombre_skill o null",
            "parametros": {{}}
        }}
    ]
}}

REGLAS:
- Para preguntas simples, un solo paso tipo "respuesta" es suficiente
- Solo usa skills que estén en la lista
- El JSON debe ser válido"""

    def __init__(self, selector_llm, catalogo_skills):
        self.selector_llm = selector_llm
        self.catalogo = catalogo_skills
    
    def generar_plan(
        self,
        sesion_id: str,
        intencion: str,
        historial: List[dict] = None,
        contexto_adicional: str = None,
    ) -> Plan:
        """Genera un plan para una intención."""
        skills_str = self.catalogo.obtener_para_prompt()

        # ============================
        # FASE 4.1: Inyección de Memoria Semántica (ChromaDB)
        # ============================

        contexto_memoria = ""

        # Solo si existe memoria y está disponible (modo PRO)
        if hasattr(self, "memoria") and self.memoria and self.memoria.semantica_disponible():
            try:
                resultados = self.memoria.buscar(intencion, limite=3)

                if resultados:
                    fragmentos = []
                    for r in resultados:
                        contenido = r.get("contenido") or r.get("texto") or str(r)
                        fragmentos.append(f"- {contenido}")

                    contexto_memoria = "\n".join(fragmentos)

            except Exception as e:
                print(f"[WARN] Error consultando memoria semántica: {e}")

        ctx = ""
        if contexto_memoria:
            ctx += f"\nCONTEXTO DE EXPERIENCIAS PREVIAS:\n{contexto_memoria}\n"

        if contexto_adicional:
            ctx += f"\nCONTEXTO ADICIONAL:\n{contexto_adicional}"

        prompt = self.PROMPT_PLANIFICACION.format(
            intencion=intencion,
            skills=skills_str,
            contexto_adicional=ctx,
        )


        
        respuesta = self.selector_llm.generar(
            prompt=prompt,
            sistema="Eres un planificador preciso. Responde SOLO con JSON válido.",
            temperatura=0.3,
        )
        
        plan_datos = self._parsear_json(respuesta.contenido)
        
        plan_id = str(uuid4())
        pasos = []
        
        for i, paso_datos in enumerate(plan_datos.get("pasos", [])):
            tipo_str = paso_datos.get("tipo", "respuesta")
            try:
                tipo = TipoPaso(tipo_str)
            except ValueError:
                tipo = TipoPaso.RESPUESTA
            
            paso = PasoPlan(
                id=f"{plan_id}-{i+1}",
                numero=i + 1,
                tipo=tipo,
                descripcion=paso_datos.get("descripcion", ""),
                skill=paso_datos.get("skill"),
                parametros=paso_datos.get("parametros", {}),
            )
            pasos.append(paso)
        
        # Si no hay pasos, crear uno de respuesta por defecto
        if not pasos:
            pasos.append(PasoPlan(
                id=f"{plan_id}-1",
                numero=1,
                tipo=TipoPaso.RESPUESTA,
                descripcion="Responder directamente al usuario",
            ))
        
        return Plan(
            id=plan_id,
            sesion_id=sesion_id,
            intencion_original=intencion,
            resumen=plan_datos.get("resumen", "Plan generado"),
            pasos=pasos,
        )
    
    def plan_a_texto(self, plan: Plan) -> str:
        """Convierte un plan a texto legible."""
        lineas = [
            f"📋 **Plan: {plan.resumen}**",
            "",
            "Pasos:",
        ]
        
        for paso in plan.pasos:
            icono = "🤔" if paso.tipo == TipoPaso.RAZONAMIENTO else "⚡" if paso.tipo == TipoPaso.SKILL else "💬"
            skill_info = f" [{paso.skill}]" if paso.skill else ""
            lineas.append(f"{paso.numero}. {icono} {paso.descripcion}{skill_info}")
        
        lineas.append("")
        lineas.append("¿Apruebas este plan? (sí/no)")
        
        return "\n".join(lineas)
    
    def _parsear_json(self, texto: str) -> dict:
        """Extrae JSON de una respuesta."""
        try:
            inicio = texto.find("{")
            fin = texto.rfind("}") + 1
            if inicio >= 0 and fin > inicio:
                return json.loads(texto[inicio:fin])
        except json.JSONDecodeError:
            pass
        return {"pasos": []}
