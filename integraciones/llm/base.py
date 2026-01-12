"""Interfaces base para proveedores LLM."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class RespuestaLLM:
    """Respuesta de un LLM."""
    contenido: str
    modelo: str
    tokens_entrada: int = 0
    tokens_salida: int = 0
    tiempo_ms: float = 0
    exito: bool = True
    error: Optional[str] = None


class ProveedorLLM(ABC):
    """Interfaz base para proveedores de LLM."""
    
    @abstractmethod
    def generar(
        self,
        prompt: str,
        sistema: str = None,
        temperatura: float = 0.7,
        max_tokens: int = 2000,
    ) -> RespuestaLLM:
        """Genera una respuesta."""
        pass
    
    @abstractmethod
    def verificar_conexion(self) -> bool:
        """Verifica si el proveedor está disponible."""
        pass
    
    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre del proveedor."""
        pass
