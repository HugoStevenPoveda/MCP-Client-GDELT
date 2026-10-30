# MCP-Cliente

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![MCP](https://img.shields.io/badge/protocol-MCP-black)
![Status](https://img.shields.io/badge/status-research-orange)

Cliente/agente que consume los 3 servidores [MCP](https://modelcontextprotocol.io) de [`MCP-Server`](../MCP-Server) (GDELT, REBEL, Embedding) para construir un grafo de conocimiento geopolítico bajo demanda y responder consultas sobre él.

## Dos agentes

| Agente | Rol | Dónde vive |
|---|---|---|
| **Agente 1 — Graph Builder** | Orquesta los MCP de GDELT/REBEL/Embedding para construir el grafo on-demand en Neo4j (ingesta → extracción de tripletas → entrenamiento KGE) | [`cliente_mcp/`](cliente_mcp/README.md) — `ConversationOrchestrator` + `handlers/` |
| **Agente 2 — GraphRAG Retrieval** | ReAct loop (tool-calling) que consulta el grafo ya construido (BFS, inferencia simbólica, link prediction KGE) y sintetiza la respuesta final en JSON | Dos implementaciones, ver abajo |

El Agente 2 tiene **dos implementaciones** del mismo flujo de retrieval:

- **`cliente_mcp/src/agentGraphRag/agente_sdk.py`** (`condicion_evaluada: "sdk_loop"`) — loop de tool-calling con el SDK de Anthropic + `fastmcp.Client`, invocado por el orquestador de `cliente_mcp` tras la fase de síntesis dentro de la app Gradio.
- **`agente2KGE/`** (`condicion_evaluada: "con_kge"`) — el mismo flujo pero ejecutado vía Claude Code CLI (`CLAUDE.md` como prompt del agente + `.mcp.json` apuntando directo al `embedding-api`), usado para correr un batch de preguntas (`preguntas.json` → `leer_preguntas.py` / `guardar_resultado.py`).

## Estructura

```
MCP-Cliente/
├── cliente_mcp/        # App principal: Gradio UI + Agente 1 + Agente 2 (SDK loop)
│   ├── README.md       # Instalación, Docker, variables de entorno
│   └── ARCHITECTURE.md # Diseño detallado de cliente_mcp (patrones, flujo de datos)
└── agente2KGE/          # Runner batch de Agente 2 vía Claude Code
    ├── CLAUDE.md        # Prompt/flujo obligatorio del agente
    ├── preguntas.json   # Consultas de entrada
    └── guardar_resultado.py / leer_preguntas.py
```

Para instalación, Docker y configuración de `.env`, ver [`cliente_mcp/README.md`](cliente_mcp/README.md).
