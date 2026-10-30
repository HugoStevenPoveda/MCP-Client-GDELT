"""
Módulo de configuración de logging para el cliente MCP.
Configura loguru con múltiples handlers para diferentes niveles de log.
"""

from loguru import logger


def setup_logger(
    log_dir: str = "logs",
    debug_level: str = "DEBUG",
    info_level: str = "INFO",
    error_level: str = "ERROR",
    rotation: str = "50 MB",
    retention: str = "7 days",
    compression: str = "zip",
    enable_console: bool = True
):
    """
    Configura el sistema de logging con múltiples handlers.

    Args:
        log_dir: Directorio base para archivos de log (default: "logs")
        debug_level: Nivel mínimo para log detallado (default: "DEBUG")
        info_level: Nivel mínimo para log compacto (default: "INFO")
        error_level: Nivel mínimo para log de errores (default: "ERROR")
        rotation: Criterio de rotación de archivos (default: "50 MB")
        retention: Tiempo de retención de logs (default: "7 days")
        compression: Formato de compresión (default: "zip")
        enable_console: Habilitar salida en consola (default: True)

    Crea tres archivos de log:
        - chat_debug.log: Log detallado con DEBUG y superior
        - chat_info.log: Log compacto con INFO y superior
        - chat_errors.log: Solo errores críticos (ERROR y superior)

    Ejemplos:
        >>> setup_logger()  # Configuración por defecto
        >>> setup_logger(log_dir="my_logs", rotation="100 MB")  # Personalizado
    """
    # Remover handler por defecto de loguru
    logger.remove()

    # Log detallado (DEBUG): rotación diaria, mantener 7 días
    logger.add(
        f"{log_dir}/chat_debug.log",
        level=debug_level,
        rotation=rotation,
        retention=retention,
        compression=compression,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        enqueue=True  # Thread-safe para async
    )

    # Log INFO y superior: más compacto
    logger.add(
        f"{log_dir}/chat_info.log",
        level=info_level,
        rotation=rotation,
        retention=retention,
        compression=compression,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        enqueue=True
    )

    # Log solo errores críticos
    logger.add(
        f"{log_dir}/chat_errors.log",
        level=error_level,
        rotation=rotation,
        retention=retention,
        compression=compression,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {extra[conversation_id]} | {message}",
        enqueue=True
    )

    # Opcional: Mantener salida en consola para desarrollo
    if enable_console:
        logger.add(
            lambda msg: print(msg, end=""),
            level=info_level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            colorize=True
        )
