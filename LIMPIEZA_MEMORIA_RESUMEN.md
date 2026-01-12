# RESUMEN DE CAMBIOS: Limpieza y Saneamiento de Memoria Avanzada

## 📋 Objetivo
Limpiar y sanear la memoria avanzada (episódica + semántica) eliminando contenido CJK (chino) y evitando autocitación, SIN romper funcionalidad existente.

---

## 📁 Archivos Modificados

### 1. **memoria/avanzada/semantica.py** ⚠️ MODIFICADO
**Líneas afectadas:** 1-8, 11-28, 34-65, 67-96, 98-149, 151-170, 172-192, 194-288

#### Cambios realizados:

**A) Imports (líneas 1-8)**
```python
# AGREGADO:
import re
from datetime import datetime, timedelta
```

**B) Constantes de clase (líneas 14-16)**
```python
# AGREGADO:
_PATRON_CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
_VENTANA_ANTI_AUTOCITACION = 30  # segundos para excluir episodios recientes
```

**C) Constructor `__init__()` (línea 28)**
```python
# AGREGADO:
self._plan_id_actual = None  # Para evitar autocitación
```

**D) Método `inicializar()` (líneas 53-55)**
```python
# AGREGADO al final del método, después de inicializar ChromaDB:
# Ejecutar limpieza de contenido CJK (una pasada automática)
self._limpiar_contenido_cjk()
```

**E) Método `agregar()` (líneas 72-76)**
```python
# AGREGADO sanitización preventiva:
contenido_limpio = self._sanitizar_contenido(contenido)
if not contenido_limpio or contenido_limpio.strip() == "":
    # Si después de sanitizar no queda nada, no agregar
    return None
```

**F) Método `buscar()` - REFACTORIZADO COMPLETAMENTE (líneas 98-149)**
```python
# CAMBIOS:
- Agregado parámetro: plan_id: str = None
- Implementado filtro anti-autocitación:
  * Excluye episodios con mismo plan_id
  * Excluye episodios con timestamp < 30 segundos
  * Query triplicado (n*3) para compensar filtrado
- Retorna solo resultados filtrados
```

**G) Método `agregar_episodio()` (líneas 151-170)**
```python
# CAMBIOS:
- Agregado parámetro: plan_id: str = None
- Se pasa plan_id en metadata para filtrado posterior
```

**H) Método `buscar_contexto()` (líneas 172-184)**
```python
# CAMBIOS:
- Agregado parámetro: plan_id: str = None
- Pasa plan_id a buscar() para filtrado
```

**I) Nuevos métodos públicos (líneas 186-192)**
```python
# AGREGADO:
def establecer_plan_actual(self, plan_id: str):
    """Establece el plan_id actual para evitar autocitación."""

def limpiar_plan_actual(self):
    """Limpia el plan_id actual."""
```

**J) Nuevos métodos privados (líneas 215-288)**
```python
# AGREGADO:
def _sanitizar_contenido(self, texto: str) -> str:
    """Elimina caracteres CJK del texto."""
    # Elimina rangos Unicode CJK
    # Limpia espacios múltiples

def _limpiar_contenido_cjk(self):
    """Limpia documentos existentes con contenido CJK."""
    # Se ejecuta una vez al inicializar
    # Detecta documentos con CJK
    # Reindexar o eliminar según contenido residual
    # Logging claro de acciones tomadas
    # Try/except robusto: no rompe si falla
```

---

### 2. **memoria/avanzada/gestor.py** ⚠️ MODIFICADO
**Líneas afectadas:** 60-88, 106-129

#### Cambios realizados:

**A) Método `registrar_tarea()` (línea 88)**
```python
# CAMBIO:
# Antes:
self.semantica.agregar_episodio(intencion, respuesta, skills, exito)

# Ahora:
self.semantica.agregar_episodio(intencion, respuesta, skills, exito, plan_id)
```

**B) Método `buscar_contexto()` (líneas 106-129)**
```python
# CAMBIOS:
- Agregado parámetro: plan_id: str = None
- Se pasa plan_id a semantica.buscar_contexto()
- Comentario actualizado: "Contexto semántico (con filtro anti-autocitación)"
```

---

### 3. **memoria/avanzada/test_limpieza.py** ✅ NUEVO ARCHIVO

Archivo de prueba completo con dos tests:

**Test 1: Limpieza de contenido CJK**
- Inserta 3 documentos: limpio, mixto (español+chino), solo chino
- Inicializa memoria (dispara limpieza automática)
- Verifica que:
  * Documento limpio se conserva
  * Documento mixto se limpia (solo español)
  * Documento solo-chino se elimina

**Test 2: Filtro anti-autocitación**
- Inserta 3 episodios:
  * Con plan_id actual (debe excluirse)
  * Con plan_id diferente (debe incluirse)
  * Muy reciente sin plan_id (debe excluirse por timestamp)
- Busca con plan_id actual
- Verifica que autocitación no ocurre

**Ejecución:**
```bash
python3 memoria/avanzada/test_limpieza.py
```

---

## 🔒 Archivos NO Modificados (según reglas)

### ❌ **core/ejecutor.py** - NO TOCADO
- Ya contiene `_sanitizar_idioma()` en líneas 330-370 para limpiar respuestas
- NO se modificó el registro centralizado de memoria (líneas 94-112)
- Permanece intacto según instrucciones

### ❌ **memoria/avanzada/episodica.py** - NO TOCADO
- Solo usa SQLite (no afectado por limpieza CJK)
- No requiere cambios según alcance del proyecto

### ❌ **memoria/avanzada/errores.py** - NO TOCADO
- No requiere cambios según alcance del proyecto

