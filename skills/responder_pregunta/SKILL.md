# responder_pregunta

## Descripción
Responde preguntas generales usando el conocimiento del LLM.

## Propósito
Proporcionar respuestas informativas a preguntas del usuario cuando no se requiere una skill especializada.

## Entradas
- **pregunta** (string, obligatorio): La pregunta a responder
- **contexto** (string, opcional): Contexto adicional para la respuesta

## Salidas
- Respuesta textual a la pregunta

## Ejemplos
- "¿Qué es Python?" → Explicación sobre el lenguaje Python
- "¿Cuál es la capital de Colombia?" → "Bogotá"

## Límites
- No puede acceder a información en tiempo real
- No puede ejecutar código
- No puede acceder a archivos del sistema
