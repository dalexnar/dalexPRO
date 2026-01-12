"""Gestor de planes de DALEX."""

from typing import Optional, Dict
from core.planificador import Plan, EstadoPlan


class GestorPlanes:
    """Gestiona planes activos por sesión."""
    
    def __init__(self):
        self._planes: Dict[str, Plan] = {}  # plan_id -> Plan
        self._sesiones: Dict[str, str] = {}  # sesion_id -> plan_id
    
    def registrar_plan(self, plan: Plan):
        """Registra un nuevo plan."""
        self._planes[plan.id] = plan
        self._sesiones[plan.sesion_id] = plan.id
    
    def obtener_plan(self, plan_id: str) -> Optional[Plan]:
        """Obtiene un plan por ID."""
        return self._planes.get(plan_id)
    
    def obtener_plan_activo(self, sesion_id: str) -> Optional[Plan]:
        """Obtiene el plan activo de una sesión."""
        plan_id = self._sesiones.get(sesion_id)
        if plan_id:
            plan = self._planes.get(plan_id)
            if plan and plan.estado == EstadoPlan.PENDIENTE:
                return plan
        return None
    
    def aprobar_plan(self, plan_id: str) -> bool:
        """Aprueba un plan."""
        plan = self._planes.get(plan_id)
        if plan and plan.estado == EstadoPlan.PENDIENTE:
            plan.estado = EstadoPlan.APROBADO
            return True
        return False
    
    def rechazar_plan(self, plan_id: str, razon: str = None) -> bool:
        """Rechaza un plan."""
        plan = self._planes.get(plan_id)
        if plan and plan.estado == EstadoPlan.PENDIENTE:
            plan.estado = EstadoPlan.RECHAZADO
            return True
        return False
    
    def limpiar_sesion(self, sesion_id: str):
        """Limpia el plan de una sesión."""
        plan_id = self._sesiones.pop(sesion_id, None)
        if plan_id:
            self._planes.pop(plan_id, None)


# Instancia global
gestor_planes = GestorPlanes()
