"""
Agente GraphRAG — SDK Loop (condicion_evaluada: sdk_loop)

Arquitectura: Anthropic SDK tool-calling loop + MCP tools via fastmcp.Client.
El LLM razona en cada iteracion que herramienta llamar y cuando detenerse,
a diferencia del pipeline deterministico de agente2KGE.

Uso standalone:
    python agente_sdk.py "tendencia de New Zealand"
    python agente_sdk.py "que pasa con China"

Uso como modulo (desde tool_executor):
    from agentGraphRag.agente_sdk import GraphRAGAgent, MCPToolManager, build_system_prompt
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastmcp import Client as MCPClient
from loguru import logger
from pydantic import BaseModel, Field

# ── Rutas ──────────────────────────────────────────────────────────────────

_THIS          = Path(__file__).resolve()
CLAUDE_MD_PATH = _THIS.parent / "CLAUDE.md"         # agentGraphRag/CLAUDE.md
ENV_PATH       = _THIS.parents[2] / ".env"           # …/cliente_mcp/.env
LOGS_DIR       = Path("logs")

load_dotenv(ENV_PATH)

# Log dedicado para Agente 2 — escribe solo mensajes con prefijo "AGENTE 2:"
LOGS_DIR.mkdir(exist_ok=True)
logger.add(
    LOGS_DIR / "agente2_debug.log",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    filter=lambda r: r["message"].startswith("AGENTE 2:"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
    enqueue=True,
)

# ── Configuracion ──────────────────────────────────────────────────────────

EMBEDDING_URL  = "http://192.168.0.20:7002/mcp"
MODEL          = "claude-sonnet-4-6"
MAX_ITERATIONS = 25

ALLOWED_TOOLS = {
    "check_country_in_graph",
    "expand_graph_from_country",
    "get_articles_by_triplet",
    "get_inferred_relations_by_country",
    "discover_top_n",
    "search_similar_entities",
    "execute_custom_cypher_query",
}


# ── Pydantic — Schema del JSON de salida ───────────────────────────────────

class EventoRelevante(BaseModel):
    gkg_record_id: str
    fecha: str
    fuente: str
    url: str
    tono: float
    triplet: str


class ResultadoFinal(BaseModel):
    resumen: str
    entidades_clave:        list[str] = Field(default_factory=list)
    relaciones_detectadas:  list[str] = Field(default_factory=list)
    inferencias_simbolicas: list[str] = Field(default_factory=list)
    inferencias_kge:        list[str] = Field(default_factory=list)
    entidades_similares_kge: list[str] = Field(default_factory=list)
    eventos_relevantes:     list[EventoRelevante] = Field(default_factory=list)
    fuentes_citadas:        list[str] = Field(default_factory=list)
    recomendacion: str


class Trazabilidad(BaseModel):
    triplets_usados: int
    triplets_con_articulo_verificado: int
    score: float


class GraphRAGResponse(BaseModel):
    condicion_evaluada: str = "sdk_loop"
    pais_consultado: str
    resultado_final: ResultadoFinal
    trazabilidad: Trazabilidad


class GraphRAGError(BaseModel):
    error: str = "pais_no_encontrado"
    pais_consultado: str
    available_countries: list[str] = Field(default_factory=list)


# ── MCPToolManager ─────────────────────────────────────────────────────────

class MCPToolManager:
    """
    Conecta al servidor MCP usando fastmcp.Client.
    Cada operacion abre y cierra su propia conexion HTTP via async with.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._client = MCPClient(url)
        self._tools_meta: list = []

    async def initialize(self) -> None:
        logger.debug(f"[GraphRAG] Conectando a MCP: {self.url}")
        logger.info(f"[GraphRAG] Conectando a MCP: {self.url}")
        async with self._client:
            all_tools = await self._client.list_tools()
        self._tools_meta = [t for t in all_tools if t.name in ALLOWED_TOOLS]
        logger.debug(f"[GraphRAG] Tools cargadas ({len(self._tools_meta)}): "
                    f"{[t.name for t in self._tools_meta]}")
        logger.info(f"[GraphRAG] Tools cargadas ({len(self._tools_meta)}): "
                    f"{[t.name for t in self._tools_meta]}")

    def to_anthropic_format(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema or {"type": "object", "properties": {}},
            }
            for t in self._tools_meta
        ]

    async def call(self, name: str, arguments: dict) -> str:
        if name not in {t.name for t in self._tools_meta}:
            return f"ERROR: tool '{name}' no permitida."
        try:
            async with self._client:
                result = await self._client.call_tool(name, arguments)
            parts = [c.text if hasattr(c, "text") else str(c) for c in result.content]
            return "\n".join(parts) if parts else "Sin resultado."
        except Exception as exc:
            return f"ERROR ejecutando {name}: {exc}"


# ── GraphRAGAgent ──────────────────────────────────────────────────────────

