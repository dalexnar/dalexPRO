"""Catálogo de skills de DALEX."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import re

from config.settings import config


@dataclass
class EntradaSkill:
    """Entrada de una skill."""
    nombre: str
    tipo: str
    descripcion: str
    obligatorio: bool = True
    default: str = None


@dataclass
class Skill:
    """Definición de una skill."""
    nombre: str
    descripcion: str
    proposito: str
    entradas: List[EntradaSkill] = field(default_factory=list)
    salidas: List[str] = field(default_factory=list)
    ejemplos: List[str] = field(default_factory=list)
    limites: List[str] = field(default_factory=list)
    ruta: str = ""
    
    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "proposito": self.proposito,
            "entradas": [
                {"nombre": e.nombre, "tipo": e.tipo, "obligatorio": e.obligatorio}
                for e in self.entradas
            ],
        }


class CatalogoSkills:
    """Catálogo de skills disponibles."""
    
    def __init__(self, carpeta: str = None):
        self.carpeta = carpeta or config.carpeta_skills
        self.skills: Dict[str, Skill] = {}
    
    def escanear(self) -> int:
        """Escanea la carpeta de skills y carga las definiciones."""
        self.skills = {}
        carpeta_path = Path(self.carpeta)
        
        if not carpeta_path.exists():
            print(f"⚠ Carpeta de skills no existe: {self.carpeta}")
            return 0
        
        for item in carpeta_path.iterdir():
            if item.is_dir():
                skill_file = item / "SKILL.md"
                if skill_file.exists():
                    skill = self._parsear_skill(skill_file)
                    if skill:
                        self.skills[skill.nombre] = skill
        
        return len(self.skills)
    
    def _parsear_skill(self, ruta: Path) -> Optional[Skill]:
        """Parsea un archivo SKILL.md."""
        try:
            contenido = ruta.read_text(encoding="utf-8")
            
            # Extraer nombre (primer heading)
            nombre_match = re.search(r'^#\s+(.+)$', contenido, re.MULTILINE)
            nombre = nombre_match.group(1).strip() if nombre_match else ruta.parent.name
            
            # Extraer secciones
            def extraer_seccion(titulo: str) -> str:
                patron = rf'##\s+{titulo}\s*\n(.*?)(?=\n##|\Z)'
                match = re.search(patron, contenido, re.DOTALL | re.IGNORECASE)
                return match.group(1).strip() if match else ""
            
            descripcion = extraer_seccion("Descripción") or extraer_seccion("Description")
            proposito = extraer_seccion("Propósito") or extraer_seccion("Purpose")
            
            # Extraer entradas
            entradas = []
            entradas_texto = extraer_seccion("Entradas") or extraer_seccion("Inputs")
            for linea in entradas_texto.split("\n"):
                match = re.match(r'-\s+\*\*(\w+)\*\*\s*\((\w+)(?:,\s*(obligatorio|opcional))?\):\s*(.+)', linea)
                if match:
                    entradas.append(EntradaSkill(
                        nombre=match.group(1),
                        tipo=match.group(2),
                        obligatorio=match.group(3) != "opcional",
                        descripcion=match.group(4)
                    ))
            
            return Skill(
                nombre=nombre,
                descripcion=descripcion,
                proposito=proposito,
                entradas=entradas,
                ruta=str(ruta.parent),
            )
            
        except Exception as e:
            print(f"Error parseando skill {ruta}: {e}")
            return None
    
    def obtener(self, nombre: str) -> Optional[Skill]:
        """Obtiene una skill por nombre."""
        return self.skills.get(nombre)
    
    def listar(self) -> List[dict]:
        """Lista todas las skills disponibles."""
        return [s.to_dict() for s in self.skills.values()]
    
    def obtener_para_prompt(self) -> str:
        """Genera texto de skills para incluir en prompts."""
        if not self.skills:
            return "No hay skills disponibles."

        lineas = ["Skills disponibles:"]
        for skill in self.skills.values():
            entradas_str = ", ".join(
                f"{e.nombre}:{e.tipo}" for e in skill.entradas
            ) or "ninguna"
            lineas.append(f"- {skill.nombre}: {skill.descripcion[:100]}")
            lineas.append(f"  Entradas: {entradas_str}")

        return "\n".join(lineas)

    def reescanear(self) -> int:
        """Reescanea el catálogo de skills."""
        return self.escanear()
