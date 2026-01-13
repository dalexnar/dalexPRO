"""Rutas de la API para gestión de documentos."""

import os
from datetime import datetime
from typing import List
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from memoria.avanzada import gestor_memoria
from config.settings import config


router = APIRouter()


# === CONFIGURACIÓN ===

DIRECTORIO_DOCUMENTOS = "data/documentos"
TIPOS_PERMITIDOS = {".pdf", ".txt", ".docx"}
MAX_SIZE_MB = 10
CHUNK_SIZE = 500  # tokens aproximados (~2000 caracteres)


# === MODELOS ===

class DocumentoResponse(BaseModel):
    id: str
    nombre: str
    chunks_indexados: int
    fecha: str


class DocumentoListItem(BaseModel):
    id: str
    nombre: str
    tipo: str
    chunks: int
    fecha: str


# === UTILIDADES DE PROCESAMIENTO ===

def extraer_texto_pdf(ruta: str) -> str:
    """Extrae texto de un PDF."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(ruta)
        texto = []

        for pagina in reader.pages:
            texto.append(pagina.extract_text())

        return "\n".join(texto)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {str(e)}")


def extraer_texto_docx(ruta: str) -> str:
    """Extrae texto de un DOCX."""
    try:
        from docx import Document

        doc = Document(ruta)
        texto = []

        for parrafo in doc.paragraphs:
            if parrafo.text.strip():
                texto.append(parrafo.text)

        return "\n".join(texto)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando DOCX: {str(e)}")


def extraer_texto_txt(ruta: str) -> str:
    """Extrae texto de un TXT."""
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # Intentar con latin-1 si UTF-8 falla
        with open(ruta, 'r', encoding='latin-1') as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo TXT: {str(e)}")


def dividir_en_chunks(texto: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """
    Divide el texto en chunks de aproximadamente chunk_size tokens.
    Aproximación: 1 token ≈ 4 caracteres.
    """
    chars_por_chunk = chunk_size * 4
    chunks = []

    # Dividir por párrafos primero
    parrafos = texto.split('\n')
    chunk_actual = []
    longitud_actual = 0

    for parrafo in parrafos:
        parrafo = parrafo.strip()
        if not parrafo:
            continue

        longitud_parrafo = len(parrafo)

        if longitud_actual + longitud_parrafo > chars_por_chunk and chunk_actual:
            # Guardar chunk actual
            chunks.append('\n'.join(chunk_actual))
            chunk_actual = [parrafo]
            longitud_actual = longitud_parrafo
        else:
            chunk_actual.append(parrafo)
            longitud_actual += longitud_parrafo

    # Agregar último chunk
    if chunk_actual:
        chunks.append('\n'.join(chunk_actual))

    return chunks


# === ENDPOINTS ===

@router.post("/documentos/subir", response_model=DocumentoResponse, tags=["Documentos"])
async def subir_documento(archivo: UploadFile = File(...)):
    """
    Sube y procesa un documento (PDF, TXT, DOCX).
    Extrae el texto, lo divide en chunks y lo indexa en ChromaDB.
    """
    # Verificar que la memoria semántica esté disponible
    if not gestor_memoria.semantica or not gestor_memoria.semantica.habilitada:
        raise HTTPException(
            status_code=503,
            detail="Memoria semántica no disponible. Verifica que ChromaDB esté instalado y configurado."
        )

    # Validar tipo de archivo
    extension = Path(archivo.filename).suffix.lower()
    if extension not in TIPOS_PERMITIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Tipos soportados: {', '.join(TIPOS_PERMITIDOS)}"
        )

    # Validar tamaño (leer en chunks de 1MB)
    contenido_bytes = await archivo.read()
    size_mb = len(contenido_bytes) / (1024 * 1024)

    if size_mb > MAX_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo muy grande. Máximo permitido: {MAX_SIZE_MB}MB"
        )

    # Crear directorio si no existe
    Path(DIRECTORIO_DOCUMENTOS).mkdir(parents=True, exist_ok=True)

    # Generar ID único para el documento
    doc_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat()

    # Guardar archivo
    nombre_archivo_seguro = f"{doc_id}_{archivo.filename}"
    ruta_archivo = os.path.join(DIRECTORIO_DOCUMENTOS, nombre_archivo_seguro)

    try:
        with open(ruta_archivo, 'wb') as f:
            f.write(contenido_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando archivo: {str(e)}")

    # Extraer texto según el tipo
    try:
        if extension == '.pdf':
            texto = extraer_texto_pdf(ruta_archivo)
        elif extension == '.docx':
            texto = extraer_texto_docx(ruta_archivo)
        elif extension == '.txt':
            texto = extraer_texto_txt(ruta_archivo)
        else:
            raise HTTPException(status_code=400, detail="Tipo de archivo no soportado")
    except HTTPException:
        # Limpiar archivo si falló la extracción
        os.remove(ruta_archivo)
        raise

    # Validar que hay texto
    if not texto or len(texto.strip()) < 10:
        os.remove(ruta_archivo)
        raise HTTPException(
            status_code=400,
            detail="El documento no contiene texto suficiente para indexar"
        )

    # Dividir en chunks
    chunks = dividir_en_chunks(texto)

    if not chunks:
        os.remove(ruta_archivo)
        raise HTTPException(status_code=400, detail="No se pudo dividir el documento en chunks")

    # Indexar cada chunk en ChromaDB
    chunks_indexados = 0
    for i, chunk in enumerate(chunks):
        chunk_id = gestor_memoria.semantica.agregar_documento_chunk(
            contenido=chunk,
            doc_id=doc_id,
            nombre_archivo=archivo.filename,
            tipo_archivo=extension[1:],  # Remover el punto
            chunk_index=i
        )

        if chunk_id:
            chunks_indexados += 1

    if chunks_indexados == 0:
        # Si no se indexó nada, limpiar
        os.remove(ruta_archivo)
        raise HTTPException(status_code=500, detail="Error indexando documento en memoria semántica")

    return DocumentoResponse(
        id=doc_id,
        nombre=archivo.filename,
        chunks_indexados=chunks_indexados,
        fecha=timestamp
    )


@router.get("/documentos", response_model=List[DocumentoListItem], tags=["Documentos"])
async def listar_documentos():
    """Lista todos los documentos indexados."""
    if not gestor_memoria.semantica or not gestor_memoria.semantica.habilitada:
        raise HTTPException(
            status_code=503,
            detail="Memoria semántica no disponible"
        )

    documentos = gestor_memoria.semantica.listar_documentos()

    return [
        DocumentoListItem(
            id=doc["id"],
            nombre=doc["nombre"],
            tipo=doc["tipo"],
            chunks=doc["chunks"],
            fecha=doc["fecha"]
        )
        for doc in documentos
    ]


@router.delete("/documentos/{doc_id}", tags=["Documentos"])
async def eliminar_documento(doc_id: str):
    """
    Elimina un documento y todos sus chunks de ChromaDB.
    También elimina el archivo físico del disco.
    """
    if not gestor_memoria.semantica or not gestor_memoria.semantica.habilitada:
        raise HTTPException(
            status_code=503,
            detail="Memoria semántica no disponible"
        )

    # Intentar eliminar de ChromaDB
    eliminado = gestor_memoria.semantica.eliminar_documento(doc_id)

    if not eliminado:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Intentar eliminar archivo físico (buscar archivos que empiecen con el doc_id)
    try:
        directorio = Path(DIRECTORIO_DOCUMENTOS)
        if directorio.exists():
            for archivo in directorio.glob(f"{doc_id}_*"):
                archivo.unlink()
    except Exception as e:
        # No fallar si no se puede eliminar el archivo físico
        print(f"Advertencia: No se pudo eliminar archivo físico: {e}")

    return {"mensaje": "Documento eliminado correctamente", "id": doc_id}
