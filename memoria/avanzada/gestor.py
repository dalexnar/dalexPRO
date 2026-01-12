"""Gestor central de memoria avanzada (modo pro)."""

from typing import Optional, List

from config.settings import config
from memoria.avanzada.episodica import MemoriaEpisodica
from memoria.avanzada.semantica import MemoriaSemantica
from memoria.avanzada.errores import MemoriaErrores


class GestorMemoriaAvanzada:
    """
    Gestor que coordina las memorias avanzadas.
    Solo se activa en modo 'pro'.
    """
    
    def __init__(self):
        self._modo_pro = config.es_modo_pro
        
        # Crear instancias solo si estamos en modo pro
        if self._modo_pro:
            self.episodica = MemoriaEpisodica()
            self.semantica = MemoriaSemantica()
            self.errores = MemoriaErrores()
        else:
            self.episodica = None
            self.semantica = None
            self.errores = None
        
        self._inicializado = False
    
    @property
    def activo(self) -> bool:
        """Indica si la memoria avanzada está activa."""
        return self._modo_pro and self._inicializado
    
    def inicializar(self) -> bool:
        """Inicializa las memorias avanzadas."""
        if not self._modo_pro:
            print("ℹ Memoria avanzada desactivada (modo lite)")
            return False
        
        print("Inicializando memoria avanzada (modo pro)...")
        
        # Episódica siempre funciona (usa SQLite)
        if self.episodica and self.episodica.habilitada:
            print("  ✓ Memoria episódica activa")
        
        # Semántica puede fallar (ChromaDB opcional)
        if self.semantica:
            self.semantica.inicializar()
        
        # Errores siempre funciona (usa SQLite)
        if self.errores and self.errores.habilitada:
            print("  ✓ Memoria de errores activa")
        
        self._inicializado = True
        return True
    
    def registrar_tarea(
        self,
        sesion_id: str,
        intencion: str,
        plan_id: str,
        plan_resumen: str,
        total_pasos: int,
        skills: List[str],
        exito: bool,
        respuesta: str,
        tiempo: float,
        autocorregidos: int = 0,
        errores: List[str] = None,
    ):
        """Registra una tarea completada en todas las memorias."""
        if not self.activo:
            return

        # Memoria episódica
        if self.episodica and self.episodica.habilitada:
            self.episodica.registrar(
                sesion_id, intencion, plan_id, plan_resumen,
                total_pasos, skills, exito, respuesta, tiempo,
                autocorregidos, errores
            )

        # Memoria semántica (ahora con plan_id para evitar autocitación)
        if self.semantica and self.semantica.habilitada:
            self.semantica.agregar_episodio(intencion, respuesta, skills, exito, plan_id)
    
    def registrar_error(
        self,
        tipo: str,
        mensaje: str,
        skill: str = None,
        parametros: dict = None,
        estrategia: str = None,
        exito: bool = False,
        detalle: dict = None,
    ):
        """Registra un error y su resolución."""
        if not self.activo or not self.errores:
            return
        
        self.errores.registrar(tipo, mensaje, skill, parametros, estrategia, exito, detalle)
    
    def buscar_contexto(self, mensaje: str, plan_id: str = None) -> str:
        """Busca contexto relevante para una intención."""
        if not self.activo:
            return ""

        partes = []

        # Contexto semántico (con filtro anti-autocitación)
        if self.semantica and self.semantica.habilitada:
            ctx = self.semantica.buscar_contexto(mensaje, plan_id=plan_id)
            if ctx:
                partes.append(ctx)

        # Episodios similares
        if self.episodica and self.episodica.habilitada:
            eps = self.episodica.buscar_similares(mensaje, limite=2, solo_exito=True)
            if eps:
                lineas = ["Tareas similares exitosas:"]
                for e in eps:
                    skills_str = ', '.join(e['skills']) if e['skills'] else 'ninguna'
                    lineas.append(f"- {e['intencion'][:60]} → Skills: {skills_str}")
                partes.append("\n".join(lineas))

        return "\n\n".join(partes) if partes else ""
    
    def buscar_solucion_error(self, tipo: str, mensaje: str, skill: str = None) -> Optional[dict]:
        """Busca solución conocida para un error."""
        if not self.activo or not self.errores:
            return None
        return self.errores.buscar_solucion(tipo, mensaje, skill)
    
    def stats(self) -> dict:
        """Estadísticas consolidadas."""
        if not self._modo_pro:
            return {"modo": "lite", "memoria_avanzada": False}
        
        return {
            "modo": "pro",
            "memoria_avanzada": True,
            "episodica": self.episodica.stats() if self.episodica else None,
            "semantica": self.semantica.stats() if self.semantica else None,
            "errores": self.errores.stats() if self.errores else None,
        }


# Instancia global
gestor_memoria = GestorMemoriaAvanzada()
