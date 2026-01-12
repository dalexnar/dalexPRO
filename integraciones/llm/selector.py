"""Selector de LLM para DALEX."""

from typing import Optional
from config.settings import config
from integraciones.llm.base import ProveedorLLM, RespuestaLLM
from integraciones.llm.proveedores.ollama import ProveedorOllama


class SelectorLLM:
    """
    Gestiona la selección y uso de proveedores LLM.
    Actualmente solo soporta Ollama, pero extensible.
    """
    
    def __init__(self):
        self._proveedor: Optional[ProveedorLLM] = None
        self._inicializado = False
    
    def inicializar(self) -> bool:
        """Inicializa el proveedor LLM según configuración."""
        if config.ollama_habilitado:
            self._proveedor = ProveedorOllama()
            if self._proveedor.verificar_conexion():
                self._inicializado = True
                print(f"✓ LLM: Ollama ({config.ollama_modelo}) en {config.ollama_url}")
                return True
            else:
                print(f"✗ LLM: Ollama no disponible en {config.ollama_url}")
        
        self._inicializado = False
        return False
    
    def generar(
        self,
        prompt: str,
        sistema: str = None,
        temperatura: float = 0.7,
        max_tokens: int = 2000,
    ) -> RespuestaLLM:
        """Genera una respuesta usando el proveedor disponible."""
        if not self._inicializado or not self._proveedor:
            return RespuestaLLM(
                contenido="",
                modelo="ninguno",
                exito=False,
                error="LLM no inicializado",
            )
        
        return self._proveedor.generar(
            prompt=prompt,
            sistema=sistema,
            temperatura=temperatura,
            max_tokens=max_tokens,
        )
    
    def verificar_disponibilidad(self) -> dict:
        """Verifica disponibilidad de proveedores."""
        return {
            "ollama": self._proveedor.verificar_conexion() if self._proveedor else False,
            "modelo": config.ollama_modelo,
            "url": config.ollama_url,
        }
    
    @property
    def disponible(self) -> bool:
        return self._inicializado


# Instancia global
selector_llm = SelectorLLM()
