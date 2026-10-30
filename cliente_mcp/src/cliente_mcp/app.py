"""
Interfaz Gradio para el cliente MCP.
"""

import warnings
# Suprimir warnings de deprecación de websockets en uvicorn
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn")

import gradio as gr
import asyncio
import os
from dotenv import load_dotenv

# Importar nueva arquitectura
from cliente_mcp.client import MCPClient
from cliente_mcp.llm_providers import AnthropicProvider
from cliente_mcp.orchestration import ConversationOrchestrator, ToolExecutor
from cliente_mcp.core.storage import ConversationStore
from cliente_mcp.core.config import TOOL_CONFIG
from cliente_mcp.validators.tool_classifier import ToolClassifier
from cliente_mcp.validators.workflow_validator import WorkflowValidator
from cliente_mcp.handlers.construction_handler import ConstructionHandler
from cliente_mcp.handlers.preconsulta_handler import PreconsultaHandler
from cliente_mcp.handlers.query_handler import QueryHandler
from cliente_mcp.handlers.synthesis_handler import SynthesisHandler
from cliente_mcp.templates.synthesis_template import SynthesisTemplateBuilder
from cliente_mcp.templates.dynamic_prompts import DynamicPromptBuilder
from agentGraphRag.agente_sdk import GraphRAGAgent, MCPToolManager, build_system_prompt

# Cargar variables de entorno
load_dotenv()

# Globals
mcp_client = None
orchestrator = None


def load_config():
    """Carga la configuración desde variables de entorno."""
    config = {
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
        "server_urls": [
            {"name": "GDELT", "url": os.getenv("GDELT_MCP_URL", "http://192.168.0.27:7000/mcp")},
            {"name": "REBEL", "url": os.getenv("REBEL_MCP_URL", "http://192.168.0.27:7001/sse")},
            {"name": "EMBEDDING", "url": os.getenv("EMBEDDING_MCP_URL", "http://192.168.0.27:7002/mcp")},
        ],
        "model": os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
        "max_tokens": int(os.getenv("CLAUDE_MAX_TOKENS", "1024")),
    }
    if not config["anthropic_api_key"]:
        raise ValueError("ANTHROPIC_API_KEY no configurada en .env")

    print("✅ [CONFIG] Configuración cargada correctamente\n")
    return config


async def startup():
    """Inicializa y conecta todos los componentes."""
    global mcp_client, orchestrator

    config = load_config()

    # 1. Crear y conectar cliente MCP (solo servidores MCP)
    mcp_client = MCPClient(server_urls=config["server_urls"])
    await mcp_client.connect()
    print("MODEL ", config["model"])

    # 1b. Inicializar GraphRAG Agent (Agente 2)
    graphrag_tool_manager = MCPToolManager(
        os.getenv("EMBEDDING_MCP_URL", "http://192.168.0.20:7002/mcp")
    )
    await graphrag_tool_manager.initialize()
    graphrag_agent = GraphRAGAgent(graphrag_tool_manager, build_system_prompt())

    # 2. Crear provider del LLM (desacoplado)
    llm_provider = AnthropicProvider(
        api_key=config["anthropic_api_key"],
        model=config["model"]
    )

    # 3. Crear componentes de lógica de negocio
    store = ConversationStore()
    store.skip_intermediate_phases = os.getenv("SKIP_INTERMEDIATE_PHASES", "true").lower() == "true"
    classifier = ToolClassifier(TOOL_CONFIG)
    validator = WorkflowValidator(classifier, store)
    template_builder = SynthesisTemplateBuilder()
    prompt_builder = DynamicPromptBuilder()

    # 4. Crear handlers
    construction_handler = ConstructionHandler(store, classifier)
    preconsulta_handler = PreconsultaHandler(store, classifier)
    query_handler = QueryHandler(store)
    synthesis_handler = SynthesisHandler(store, template_builder)

    # 5. Crear tool executor (con GraphRAG Agent integrado)
    tool_executor = ToolExecutor(
        validator=validator,
        classifier=classifier,
        construction_handler=construction_handler,
        preconsulta_handler=preconsulta_handler,
        query_handler=query_handler,
        synthesis_handler=synthesis_handler,
        tool_to_client_map=mcp_client.tool_to_client,
        graphrag_agent=graphrag_agent,
    )

    # 6. Crear orchestrator (punto de entrada principal)
    orchestrator = ConversationOrchestrator(
        llm_provider=llm_provider,
        mcp_client=mcp_client,
        store=store,
        prompt_builder=prompt_builder,
        tool_executor=tool_executor,
        max_tokens=config["max_tokens"],
        temperature=0.0
    )

    print("\n" + "=" * 70)
    print("✅ [STARTUP] Sistema completo inicializado y listo")
    print("=" * 70 + "\n")


