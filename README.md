# DALEX v0.5.0

Agente de Inteligencia Artificial con soporte para modo lite y pro.

## Modos de Operación

| Característica | Lite (Fase 3) | Pro (Fase 4) |
|---------------|---------------|--------------|
| Planificación | ✅ | ✅ |
| Ejecución de skills | ✅ | ✅ |
| Autocorrección | ✅ | ✅ |
| Memoria episódica | ❌ | ✅ |
| Memoria semántica | ❌ | ✅ ChromaDB |
| Memoria de errores | ❌ | ✅ |

## Requisitos

- Python 3.11+
- Ollama con modelo `qwen2.5:7b`

```bash
# Verificar Ollama
ollama list
# Si no tienes el modelo:
ollama pull qwen2.5:7b
```

## Instalación

### Opción 1: Docker (Recomendado)

```bash
# Copiar configuración
cp .env.example .env

# Editar .env según necesites
# DALEX_MODE=lite  o  DALEX_MODE=pro

# Construir y ejecutar
docker-compose up -d

# Ver logs
docker-compose logs -f
```

### Opción 2: Manual

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Si usas modo pro, instalar ChromaDB:
pip install chromadb

# Configurar
export DALEX_MODE=lite
export OLLAMA_HOST=http://localhost:11434

# Ejecutar
python main.py
```

## Configuración

### Variables de Entorno (prioridad sobre YAML)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DALEX_MODE` | `lite` | `lite` o `pro` |
| `OLLAMA_HOST` | `http://localhost:11434` | URL de Ollama |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Modelo a usar |
| `API_PORT` | `8000` | Puerto de la API |
| `DATABASE_URL` | SQLite local | URL de base de datos |

### Archivo YAML (config/dalex.yaml)

El archivo YAML sirve como configuración base. Las variables de entorno tienen prioridad.

## API

### Endpoints Principales

```bash
# Enviar mensaje
curl -X POST http://localhost:8000/mensajes \
  -H "Content-Type: application/json" \
  -d '{"mensaje": "Hola, ¿qué puedes hacer?"}'

# Estado del agente
curl http://localhost:8000/estado

# Skills disponibles
curl http://localhost:8000/skills
```

### Documentación

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Arquitectura

```
dalex/
├── config/           # Configuración (ENV > YAML)
├── core/             # Motor del agente
│   ├── agente.py     # Loop principal
│   ├── planificador.py
│   ├── ejecutor.py
│   └── autocorreccion.py
├── memoria/
│   ├── base.py       # Modelos SQLAlchemy
│   ├── operaciones.py
│   └── avanzada/     # Solo modo pro
├── skills/           # Capacidades
├── api/              # FastAPI
└── integraciones/
    └── llm/          # Conexión con Ollama
```

## Uso

### Flujo Básico

1. Usuario envía mensaje
2. Agente genera plan
3. Si es simple → ejecuta automáticamente
4. Si es complejo → pide aprobación
5. Usuario aprueba/rechaza
6. Agente ejecuta y responde

### Ejemplo de Conversación

```
Usuario: ¿Qué es Python?
Agente: Python es un lenguaje de programación...

Usuario: Crea un script que calcule factoriales
Agente: 📋 Plan: Crear script de factoriales
        1. 💬 Generar código Python para calcular factoriales
        ¿Apruebas este plan? (sí/no)

Usuario: sí
Agente: [ejecuta el plan y responde con el código]
```

## Desarrollo

### Agregar Nueva Skill

1. Crear carpeta en `skills/`
2. Agregar `SKILL.md` con la definición
3. Reiniciar el agente

### Cambiar de Modo

```bash
# En .env
DALEX_MODE=pro

# O como variable de entorno
export DALEX_MODE=pro
docker-compose up -d
```

## Troubleshooting

### Error: "No se pudo conectar con el LLM"

1. Verificar que Ollama está corriendo: `ollama list`
2. Verificar la URL: `curl http://localhost:11434/api/tags`
3. Si usas Docker, verificar que `host.docker.internal` resuelve

### Error: "Modelo no encontrado"

```bash
ollama pull qwen2.5:7b
```

### Modo Pro sin ChromaDB

Si ChromaDB no está instalado, la memoria semántica se desactiva pero el agente sigue funcionando.

```bash
pip install chromadb
```
