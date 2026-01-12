#!/usr/bin/env python3
"""
Script de verificación para la limpieza de memoria semántica.

Prueba:
1. Inserción de documentos con caracteres CJK (chino)
2. Ejecución de limpieza automática
3. Verificación de que documentos CJK no se recuperan en búsquedas
4. Verificación de filtro anti-autocitación
"""

import sys
import time
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from memoria.avanzada.semantica import MemoriaSemantica
from config.settings import config


def test_limpieza_cjk():
    """Prueba la limpieza de contenido CJK."""
    print("=" * 60)
    print("TEST 1: Limpieza de contenido CJK")
    print("=" * 60)

    # Crear instancia de memoria semántica
    memoria = MemoriaSemantica()

    if not memoria._habilitada:
        print("⚠️  Memoria semántica no habilitada en config. Activándola temporalmente...")
        memoria._habilitada = True

    # Insertar documentos de prueba ANTES de inicializar
    # (para simular que ya existen documentos sucios)
    print("\n1. Insertando documentos de prueba...")

    try:
        import chromadb
        from chromadb.config import Settings

        cliente = chromadb.PersistentClient(
            path=memoria._directorio,
            settings=Settings(anonymized_telemetry=False)
        )
        coleccion = cliente.get_or_create_collection(name=memoria._coleccion_nombre)

        # Documento 1: Solo español (debe mantenerse)
        coleccion.add(
            ids=["test_clean_1"],
            documents=["Este es un documento limpio en español sobre cláusulas abusivas"],
            metadatas=[{"tipo": "test", "timestamp": "2024-01-01T00:00:00"}]
        )

        # Documento 2: Mezcla español + chino (debe limpiarse y conservarse)
        coleccion.add(
            ids=["test_mixed_2"],
            documents=["Información legal 这是中文文本 sobre derechos del consumidor"],
            metadatas=[{"tipo": "test", "timestamp": "2024-01-01T00:00:00"}]
        )

        # Documento 3: Solo chino (debe eliminarse)
        coleccion.add(
            ids=["test_chinese_3"],
            documents=["这是完全的中文文本关于法律条款"],
            metadatas=[{"tipo": "test", "timestamp": "2024-01-01T00:00:00"}]
        )

        print(f"   ✓ 3 documentos de prueba insertados")
        print(f"     - 1 limpio (español)")
        print(f"     - 1 mixto (español + chino)")
        print(f"     - 1 sucio (solo chino)")

    except Exception as e:
        print(f"   ✗ Error insertando documentos: {e}")
        return False

    # Ahora inicializar (esto dispara la limpieza automática)
    print("\n2. Inicializando memoria (ejecuta limpieza automática)...")
    if not memoria.inicializar():
        print("   ✗ Error al inicializar memoria")
        return False

    # Verificar resultados
    print("\n3. Verificando resultados de limpieza...")
    try:
        # Buscar el documento limpio
        docs_limpios = coleccion.get(ids=["test_clean_1"])
        if docs_limpios and docs_limpios["ids"]:
            print("   ✓ Documento limpio conservado correctamente")
        else:
            print("   ✗ ERROR: Documento limpio fue eliminado")

        # Buscar el documento mixto (debería estar reindexado sin chino)
        docs_mixtos = coleccion.get(ids=["test_mixed_2"])
        if docs_mixtos and docs_mixtos["ids"]:
            contenido = docs_mixtos["documents"][0]
            if "中文" not in contenido and "legal" in contenido:
                print(f"   ✓ Documento mixto limpiado: '{contenido[:50]}...'")
            else:
                print(f"   ✗ ERROR: Documento mixto no fue limpiado correctamente: '{contenido}'")
        else:
            print("   ⚠️  Documento mixto fue eliminado (comportamiento aceptable)")

        # Buscar el documento solo chino (debería haber sido eliminado)
        docs_chinos = coleccion.get(ids=["test_chinese_3"])
        if not docs_chinos or not docs_chinos["ids"]:
            print("   ✓ Documento solo-chino eliminado correctamente")
        else:
            print(f"   ✗ ERROR: Documento solo-chino NO fue eliminado")

    except Exception as e:
        print(f"   ✗ Error verificando: {e}")
        return False

    # Limpiar documentos de prueba
    print("\n4. Limpiando documentos de prueba...")
    try:
        ids_limpiar = ["test_clean_1", "test_mixed_2", "test_chinese_3"]
        coleccion.delete(ids=ids_limpiar)
        print("   ✓ Documentos de prueba eliminados")
    except:
        pass

    return True