def chat_sync(message, history):
    """
    Función de chat sincrónica para Gradio.
    Usa el orchestrator desacoplado del LLM.

    Args:
        message: Mensaje nuevo del usuario
        history: Lista de diccionarios [{"role": "user", "content": "..."}, ...]

    Returns:
        Lista de diccionarios actualizada con el nuevo intercambio
    """
    print("\n" + "="*80)
    print(f"📝 [GRADIO] Mensaje del usuario: {message}")
    print(f"📚 [GRADIO] Historial previo: {len(history)} intercambios\n")

    if orchestrator is None:
        print("❌ [GRADIO] Error: Sistema no inicializado")
        error_msg = "❌ Error: Sistema no inicializado. Verifica los logs."
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": error_msg})
        return history

    conversation_history = [
        {"role": msg.get("role"), "content": msg.get("content")}
        for msg in history
        if msg.get("role") and msg.get("content")
    ]

    for idx, msg in enumerate(conversation_history):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:60]
        print(f"   [{idx+1}] {role}: {content}...")

    # Ejecutar chat async de forma sincrónica usando orchestrator
    try:
        print("🚀 [GRADIO] Llamando a orchestrator.chat()...")
        response, _ = asyncio.run(orchestrator.chat(message, conversation_history))
        print(f"📤 [GRADIO] Respuesta (primeros 150 chars): {response[:150]}...")

        # Agregar el nuevo intercambio al historial
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        print(f"💾 [GRADIO] Historial actualizado: {len(history)} mensajes totales")
        print("="*80 + "\n")

        return history
    except Exception as e:
        print(f"\n❌ [GRADIO] Error en chat_sync: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*80 + "\n")

        error_msg = f"❌ Error: {str(e)}"
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": error_msg})
        return history


def main():
    """Función principal que inicia la interfaz Gradio."""

    # Inicializar sistema completo
    try:
        asyncio.run(startup())
    except Exception as e:
        print(f"\n❌ Error al inicializar sistema: {e}")
        print("Verifica que:")
        print("  1. Los servidores MCP estén corriendo")
        print("  2. El archivo .env esté configurado correctamente")
        print("  3. ANTHROPIC_API_KEY esté definida\n")
        import traceback
        traceback.print_exc()
        return

    # Crear interfaz Gradio
    with gr.Blocks(title="Cliente MCP") as demo:
        gr.Markdown(
            """
            # 🤖 Cliente MCP - Knowledge Graph Pipeline

            Interactúa con Claude usando herramientas de los servidores MCP:
            - **GDELT**: Noticias comerciales
            - **REBEL**: Extracción de grafos de conocimiento
            - **EMBEDDING**: Modelos de embeddings
            """
        )

        chatbot = gr.Chatbot(
            label="Conversación",
            height=500,
            show_copy_button=True,
            type='messages'
        )

        msg = gr.Textbox(
            label="Tu mensaje",
            placeholder="Escribe tu consulta aquí...",
            lines=2
        )

        with gr.Row():
            submit = gr.Button("Enviar", variant="primary")
            clear = gr.Button("Limpiar")

        gr.Markdown("### 📝 Ejemplos de consultas")

        gr.Examples(
            examples=[
                "Actualiza los datos de GDELT de los últimos 30 minutos",
                "¿Cuántas noticias hay sobre China?",
                "Muéstrame las 5 noticias más recientes sobre semiconductores",
                "Extrae el grafo de conocimiento de 10 artículos y guárdalo en Neo4j",
                "Entrena el modelo de embeddings con 50 épocas",
            ],
            inputs=msg,
            label="Prueba estas consultas"
        )

        # Event handlers
        submit.click(
            fn=chat_sync,
            inputs=[msg, chatbot],
            outputs=chatbot
        ).then(
            lambda: "",
            outputs=msg
        )

        msg.submit(
            fn=chat_sync,
            inputs=[msg, chatbot],
            outputs=chatbot
        ).then(
            lambda: "",
            outputs=msg
        )

        clear.click(lambda: None, None, chatbot, queue=False)

    # Lanzar interfaz
    print("\n🌐 Lanzando interfaz Gradio en http://0.0.0.0:7860\n")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True
    )


if __name__ == "__main__":
    main()
