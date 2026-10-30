"""
Conversation Orchestrator: Orquesta el loop de conversación.
Desacoplado del LLM específico mediante LLMProvider.
"""

from typing import Optional, List, Tuple
from loguru import logger
import uuid
import json

from cliente_mcp.llm_providers.base import LLMProvider
from cliente_mcp.core.storage import ConversationStore
from cliente_mcp.templates.dynamic_prompts import DynamicPromptBuilder
from cliente_mcp.orchestration.tool_executor import ToolExecutor
from cliente_mcp.handlers.synthetic_tools import get_all_synthetic_tools


class ConversationOrchestrator:
    """
    Orquestador de conversación agnóstico del LLM.

    Responsabilidades:
    - Gestionar el loop de conversación
    - Construir mensajes para el LLM
    - Coordinar ejecución de tools
    - Mantener historial de conversación
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        mcp_client,
        store: ConversationStore,
        prompt_builder: DynamicPromptBuilder,
        tool_executor: ToolExecutor,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ):
        """
        Inicializa el orchestrator.

        Args:
            llm_provider: Provider del LLM (Anthropic, OpenAI, etc.)
            mcp_client: Cliente MCP para listar tools
            store: ConversationStore para estado
            prompt_builder: Builder de prompts dinámicos
            tool_executor: Executor de tools
            max_tokens: Máximo de tokens
            temperature: Temperatura del LLM
        """
        self.llm = llm_provider
        self.mcp_client = mcp_client
        self.store = store
        self.prompt_builder = prompt_builder
        self.tool_executor = tool_executor
        self.max_tokens = max_tokens
        self.temperature = temperature

        logger.info("✓ ConversationOrchestrator inicializado")

    async def chat(
        self,
        user_message: str,
        conversation_history: Optional[List] = None
    ) -> Tuple[str, List]:
        """
        Loop principal de conversación.

        Args:
            user_message: Mensaje del usuario
            conversation_history: Historial previo (opcional)

        Returns:
            Tupla (respuesta_final, historial_actualizado)
        """
        # Crear ID único para esta conversación
        conversation_id = str(uuid.uuid4())[:8]
        log = logger.bind(conversation_id=conversation_id)

        # Actualizar store con metadata
        self.store.conversation_id = conversation_id
        self.store.set_user_question(user_message)

        log.info("="*70)
        log.info("💬 Iniciando conversación con LLM")
        log.info("="*70)

        # Construir mensajes
        if conversation_history is None:
            messages = [{"role": "user", "content": user_message}]
            log.info("📝 Nueva conversación (sin historial)")
        else:
            messages = conversation_history.copy()
            messages.append({"role": "user", "content": user_message})
            log.info(f"📝 Continuando conversación | Historial: {len(conversation_history)} mensajes")

        log.info(f"📨 Mensaje recibido: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")

        # Loop de conversación
        max_iterations = 30
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            log.info(f"🔄 Iteración {iteration}/{max_iterations}")

            # Generar prompt dinámico según fase actual
            system_prompt = self.get_system_prompt()

            # Filtrar tools según fase actual
            llm_tools = self._get_tools_for_phase()
            log.info(f"🔧 Tools activas ({len(llm_tools)}): {[t['name'] for t in llm_tools]}")

            # Log del system prompt
            log.debug("="*70)
            log.debug("📋 SYSTEM PROMPT DINÁMICO")
            log.debug(f"Fase actual | Caracteres: {len(system_prompt)}")
            log.debug("="*70)

            # ==================== LOG MESSAGES ====================
            log.debug("="*70)
            log.debug("📤 MESSAGES ENVIADO AL LLM")
            log.debug("="*70)
            log.debug(json.dumps(messages, indent=2, ensure_ascii=False))
            log.debug("="*70)
            # ======================================================

            # Llamar al LLM (agnóstico del provider)
            response = await self.llm.chat(
                messages=messages,
                system_prompt=system_prompt,
                tools=llm_tools,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            # ==================== LOG RESPONSE ====================
            log.debug("="*70)
            log.debug("📥 RESPONSE RECIBIDO DEL LLM")
            log.debug(f"Stop reason: {response.stop_reason}")
            log.debug(f"Tool calls: {len(response.tool_calls)}")
            log.debug(f"Content preview: {response.content[:200]}...")
            log.debug("="*70)
            # ======================================================

            log.info(f"✓ LLM respondió | Stop reason: {response.stop_reason}")

            # Agregar respuesta del asistente a mensajes
            assistant_message = self.llm.serialize_assistant_message(response.raw_content)
            messages.append(assistant_message)

            # Verificar si LLM quiere usar tools
            if response.stop_reason == "tool_use":
                tool_results = await self.tool_executor.execute_tools(
                    response.tool_calls,
                    log
                )

                # Si synthesize_final_response fue llamado, retornar su resultado directo
                synth_call = next(
                    (tc for tc in response.tool_calls if tc.name == "synthesize_final_response"),
                    None
                )
                if synth_call:
                    synth_result = next(
                        (tr["content"] for tr in tool_results if tr["tool_use_id"] == synth_call.id),
                        None
                    )
                    if synth_result:
                        log.info("✅ Retornando JSON de Agente 2 directo — sin pasar por LLM")
                        return synth_result, messages

                # Crear mensaje con resultados en formato del LLM
                tool_result_message = self.llm.create_tool_result_message(tool_results)
                messages.append(tool_result_message)

                log.info(f"↻ Enviando {len(tool_results)} resultados al LLM...")

            elif response.stop_reason == "complete":
                log.info(f"✓ Conversación completada | Respuesta: {len(response.content)} chars")
                log.info("═"*70)
                return response.content, messages

            else:
                log.warning(f"⚠️  Stop reason inesperado: {response.stop_reason}")
                break

        log.warning(f"⚠️  Límite de iteraciones alcanzado ({max_iterations})")
        return "No se pudo completar la conversación (max iterations)", messages

    def get_system_prompt(self) -> str:
        """
        Obtiene el system prompt dinámico para la fase actual.

        Returns:
            System prompt generado según la fase actual del workflow
        """
        return self.prompt_builder.build(self.store)

    def _get_tools_for_phase(self) -> list:
        """
        Retorna solo las tools relevantes para la fase actual.
        En modo bypass: construcción → 3 tools; síntesis → solo synthesize_final_response.
        """
        from cliente_mcp.templates.dynamic_prompts import detect_phase

        if self.store.skip_intermediate_phases:
            fase = detect_phase(self.store)
            if fase == "construccion":
                allowed = {"update_gdelt_data", "extract_knowledge_graph", "initial_fit_model"}
                mcp_tools = [t for t in self.mcp_client.list_tools() if t.name in allowed]
                return self.llm.format_tools(mcp_tools)
            else:
                return get_all_synthetic_tools()

        # Flujo normal: todas las tools
        mcp_tools = self.mcp_client.list_tools()
        llm_tools = self.llm.format_tools(mcp_tools)
        llm_tools.extend(get_all_synthetic_tools())
        return llm_tools

    def reset_conversation_state(self):
        """Resetea el estado de la conversación."""
        self.store.reset()
        logger.info("🔄 Estado de conversación reseteado")