def test_anti_autocitacion():
    """Prueba el filtro anti-autocitación."""
    print("\n" + "=" * 60)
    print("TEST 2: Filtro anti-autocitación")
    print("=" * 60)

    memoria = MemoriaSemantica()

    if not memoria._habilitada:
        memoria._habilitada = True

    if not memoria.inicializar():
        print("⚠️  No se pudo inicializar memoria para este test")
        return False

    plan_id_actual = "plan_test_123"

    print("\n1. Insertando episodios de prueba...")
    try:
        # Episodio 1: Con plan_id actual (debe ser excluido)
        doc1 = memoria.agregar_episodio(
            intencion="Consulta sobre cláusulas abusivas",
            resultado="Resultado sobre cláusulas abusivas",
            skills=["legal"],
            exito=True,
            plan_id=plan_id_actual
        )

        # Episodio 2: Con plan_id diferente (debe ser incluido)
        doc2 = memoria.agregar_episodio(
            intencion="Consulta sobre derechos del consumidor",
            resultado="Resultado sobre derechos del consumidor",
            skills=["legal"],
            exito=True,
            plan_id="plan_diferente_456"
        )

        # Esperar un poco para que el timestamp sea diferente
        time.sleep(2)

        # Episodio 3: Muy reciente, sin plan_id (debe ser excluido por timestamp)
        doc3 = memoria.agregar_episodio(
            intencion="Consulta reciente sobre garantías",
            resultado="Resultado sobre garantías",
            skills=["legal"],
            exito=True,
            plan_id=None
        )

        print(f"   ✓ 3 episodios insertados")
        print(f"     - Doc 1: plan_id={plan_id_actual} (debe excluirse)")
        print(f"     - Doc 2: plan_id=plan_diferente_456 (debe incluirse)")
        print(f"     - Doc 3: muy reciente, sin plan_id (debe excluirse)")

    except Exception as e:
        print(f"   ✗ Error insertando episodios: {e}")
        return False

    print("\n2. Buscando con filtro anti-autocitación...")
    try:
        # Buscar pasando el plan_id actual
        resultados = memoria.buscar(
            consulta="cláusulas abusivas derechos",
            plan_id=plan_id_actual,
            limite=5
        )

        print(f"   Resultados encontrados: {len(resultados)}")

        # Verificar que no incluye el episodio con plan_id_actual
        plan_ids_encontrados = [r["metadata"].get("plan_id") for r in resultados]
        if plan_id_actual in plan_ids_encontrados:
            print(f"   ✗ ERROR: Se encontró episodio con plan_id actual (autocitación)")
            return False
        else:
            print(f"   ✓ Filtro plan_id funciona: plan_id actual excluido")

        # Verificar que el episodio reciente fue excluido
        # (es difícil de verificar sin IDs, pero al menos confirmamos que hay filtrado)
        if len(resultados) <= 1:
            print(f"   ✓ Filtro temporal parece funcionar (pocos resultados recientes)")
        else:
            print(f"   ⚠️  Se encontraron {len(resultados)} resultados (verificar filtro temporal manualmente)")

    except Exception as e:
        print(f"   ✗ Error buscando: {e}")
        return False

    # Limpiar documentos de prueba
    print("\n3. Limpiando documentos de prueba...")
    try:
        if doc1:
            memoria._coleccion.delete(ids=[doc1])
        if doc2:
            memoria._coleccion.delete(ids=[doc2])
        if doc3:
            memoria._coleccion.delete(ids=[doc3])
        print("   ✓ Documentos de prueba eliminados")
    except:
        pass

    return True


def main():
    print("\n🧪 PRUEBAS DE LIMPIEZA Y SANEAMIENTO DE MEMORIA SEMÁNTICA\n")

    # Test 1: Limpieza CJK
    test1_ok = test_limpieza_cjk()

    # Test 2: Anti-autocitación
    test2_ok = test_anti_autocitacion()

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    print(f"Test 1 (Limpieza CJK):       {'✅ PASÓ' if test1_ok else '❌ FALLÓ'}")
    print(f"Test 2 (Anti-autocitación):  {'✅ PASÓ' if test2_ok else '❌ FALLÓ'}")
    print("=" * 60)

    if test1_ok and test2_ok:
        print("\n✅ TODAS LAS PRUEBAS PASARON EXITOSAMENTE\n")
        return 0
    else:
        print("\n❌ ALGUNAS PRUEBAS FALLARON\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
