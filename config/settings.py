"""
Configuración de DALEX.
PRIORIDAD: Variables de entorno > YAML > Defaults
"""

import os
from pathlib import Path
from typing import Optional
import yaml


class Config:
    """Configuración centralizada con prioridad ENV > YAML."""
    
    def __init__(self):
        self._yaml_data = {}
        self._cargar_yaml()
    
    def _cargar_yaml(self):
        """Carga el archivo YAML como base."""
        ruta = os.getenv("DALEX_CONFIG_PATH", "./config/dalex.yaml")
        ruta_path = Path(ruta)
        if ruta_path.exists():
            with open(ruta_path, "r", encoding="utf-8") as f:
                self._yaml_data = yaml.safe_load(f) or {}
    
    def _get(self, *keys, env_var: str = None, default=None):
        """
        Obtiene un valor con prioridad: ENV > YAML > default.
        
        Args:
            *keys: Ruta en el YAML (ej: "agente", "nombre")
            env_var: Variable de entorno alternativa
            default: Valor por defecto
        """
        # 1. Intentar variable de entorno
        if env_var and os.getenv(env_var):
            valor = os.getenv(env_var)
            # Convertir tipos básicos
            if valor.lower() in ("true", "false"):
                return valor.lower() == "true"
            try:
                return int(valor)
            except ValueError:
                pass
            return valor
        
        # 2. Intentar YAML
        data = self._yaml_data
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data if data is not None else default
    
    # === AGENTE ===
    @property
    def nombre(self) -> str:
        return self._get("agente", "nombre", env_var="DALEX_NAME", default="DALEX")
    
    @property
    def version(self) -> str:
        return self._get("agente", "version", default="0.5.0")
    
    @property
    def modo(self) -> str:
        """Modo de operación: 'lite' o 'pro'"""
        return self._get("agente", "modo", env_var="DALEX_MODE", default="lite")
    
    @property
    def es_modo_pro(self) -> bool:
        return self.modo.lower() == "pro"
    
    @property
    def carpeta_skills(self) -> str:
        return self._get("agente", "carpeta_skills", default="/app/data/skills")
    
    @property
    def timeout_llm(self) -> int:
        return self._get("agente", "timeout_llm", env_var="DALEX_TIMEOUT", default=120)
    
    @property
    def max_pasos(self) -> int:
        return self._get("agente", "max_pasos", default=10)
    
    # === LLM / OLLAMA ===
    @property
    def ollama_url(self) -> str:
        return self._get("llm", "ollama", "url", env_var="OLLAMA_HOST", default="http://localhost:11434")
    
    @property
    def ollama_modelo(self) -> str:
        return self._get("llm", "ollama", "modelo", env_var="OLLAMA_MODEL", default="qwen2.5:7b")
    
    @property
    def ollama_habilitado(self) -> bool:
        return self._get("llm", "ollama", "habilitado", env_var="OLLAMA_ENABLED", default=True)
    
    # === BASE DE DATOS ===
    @property
    def database_url(self) -> str:
        return self._get("base_datos", "url", env_var="DATABASE_URL", default="sqlite:///./data/dalex.db")
    
    # === API ===
    @property
    def api_host(self) -> str:
        return self._get("api", "host", env_var="API_HOST", default="0.0.0.0")
    
    @property
    def api_puerto(self) -> int:
        return self._get("api", "puerto", env_var="API_PORT", default=8000)
    
    # === MEMORIA (solo modo pro) ===
    @property
    def memoria_episodica_habilitada(self) -> bool:
        if not self.es_modo_pro:
            return False
        return self._get("memoria", "episodica", "habilitada", default=True)
    
    @property
    def memoria_episodica_max(self) -> int:
        return self._get("memoria", "episodica", "max_registros", default=10000)
    
    @property
    def memoria_semantica_habilitada(self) -> bool:
        if not self.es_modo_pro:
            return False
        return self._get("memoria", "semantica", "habilitada", default=True)
    
    @property
    def memoria_semantica_directorio(self) -> str:
        return self._get("memoria", "semantica", "directorio", default="./data/chromadb")
    
    @property
    def memoria_semantica_coleccion(self) -> str:
        return self._get("memoria", "semantica", "coleccion", default="dalex_memoria")
    
    @property
    def memoria_semantica_max_resultados(self) -> int:
        return self._get("memoria", "semantica", "max_resultados", default=5)
    
    @property
    def memoria_errores_habilitada(self) -> bool:
        if not self.es_modo_pro:
            return False
        return self._get("memoria", "errores", "habilitada", default=True)
    
    @property
    def memoria_errores_max(self) -> int:
        return self._get("memoria", "errores", "max_registros", default=5000)
    
    @property
    def memoria_errores_umbral(self) -> int:
        return self._get("memoria", "errores", "umbral_autocorreccion", default=2)
    
    # === AUDITORIA ===
    @property
    def auditoria_habilitada(self) -> bool:
        return self._get("auditoria", "habilitado", default=True)
    
    @property
    def auditoria_nivel(self) -> str:
        return self._get("auditoria", "nivel", default="completo")
    
    def resumen(self) -> dict:
        """Resumen de configuración actual."""
        return {
            "nombre": self.nombre,
            "version": self.version,
            "modo": self.modo,
            "ollama_url": self.ollama_url,
            "ollama_modelo": self.ollama_modelo,
            "api_puerto": self.api_puerto,
            "memoria_avanzada": self.es_modo_pro,
        }


# Instancia global
config = Config()
