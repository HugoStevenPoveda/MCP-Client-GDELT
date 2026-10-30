# Cliente MCP con Interfaz Gradio

> 🚀 **Cliente MCP** para orquestar múltiples servidores MCP 

## 🎯 Características

- **Interfaz Web Gradio**: Chat conversacional sin código
- **Multi-Servidor MCP**: Conexión simultánea a 3 servidores mcp
- **Claude AI como Agente**: Tool use inteligente para orquestar servicios
- **Flujo Completo**: Desde ingesta de noticias → extracción de conocimiento → modelos ML
- **Dockerizado**: Despliegue reproducible con contenedores
- **Debug Completo**: Logs detallados de todo el flujo de ejecución

## 🏗️ Arquitectura

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                    🌐 NAVEGADOR WEB                              │
│                   http://localhost:7860                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   📱 GRADIO INTERFACE                            │
│                      (app.py)                                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  - Recibe pregunta del usuario                         │    │
│  │  - Convierte historial a formato Claude               │    │
│  │  - Llama a MCPClient.chat()                           │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  🤖 MCP CLIENT                                   │
│                   (client.py)                                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  1. Formatea tools para Claude                        │    │
│  │  2. Envía mensaje + tools a Claude API               │    │
│  │  3. Recibe decisión de Claude (tool_use/end_turn)    │    │
│  │  4. Ejecuta tools en servidores MCP vía FastMCP       │    │
│  │  5. Regresa resultados a Claude                       │    │
│  │  6. Repite hasta que Claude termine (loop agentic)    │    │
│  └────────────────────────────────────────────────────────┘    │
└──────┬────────────────────────────────────┬────────────────┬────┘NETWORKDUCK
       │                                    │                │
       │                                    │                │
       ▼                                    ▼                ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  🗞️  MCP GDELT  │  │  🕸️  MCP REBEL  │  │  🤖 MCP EMBED   │
│   :7000/mcp     │  │   :7001/mcp     │  │   :7002/mcp     │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ - update_gdelt  │  │ - extract_kg    │  │ - fit_model     │
│ - query_data    │  │ - save_neo4j    │  │ - discover      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
       │                     │                     │
       ▼                     ▼                     ▼
   DuckDB DB          Neo4j Graph DB      PyTorch Models
```

### Estructura del Proyecto

```
cliente_mcp/
├── src/
│   └── cliente_mcp/
│       ├── __init__.py
│       ├── app.py                      # Interfaz Gradio (UI - punto de entrada)
│       ├── client.py                   # Cliente MCP (solo servidores MCP)
│       │
│       ├── llm_providers/              # 🆕 Abstracción del LLM
│       │   ├── __init__.py
│       │   ├── base.py                 # Interfaz LLMProvider
│       │   └── anthropic_provider.py   # Implementación Anthropic/Claude
│       │
│       ├── orchestration/              # 🆕 Orquestación de conversación
│       │   ├── __init__.py
│       │   ├── conversation_orchestrator.py  # Loop de conversación
│       │   └── tool_executor.py              # Ejecución y validación de tools
│       │
│       ├── core/                       # Configuración y modelos
│       │   ├── __init__.py
│       │   ├── config.py               # Configuración de tools
│       │   ├── models.py               # Dataclasses y modelos
│       │   └── storage.py              # Estado de conversación
│       │
│       ├── handlers/                   # Handlers por tipo de tool
│       │   ├── __init__.py
│       │   ├── construction_handler.py
│       │   ├── preconsulta_handler.py
│       │   ├── query_handler.py
│       │   ├── synthesis_handler.py
│       │   └── synthetic_tools.py
│       │
│       ├── templates/                  # Generación de prompts dinámicos
│       │   ├── __init__.py
│       │   ├── dynamic_prompts.py      # Builder de prompts por fase
│       │   ├── synthesis_template.py
│       │   └── prompts/                # Templates Jinja2
│       │       ├── base.j2
│       │       ├── construccion.j2
│       │       ├── consultas.j2
│       │       ├── preconsulta.j2
│       │       └── sintesis.j2
│       │
│       ├── utils/                      # Utilidades
│       │   ├── __init__.py
│       │   └── logger_config.py        # Configuración de logging
│       │
│       └── validators/                 # Validación de workflow
│           ├── __init__.py
│           ├── tool_classifier.py
│           └── workflow_validator.py
│
├── Dockerfile                   # Multi-stage build con uv
├── .dockerignore                # Exclusiones para Docker build
├── pyproject.toml               # Dependencias del proyecto
├── uv.lock                      # Lockfile reproducible
├── .env                         # Variables de entorno (NO COMMITEAR)
├── README.md                    # Este archivo
├── ARCHITECTURE.md              # 📘 Documentación de arquitectura
├── DOCKER.md                    # 🐳 Guía completa de Docker
└── validate_docker.sh           # Script de validación pre-build
```

## 🚀 Inicio Rápido

### Prerrequisitos

- Python 3.12+ (para ejecución local)
- Docker (para ejecución en contenedor)
- Servidores MCP corriendo (GDELT, REBEL, Embedding)
- API Key de Anthropic

### Opción 1: Ejecución Local

**1. Instalar dependencias:**
```bash
uv sync
```

**2. Ejecutar aplicación:**
```bash
python -m src.cliente_mcp.app
```

**3. Abrir navegador:**
```
http://localhost:7860
```

### Opción 2: Ejecución con Docker

**1. Construir la imagen:**
```bash
docker build -t cliente-mcp:latest .
```

**2. Ejecutar el contenedor:**
```bash
docker run -d \
  --name cliente-mcp \
  --env-file .env \
  -p 7860:7860 \
  -v $(pwd)/logs:/app/logs \
  cliente-mcp:latest
```

**3. Ver logs del contenedor:**
```bash
docker logs -f cliente-mcp
```

**4. Abrir navegador:**
```
http://localhost:7860
```

## ⚙️ Configuración

### Variables de Entorno (.env)

```bash
### Anthropic API
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

### URLs de Servidores MCP
# ⚠️ IMPORTANTE: FastMCP expone  el endpoint /mcp
GDELT_MCP_URL=http://localhost:7000/mcp
REBEL_MCP_URL=http://localhost:7001/mcp
EMBEDDING_MCP_URL=http://localhost:7002/mcp

### Configuración de Claude
CLAUDE_MODEL=claude-3-5-haiku-20241022
CLAUDE_MAX_TOKENS=1024
```
