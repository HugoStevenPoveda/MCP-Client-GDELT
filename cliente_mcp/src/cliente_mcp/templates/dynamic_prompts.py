"""
Sistema de prompts dinámicos por fase.
Simple, sin abstracciones complejas - KISS approach.
"""

import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from loguru import logger


# ==================== FUNCIONES SIMPLES ====================

def _load_preconsulta_data(file_path: str = "logs/preconsulta.json") -> dict:
    """
    Carga datos de preconsulta.json si existe.

    Args:
        file_path: Ruta al archivo preconsulta.json

    Returns:
        Dictionary con datos de preconsulta, o {} si no existe
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.debug(f"Archivo {file_path} no encontrado")
        return {}
    except json.JSONDecodeError as e:
        logger.warning(f"Error decodificando {file_path}: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Error cargando {file_path}: {e}")
        return {}


def detect_phase(store) -> str:
    """
    Detecta fase actual basado en store.

    Args:
        store: ConversationStore instance

    Returns:
        Nombre de la fase: "construccion", "preconsulta", "consultas", "sintesis"
    """
    # Fase 1: Construcción
    if not store.is_construction_complete():
        return "construccion"

    # Bypass: saltar PRECONSULTA y QUERY, ir directo a SÍNTESIS
    if getattr(store, 'skip_intermediate_phases', False):
        return "sintesis"

    # Fase 2: Preconsulta
    if not store.is_preconsulta_complete():
        return "preconsulta"

    # Fase 3: Consultas (hasta tener al menos 2 consultas)
    if store.get_query_count() < 2:
        return "consultas"

    # Fase 4: Síntesis
    return "sintesis"


def build_context(store, fase: str) -> dict:
    """
    Construye contexto para template.

    Args:
        store: ConversationStore instance
        fase: Nombre de la fase actual

    Returns:
        Dictionary con variables para el template
    """
    context = {
        "fase": fase,
        "user_question": store.metadata.user_question or "la pregunta del usuario",
        "query_count": store.get_query_count(),
        "skip_phases": getattr(store, 'skip_intermediate_phases', False),
    }

    # Información adicional según fase
    if fase == "construccion":
        context["construction_status"] = store.get_construction_status()

    elif fase == "preconsulta":
        context["preconsulta_status"] = store.get_preconsulta_status()

    elif fase in ["consultas", "sintesis"]:
        context["queries_done"] = store.get_query_count()

        # Cargar datos de preconsulta para mostrar en el prompt
        preconsulta_data = _load_preconsulta_data()

        if preconsulta_data:
            # Extraer relation_types
            relation_types_data = preconsulta_data.get("get_tipos_relaciones", {})
            if isinstance(relation_types_data, dict):
                relaciones_str = relation_types_data.get("relaciones", "")
                # Parse comma-separated string
                if isinstance(relaciones_str, str):
                    relation_types = [r.strip() for r in relaciones_str.split(",") if r.strip()]
                else:
                    relation_types = []
            else:
                relation_types = []
            context["relation_types"] = relation_types

            # Extraer tripletas
            tripletas_info = preconsulta_data.get("query_by_gkg_record_id", {})
            if isinstance(tripletas_info, dict):
                todas_tripletas = tripletas_info.get("tripletas", [])
                context["tripletas_muestra"] = todas_tripletas[:20]  # Primeras 20
                context["total_tripletas"] = len(todas_tripletas)
                context["documentos_procesados"] = tripletas_info.get("documentos_procesados", 0)
            else:
                context["tripletas_muestra"] = []
                context["total_tripletas"] = 0
                context["documentos_procesados"] = 0

            # Extraer record_ids (opcional, para referencia)
            record_ids_data = preconsulta_data.get("get_record_ids_recientes", {})
            if isinstance(record_ids_data, dict):
                ids_value = record_ids_data.get("record_ids", "")
                if isinstance(ids_value, str):
                    record_ids = [rid.strip() for rid in ids_value.split(",") if rid.strip()]
                elif isinstance(ids_value, list):
                    record_ids = [str(rid) for rid in ids_value]
                else:
                    record_ids = []
            else:
                record_ids = []
            context["record_ids"] = record_ids[:10]  # Primeros 10

        else:
            # Defaults if preconsulta.json not found
            context["relation_types"] = []
            context["tripletas_muestra"] = []
            context["total_tripletas"] = 0
            context["documentos_procesados"] = 0
            context["record_ids"] = []

    return context


# ==================== CLASE SIMPLE ====================

class DynamicPromptBuilder:
    """
    Builder simple de prompts dinámicos.
    Una clase, métodos simples, sin complejidad.
    """

    def __init__(self, template_dir: str = None):
        """
        Inicializa el builder.

        Args:
            template_dir: Directorio de templates (opcional, usa default si no se especifica)
        """
        if template_dir is None:
            # Default: buscar en la carpeta de templates
            base_path = Path(__file__).parent / "prompts"
            template_dir = str(base_path)

        logger.debug(f"Inicializando DynamicPromptBuilder con templates en: {template_dir}")

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def build(self, store) -> str:
        """
        Construye prompt para fase actual.

        Args:
            store: ConversationStore instance

        Returns:
            System prompt completo para la fase actual
        """
        # Detectar fase automáticamente
        fase = detect_phase(store)
        logger.info(f"📍 Fase detectada: {fase}")

        # Construir contexto
        context = build_context(store, fase)

        # Cargar y renderizar template
        template = self.env.get_template(f"{fase}.j2")
        prompt = template.render(**context)

        logger.debug(f"✓ Prompt generado para fase '{fase}' ({len(prompt)} chars)")

        return prompt

    def build_for_phase(self, fase: str, store) -> str:
        """
        Construye prompt para fase específica (útil para testing).

        Args:
            fase: Nombre de la fase ("construccion", "preconsulta", etc.)
            store: ConversationStore instance

        Returns:
            System prompt para la fase especificada
        """
        context = build_context(store, fase)
        template = self.env.get_template(f"{fase}.j2")
        return template.render(**context)


# ==================== HELPERS DE DEBUG ====================

def print_current_phase(store):
    """
    Helper para debug: muestra la fase actual y progreso.

    Args:
        store: ConversationStore instance
    """
    fase = detect_phase(store)

    print(f"\n📍 FASE ACTUAL: {fase.upper()}")
    print(f"   Construcción: {'✅' if store.is_construction_complete() else '⏳'}")
    print(f"   Preconsulta: {'✅' if store.is_preconsulta_complete() else '⏳'}")
    print(f"   Queries ejecutadas: {store.get_query_count()}")
    print()


def validate_phase_transition(old_phase: str, new_phase: str) -> bool:
    """
    Valida que una transición de fase sea lógica.

    Args:
        old_phase: Fase anterior
        new_phase: Fase nueva

    Returns:
        True si la transición es válida
    """
    valid_transitions = {
        "construccion": ["preconsulta"],
        "preconsulta": ["consultas"],
        "consultas": ["sintesis"],
        "sintesis": []  # Fase final, no hay transiciones
    }

    return new_phase in valid_transitions.get(old_phase, [])
