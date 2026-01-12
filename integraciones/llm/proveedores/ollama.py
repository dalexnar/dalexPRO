"""Proveedor Ollama para DALEX."""

import time
import httpx
from typing import Optional

from integraciones.llm.base import ProveedorLLM, RespuestaLLM
from config.settings import config


class ProveedorOllama(ProveedorLLM):
    """Proveedor de LLM usando Ollama local."""
    
    def __init__(self, url: str = None, modelo: str = None, timeout: int = None):
        # Prioridad: parámetro > config (que ya aplica ENV > YAML)
        self.url = url or config.ollama_url
        self.modelo = modelo or config.ollama_modelo
        self.timeout = timeout or config.timeout_llm
        self._disponible = None
    
    @property
    def nombre(self) -> str:
        return "ollama"
    
    def verificar_conexion(self) -> bool:
        """Verifica conexión con Ollama."""
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.url}/api/tags")
                if resp.status_code == 200:
                    # Verificar que el modelo existe
                    modelos = resp.json().get("models", [])
                    nombres = [m.get("name", "").split(":")[0] for m in modelos]
                    modelo_base = self.modelo.split(":")[0]
                    
                    if modelo_base in nombres or self.modelo in [m.get("name") for m in modelos]:
                        self._disponible = True
                        return True
                    
                    print(f"⚠ Modelo '{self.modelo}' no encontrado en Ollama")
                    print(f"  Modelos disponibles: {nombres}")
                    print(f"  Ejecuta: ollama pull {self.modelo}")
                    self._disponible = False
                    return False
                    
        except Exception as e:
            print(f"✗ Error conectando a Ollama ({self.url}): {e}")
            self._disponible = False
        return False
    
    def generar(
        self,
        prompt: str,
        sistema: str = None,
        temperatura: float = 0.7,
        max_tokens: int = 2000,
    ) -> RespuestaLLM:
        """Genera respuesta usando Ollama."""
        inicio = time.time()
        
        mensajes = []
        if sistema:
            mensajes.append({"role": "system", "content": sistema})
        mensajes.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.modelo,
            "messages": mensajes,
            "stream": False,
            "options": {
                "temperature": temperatura,
                "num_predict": max_tokens,
            }
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.url}/api/chat", json=payload)
                
                if resp.status_code == 200:
                    data = resp.json()
                    contenido = data.get("message", {}).get("content", "")
                    
                    return RespuestaLLM(
                        contenido=contenido,
                        modelo=self.modelo,
                        tokens_entrada=data.get("prompt_eval_count", 0),
                        tokens_salida=data.get("eval_count", 0),
                        tiempo_ms=(time.time() - inicio) * 1000,
                        exito=True,
                    )
                else:
                    return RespuestaLLM(
                        contenido="",
                        modelo=self.modelo,
                        tiempo_ms=(time.time() - inicio) * 1000,
                        exito=False,
                        error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    )
                    
        except httpx.TimeoutException:
            return RespuestaLLM(
                contenido="",
                modelo=self.modelo,
                tiempo_ms=(time.time() - inicio) * 1000,
                exito=False,
                error=f"Timeout después de {self.timeout}s",
            )
        except Exception as e:
            return RespuestaLLM(
                contenido="",
                modelo=self.modelo,
                tiempo_ms=(time.time() - inicio) * 1000,
                exito=False,
                error=str(e),
            )