class GraphRAGAgent:
    """
    Loop de razonamiento con Anthropic SDK.
    El LLM decide que tool llamar en cada paso y cuando detenerse.
    """

    def __init__(self, tool_manager: MCPToolManager, system_prompt: str) -> None:
        self._llm    = anthropic.Anthropic()
        self._tools  = tool_manager
        self._system = system_prompt

    async def run(self, query: str) -> dict:
        logger.debug(f"AGENTE 2: Iniciando | query: {query[:80]}")
        logger.info(f"AGENTE 2: Iniciando | query: {query[:80]}")
        logger.debug(f"AGENTE 2: Modelo={MODEL} | Max iteraciones={MAX_ITERATIONS}")
        logger.info(f"AGENTE 2: Modelo={MODEL} | Max iteraciones={MAX_ITERATIONS}")
        ant_tools = self._tools.to_anthropic_format()
        logger.debug(f"AGENTE 2: Tools disponibles: {[t['name'] for t in ant_tools]}")
        logger.info(f"AGENTE 2: Tools disponibles: {[t['name'] for t in ant_tools]}")
        messages: list[dict] = [{"role": "user", "content": query}]

        for step in range(1, MAX_ITERATIONS + 1):
            logger.debug(f"AGENTE 2: ── Paso {step:02d}/{MAX_ITERATIONS} ──")
            logger.info(f"AGENTE 2: ── Paso {step:02d}/{MAX_ITERATIONS} ──")
            response = self._llm.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=self._system,
                tools=ant_tools,
                messages=messages,
            )
            logger.debug(f"AGENTE 2: stop_reason={response.stop_reason} | tokens={response.usage.input_tokens}in/{response.usage.output_tokens}out")
            logger.info(f"AGENTE 2: stop_reason={response.stop_reason} | tokens={response.usage.input_tokens}in/{response.usage.output_tokens}out")
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                result = self._parse_json(response)
                if "error" in result:
                    logger.warning(f"AGENTE 2: Finalizado con error: {result}")
                else:
                    logger.debug(f"AGENTE 2: Completado OK | pais={result.get('pais_consultado','?')}")
                    logger.info(f"AGENTE 2: Completado OK | pais={result.get('pais_consultado','?')}")
                return result

            if response.stop_reason == "tool_use":
                tool_results = await self._dispatch_tools(response.content)
                messages.append({"role": "user", "content": tool_results})
            else:
                logger.warning(f"AGENTE 2: stop_reason inesperado: {response.stop_reason}")
                break

        logger.error("AGENTE 2: Límite de iteraciones alcanzado")
        return {"error": "max_iterations_exceeded"}

    async def _dispatch_tools(self, blocks: list) -> list[dict]:
        results = []
        for block in blocks:
            if block.type == "tool_use":
                logger.debug(f"AGENTE 2: Tool → {block.name} | args={json.dumps(block.input, ensure_ascii=False)[:150]}")
                logger.info(f"AGENTE 2: Tool → {block.name} | args={json.dumps(block.input, ensure_ascii=False)[:150]}")
                output = await self._tools.call(block.name, block.input)
                logger.debug(f"AGENTE 2: Resultado ← {str(output)[:300]}")
                logger.info(f"AGENTE 2: Resultado ← {str(output)[:300]}")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })
        return results

    @staticmethod
    def _parse_json(response) -> dict:
        for block in response.content:
            if hasattr(block, "text"):
                text  = block.text.strip()
                start = text.find("{")
                end   = text.rfind("}") + 1
                if start != -1 and end > start:
                    try:
                        return json.loads(text[start:end])
                    except json.JSONDecodeError as e:
                        logger.warning(f"AGENTE 2: JSON parse error: {e}")
        logger.error("AGENTE 2: No se pudo parsear JSON de la respuesta")
        return {"error": "json_parse_failed"}


# ── Helpers ────────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    """Carga CLAUDE.md local y ajusta condicion_evaluada para sdk_loop."""
    if not CLAUDE_MD_PATH.exists():
        raise FileNotFoundError(f"No se encontro CLAUDE.md en: {CLAUDE_MD_PATH}")
    content = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    return content.replace('"condicion_evaluada": "con_kge"', '"condicion_evaluada": "sdk_loop"')


def save_result(result: dict, filename: str = "agente.json") -> None:
    """Guarda el resultado del agente en logs/<filename>."""
    try:
        LOGS_DIR.mkdir(exist_ok=True)
        path = LOGS_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.debug(f"[GraphRAG] Resultado guardado en {path.resolve()}")
        logger.info(f"[GraphRAG] Resultado guardado en {path.resolve()}")
    except Exception as exc:
        logger.error(f"[GraphRAG] Error guardando {filename}: {exc}")


def serialize_output(raw: dict) -> str:
    """Valida con Pydantic y serializa como JSON string."""
    try:
        if raw.get("error") == "pais_no_encontrado":
            return GraphRAGError(**raw).model_dump_json(indent=2)
        return GraphRAGResponse(**raw).model_dump_json(indent=2)
    except Exception as exc:
        return json.dumps(
            {"validation_error": str(exc), "raw": raw},
            indent=2, ensure_ascii=False,
        )


# ── Entry point standalone ─────────────────────────────────────────────────

async def main() -> None:
    if len(sys.argv) < 2:
        logger.error('Uso: python agente_sdk.py "consulta sobre un pais"')
        sys.exit(1)

    query         = " ".join(sys.argv[1:])
    system_prompt = build_system_prompt()

    tool_manager = MCPToolManager(EMBEDDING_URL)
    await tool_manager.initialize()

    agent = GraphRAGAgent(tool_manager, system_prompt)
    raw   = await agent.run(query)

    save_result(raw)
    print(serialize_output(raw))


if __name__ == "__main__":
    asyncio.run(main())