### ❌ **core/agente.py** - NO TOCADO
- Usa `gestor_memoria.buscar_contexto()` en línea 107
- No pasa plan_id porque se ejecuta ANTES de generar el plan
- El filtro de timestamp (30s) es suficiente para este caso
- No requiere cambios en esta fase

---

## 🎯 Funcionalidades Implementadas

### ✅ 1. Limpieza de Contenido CJK
- **Detección:** Patrón regex para rangos Unicode CJK
- **Sanitización preventiva:** Todo documento nuevo se limpia antes de agregar
- **Limpieza retroactiva:** Al inicializar, se limpian documentos existentes
- **Estrategia:**
  - Documentos mixtos: reindexar solo parte en español
  - Documentos solo-CJK: eliminar completamente
  - Documentos limpios: conservar sin cambios
- **Logging claro:**
  ```
  🧹 Memoria semántica saneada: X documentos revisados, Y corregidos, Z eliminados
  ```

### ✅ 2. Filtro Anti-Autocitación
- **Filtro por plan_id:** Excluye episodios del mismo plan activo
- **Filtro por timestamp:** Excluye episodios de últimos 30 segundos
- **Implementación:**
  - Query aumentado (n*3) para compensar filtrado
  - Filtrado post-query para máxima flexibilidad
  - Parámetro opcional: si no se pasa plan_id, solo usa timestamp

### ✅ 3. Seguridad y Robustez
- **Try/except en `_limpiar_contenido_cjk()`**: Si falla, solo imprime warning, no rompe inicialización
- **Try/except en `buscar()`**: Si falla parseo de timestamp, incluye documento (fail-safe)
- **Validación de contenido limpio**: Si después de sanitizar queda vacío, no se agrega
- **Compatibilidad con ChromaDB no disponible**: Toda la lógica ya existente se mantiene

### ✅ 4. Verificación Automática
- Script de prueba completo: `memoria/avanzada/test_limpieza.py`
- Tests automatizados con salida clara
- Limpieza automática de datos de prueba

---

## 🚀 Cómo Usar

### Inicialización Normal
```python
from memoria.avanzada.gestor import gestor_memoria

# Al inicializar, se ejecuta limpieza automática
gestor_memoria.inicializar()
# Output: 🧹 Memoria semántica saneada: ...
```

### Evitar Autocitación en Búsquedas
```python
# Opción 1: Pasar plan_id explícitamente
contexto = gestor_memoria.buscar_contexto(mensaje, plan_id=plan_actual.id)

# Opción 2: Establecer plan_id globalmente (uso avanzado)
gestor_memoria.semantica.establecer_plan_actual(plan_id)
contexto = gestor_memoria.buscar_contexto(mensaje)
gestor_memoria.semantica.limpiar_plan_actual()
```

### Ejecutar Tests
```bash
cd /home/dalexnar/proyectos/dalex-pro/app
python3 memoria/avanzada/test_limpieza.py
```

---

## 📊 Estadísticas de Cambios

| Archivo | Líneas Modificadas | Líneas Agregadas | Tipo |
|---------|-------------------|------------------|------|
| `memoria/avanzada/semantica.py` | ~30 | ~120 | MODIFICADO |
| `memoria/avanzada/gestor.py` | ~5 | ~3 | MODIFICADO |
| `memoria/avanzada/test_limpieza.py` | 0 | 278 | NUEVO |
| **TOTAL** | **~35** | **~401** | - |

---

## ✅ Checklist de Reglas Cumplidas

- [x] NO tocar registro centralizado en `core/ejecutor.py`
- [x] NO romper modo lite (cambios solo afectan modo pro)
- [x] NO cambiar endpoints ni contratos de API
- [x] NO cambiar estructuras de base de datos
- [x] NO eliminar funcionalidades existentes
- [x] Cambios mínimos, seguros y documentados
- [x] Try/except robusto: no rompe si ChromaDB falla
- [x] Logs claros y descriptivos
- [x] Tests de verificación incluidos
- [x] Compatibilidad retroactiva completa

---

## 🧪 Próximos Pasos (NO implementados en esta fase)

Según tus instrucciones, estas tareas están FUERA del alcance actual:

- [ ] Inyección de memoria en prompts del ejecutor
- [ ] Cambios en prompting o generación de planes
- [ ] Modificación de endpoints API
- [ ] Optimización de embeddings o similitud semántica

---

## 📝 Notas Técnicas

### Patrón CJK Utilizado
```python
_PATRON_CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
```
Cubre los rangos Unicode principales:
- `\u4e00-\u9fff`: CJK Unified Ideographs
- `\u3400-\u4dbf`: CJK Extension A
- `\uf900-\ufaff`: CJK Compatibility Ideographs

### Ventana Anti-Autocitación
```python
_VENTANA_ANTI_AUTOCITACION = 30  # segundos
```
Configurable según necesidad. 30 segundos previene que un episodio recién creado se recupere inmediatamente en la misma sesión.

### Estrategia de Query Aumentado
Para compensar el filtrado post-query, se triplica el número de resultados solicitados:
```python
n_query = min(n * 3, 50)  # Triplicar pero limitar a 50
```
Esto garantiza que después del filtrado, tengamos suficientes resultados relevantes.

---

## 🎉 Resumen Final

**COMPLETADO EXITOSAMENTE:**
1. ✅ Limpieza de contenido CJK (preventiva + retroactiva)
2. ✅ Filtro anti-autocitación (plan_id + timestamp)
3. ✅ Manejo de errores robusto
4. ✅ Logs claros y descriptivos
5. ✅ Script de verificación completo
6. ✅ Compatibilidad total con código existente
7. ✅ Sin romper modo lite ni funcionalidad actual

**IMPACTO:** Fase de limpieza y calidad de memoria completada sin modificar lógica de ejecución ni prompting.
