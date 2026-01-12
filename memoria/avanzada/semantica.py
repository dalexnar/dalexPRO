"""Memoria semántica: búsqueda por similitud con ChromaDB (modo pro)."""

import re
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Optional

from config.settings import config


class MemoriaSemantica:
    """Búsqueda por similitud semántica usando ChromaDB."""

    # Constantes para limpieza y filtrado
    _PATRON_CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
    _VENTANA_ANTI_AUTOCITACION = 30  # segundos para excluir episodios recientes

    def __init__(self):
        self._habilitada = config.memoria_semantica_habilitada
        self._directorio = config.memoria_semantica_directorio
        self._coleccion_nombre = config.memoria_semantica_coleccion
        self._max_resultados = config.memoria_semantica_max_resultados

        self._cliente = None
        self._coleccion = None
        self._inicializado = False
        self._error_init = None
        self._plan_id_actual = None  # Para evitar autocitación
    
    @property
    def habilitada(self) -> bool:
        return self._habilitada and self._inicializado
    
    def inicializar(self) -> bool:
        """Inicializa ChromaDB. Falla silenciosamente si no está disponible."""
        if not self._habilitada:
            return False

        try:
            import chromadb
            from chromadb.config import Settings

            self._cliente = chromadb.PersistentClient(
                path=self._directorio,
                settings=Settings(anonymized_telemetry=False)
            )
            self._coleccion = self._cliente.get_or_create_collection(
                name=self._coleccion_nombre
            )
            self._inicializado = True
            print(f"✓ Memoria semántica (ChromaDB) inicializada")

            # Ejecutar limpieza de contenido CJK (una pasada automática)
            self._limpiar_contenido_cjk()

            return True

        except ImportError:
            self._error_init = "ChromaDB no instalado (pip install chromadb)"
            print(f"⚠ {self._error_init}")
            return False
        except Exception as e:
            self._error_init = str(e)
            print(f"⚠ Memoria semántica no disponible: {e}")
            return False
    
    def agregar(self, contenido: str, metadata: dict = None) -> Optional[str]:
        """Agrega un documento a la memoria."""
        if not self._inicializado:
            return None

        # Sanitizar contenido antes de agregar (prevención)
        contenido_limpio = self._sanitizar_contenido(contenido)
        if not contenido_limpio or contenido_limpio.strip() == "":
            # Si después de sanitizar no queda nada, no agregar
            return None

        doc_id = str(uuid4())
        meta = {"timestamp": datetime.utcnow().isoformat()}
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (bool, int, float, str)):
                    meta[k] = v
                else:
                    meta[k] = str(v)

        try:
            self._coleccion.add(
                documents=[contenido_limpio],
                metadatas=[meta],
                ids=[doc_id]
            )
            return doc_id
        except Exception as e:
            print(f"Error agregando a ChromaDB: {e}")
            return None
    
    def buscar(self, consulta: str, limite: int = None, plan_id: str = None) -> List[dict]:
        """Busca documentos similares, excluyendo autocitaciones."""
        if not self._inicializado:
            return []

        n = limite or self._max_resultados

        try:
            # Obtener más resultados de los necesarios para poder filtrar
            n_query = min(n * 3, 50)  # Triplicar pero limitar a 50

            resultados = self._coleccion.query(
                query_texts=[consulta],
                n_results=n_query
            )

            docs = []
            if resultados and resultados["documents"] and resultados["documents"][0]:
                ahora = datetime.utcnow()
                plan_id_filtro = plan_id or self._plan_id_actual

                for i, doc in enumerate(resultados["documents"][0]):
                    metadata = resultados["metadatas"][0][i] if resultados["metadatas"] else {}

                    # Filtro anti-autocitación: excluir episodios del mismo plan_id
                    if plan_id_filtro and metadata.get("plan_id") == plan_id_filtro:
                        continue

                    # Filtro anti-autocitación: excluir episodios muy recientes
                    timestamp_str = metadata.get("timestamp")
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            edad = (ahora - timestamp).total_seconds()
                            if edad < self._VENTANA_ANTI_AUTOCITACION:
                                continue
                        except:
                            pass  # Si falla el parseo, incluir el documento

                    docs.append({
                        "contenido": doc,
                        "metadata": metadata,
                    })

                    # Detener cuando tengamos suficientes resultados
                    if len(docs) >= n:
                        break

            return docs
        except Exception as e:
            print(f"Error buscando en ChromaDB: {e}")
            return []
    
    def agregar_episodio(
        self,
        intencion: str,
        resultado: str,
        skills: List[str],
        exito: bool,
        plan_id: str = None
    ) -> Optional[str]:
        """Agrega un episodio formateado."""
        if not self._inicializado:
            return None

        skills_str = ', '.join(skills) if skills else 'ninguna'
        texto = f"Tarea: {intencion}\nResultado: {resultado}\nSkills: {skills_str}"

        metadata = {"tipo": "episodio", "exito": exito}
        if plan_id:
            metadata["plan_id"] = plan_id

        return self.agregar(texto, metadata)
    
    def buscar_contexto(self, mensaje: str, plan_id: str = None) -> str:
        """Busca contexto relevante formateado para el agente."""
        if not self._inicializado:
            return ""

        docs = self.buscar(mensaje, limite=3, plan_id=plan_id)
        if not docs:
            return ""

        lineas = ["Contexto de tareas anteriores:"]
        for d in docs:
            lineas.append(f"- {d['contenido'][:150]}")
        return "\n".join(lineas)

    def establecer_plan_actual(self, plan_id: str):
        """Establece el plan_id actual para evitar autocitación."""
        self._plan_id_actual = plan_id

    def limpiar_plan_actual(self):
        """Limpia el plan_id actual."""
        self._plan_id_actual = None
    
    def stats(self) -> dict:
        """Estadísticas de memoria semántica."""
        if not self._habilitada:
            return {"habilitada": False}

        if not self._inicializado:
            return {
                "habilitada": True,
                "inicializado": False,
                "error": self._error_init
            }

        try:
            return {
                "habilitada": True,
                "inicializado": True,
                "documentos": self._coleccion.count()
            }
        except:
            return {"habilitada": True, "inicializado": True, "error": "Error obteniendo stats"}

    def _sanitizar_contenido(self, texto: str) -> str:
        """Elimina caracteres CJK del texto, dejando solo texto en alfabeto latino."""
        if not texto:
            return texto

        # Eliminar caracteres CJK
        texto_limpio = self._PATRON_CJK.sub('', texto)

        # Limpiar espacios múltiples y saltos de línea
        texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()

        return texto_limpio

    def _limpiar_contenido_cjk(self):
        """
        Limpia documentos existentes con contenido CJK.
        Se ejecuta una vez al inicializar la memoria.
        """
        if not self._inicializado:
            return

        try:
            # Obtener todos los documentos
            todos = self._coleccion.get()

            if not todos or not todos["ids"]:
                return

            ids_a_eliminar = []
            ids_a_reindexar = []
            docs_reindexados = []
            metas_reindexadas = []

            total = len(todos["ids"])

            for i, doc_id in enumerate(todos["ids"]):
                contenido = todos["documents"][i] if todos["documents"] else ""
                metadata = todos["metadatas"][i] if todos["metadatas"] else {}

                # Detectar si tiene caracteres CJK
                if self._PATRON_CJK.search(contenido):
                    contenido_limpio = self._sanitizar_contenido(contenido)

                    if contenido_limpio and contenido_limpio.strip():
                        # Reindexar con contenido limpio
                        ids_a_eliminar.append(doc_id)
                        ids_a_reindexar.append(doc_id)
                        docs_reindexados.append(contenido_limpio)
                        metas_reindexadas.append(metadata)
                    else:
                        # Eliminar si no queda contenido útil
                        ids_a_eliminar.append(doc_id)

            # Aplicar cambios
            eliminados = len(ids_a_eliminar)
            reindexados = len(ids_a_reindexar)

            if ids_a_eliminar:
                self._coleccion.delete(ids=ids_a_eliminar)

            if ids_a_reindexar:
                self._coleccion.add(
                    ids=ids_a_reindexar,
                    documents=docs_reindexados,
                    metadatas=metas_reindexadas
                )

            if eliminados > 0 or reindexados > 0:
                print(f"🧹 Memoria semántica saneada: {total} documentos revisados, "
                      f"{reindexados} corregidos, {eliminados - reindexados} eliminados")

        except Exception as e:
            # No romper la inicialización si falla la limpieza
            print(f"⚠ Error durante limpieza de memoria semántica: {e}")
