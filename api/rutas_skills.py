
"""Rutas de la API para gestión de skills."""

import os
import re
import shutil
from pathlib import Path
BASE_SKILLS_PATH = Path("data/skills")
BASE_SKILLS_PATH.mkdir(parents=True, exist_ok=True)
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field

from core.agente import agente
from config.settings import config


router = APIRouter()


# === MODELOS ===

class EntradaSkillRequest(BaseModel):
    nombre: str = Field(..., description="Nombre del parámetro")
    tipo: str = Field(..., description="Tipo del parámetro (string, int, bool, etc)")
    obligatorio: bool = Field(True, description="Si el parámetro es obligatorio")
    descripcion: str = Field("", description="Descripción del parámetro")


class CrearSkillRequest(BaseModel):
    nombre: str = Field(..., description="Nombre de la skill")
    descripcion: str = Field(..., description="Descripción breve de la skill")
    proposito: str = Field(..., description="Propósito detallado de la skill")
    entradas: List[EntradaSkillRequest] = Field(default_factory=list)
    salidas: Optional[str] = Field("Resultado de la ejecución", description="Descripción de las salidas")
    ejemplos: Optional[str] = Field("", description="Ejemplos de uso")
    limites: Optional[str] = Field("", description="Limitaciones de la skill")


class SkillResponse(BaseModel):
    exito: bool
    nombre: str
    ruta: str
    mensaje: Optional[str] = None


# === UTILIDADES ===

def validar_nombre_skill(nombre: str) -> str:
    """
    Valida y normaliza el nombre de una skill.
    Convierte a snake_case y valida caracteres permitidos.
    """
    nombre = nombre.lower().strip()
    nombre = re.sub(r'\s+', '_', nombre)
    nombre = re.sub(r'[^a-z0-9_]', '', nombre)

    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre de skill inválido")

    return nombre


def generar_skill_md(
    nombre: str,
    descripcion: str,
    proposito: str,
    entradas: List[EntradaSkillRequest],
    salidas: str = "Resultado de la ejecución",
    ejemplos: str = "",
    limites: str = ""
) -> str:
    """Genera el contenido de un archivo SKILL.md."""

    entradas_md = []
    for entrada in entradas:
        obligatorio_str = "obligatorio" if entrada.obligatorio else "opcional"
        desc = entrada.descripcion or "Sin descripción"
        entradas_md.append(
            f"- **{entrada.nombre}** ({entrada.tipo}, {obligatorio_str}): {desc}"
        )

    entradas_texto = "\n".join(entradas_md) if entradas_md else "- No requiere entradas"
    ejemplos_texto = ejemplos if ejemplos else "- Pendiente de documentar"
    limites_texto = limites if limites else "- Ninguno conocido"

    return f"""# {nombre}

## Descripción
{descripcion}

## Propósito
{proposito}

## Entradas
{entradas_texto}

## Salidas
- {salidas}

## Ejemplos
{ejemplos_texto}

## Límites
{limites_texto}
"""


def extraer_nombre_de_md(contenido: str) -> str:
    """Extrae el nombre de una skill desde el contenido de un SKILL.md."""
    match = re.search(r'^#\s+(.+)$', contenido, re.MULTILINE)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="El archivo no contiene un heading de nivel 1 (# nombre)"
        )
    return match.group(1).strip()


# === ENDPOINTS ===

@router.post("/skills/crear", response_model=SkillResponse, tags=["Skills"])
async def crear_skill(request: CrearSkillRequest):
    """
    Crea una nueva skill desde JSON.
    Genera la carpeta y el archivo SKILL.md automáticamente.
    """
    nombre_normalizado = validar_nombre_skill(request.nombre)

    if not agente._inicializado:
        raise HTTPException(
            status_code=503,
            detail="El agente no está inicializado"
        )

    carpeta_skill = Path(config.carpeta_skills) / nombre_normalizado

    if carpeta_skill.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una skill con el nombre '{nombre_normalizado}'"
        )

    try:
        carpeta_skill.mkdir(parents=True, exist_ok=False)

        contenido_md = generar_skill_md(
            nombre=request.nombre,
            descripcion=request.descripcion,
            proposito=request.proposito,
            entradas=request.entradas,
            salidas=request.salidas,
            ejemplos=request.ejemplos,
            limites=request.limites
        )

        archivo_skill = carpeta_skill / "SKILL.md"
        archivo_skill.write_text(contenido_md, encoding="utf-8")

        n_skills = agente.catalogo.reescanear()

        return SkillResponse(
            exito=True,
            nombre=nombre_normalizado,
            ruta=str(carpeta_skill),
            mensaje=f"Skill creada exitosamente. Total de skills: {n_skills}"
        )

    except Exception as e:
        if carpeta_skill.exists():
            shutil.rmtree(carpeta_skill)

        raise HTTPException(
            status_code=500,
            detail=f"Error creando skill: {str(e)}"
        )


@router.post("/skills/subir", response_model=SkillResponse, tags=["Skills"])
async def subir_skill(archivo: UploadFile = File(...)):
    """
    Sube una skill desde un archivo SKILL.md.
    Extrae el nombre del primer heading y crea la estructura necesaria.
    """
    if not archivo.filename.endswith(".md"):
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten archivos .md"
        )

    if not agente._inicializado:
        raise HTTPException(
            status_code=503,
            detail="El agente no está inicializado"
        )

    try:
        contenido_bytes = await archivo.read()
        contenido = contenido_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="El archivo no está codificado en UTF-8"
        )

    try:
        nombre = extraer_nombre_de_md(contenido)
        nombre_normalizado = validar_nombre_skill(nombre)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error extrayendo nombre de la skill: {str(e)}"
        )

    carpeta_skill = Path(config.carpeta_skills) / nombre_normalizado

    if carpeta_skill.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una skill con el nombre '{nombre_normalizado}'"
        )

    try:
        carpeta_skill.mkdir(parents=True, exist_ok=False)

        archivo_skill = carpeta_skill / "SKILL.md"
        archivo_skill.write_text(contenido, encoding="utf-8")

        n_skills = agente.catalogo.reescanear()

        return SkillResponse(
            exito=True,
            nombre=nombre_normalizado,
            ruta=str(carpeta_skill),
            mensaje=f"Skill subida exitosamente. Total de skills: {n_skills}"
        )

    except Exception as e:
        if carpeta_skill.exists():
            shutil.rmtree(carpeta_skill)

        raise HTTPException(
            status_code=500,
            detail=f"Error subiendo skill: {str(e)}"
        )


@router.delete("/skills/{nombre}", response_model=SkillResponse, tags=["Skills"])
async def eliminar_skill(nombre: str):
    """
    Elimina una skill y su carpeta del sistema.
    """
    if not agente._inicializado:
        raise HTTPException(
            status_code=503,
            detail="El agente no está inicializado"
        )

    nombre_normalizado = validar_nombre_skill(nombre)

    skill = agente.catalogo.obtener(nombre_normalizado)
    if not skill:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{nombre_normalizado}' no encontrada"
        )

    carpeta_skill = Path(config.carpeta_skills) / nombre_normalizado

    if not carpeta_skill.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Carpeta de skill no encontrada: {carpeta_skill}"
        )

    try:
        shutil.rmtree(carpeta_skill)

        n_skills = agente.catalogo.reescanear()

        return SkillResponse(
            exito=True,
            nombre=nombre_normalizado,
            ruta=str(carpeta_skill),
            mensaje=f"Skill eliminada exitosamente. Total de skills: {n_skills}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error eliminando skill: {str(e)}"
        )
