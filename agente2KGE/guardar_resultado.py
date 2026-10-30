"""
Guarda el JSON resultado del agente como resultados/{nombre_pregunta}.json
Si el JSON recibido esta vacio o es None, guarda la estructura con campos vacios.

Uso: python guardar_resultado.py "nombre de la pregunta" '{"json": ...}'
     python guardar_resultado.py "nombre de la pregunta"   <- guarda JSON vacio
"""

import json
import re
import sys
from pathlib import Path

RESULTADOS_DIR = Path(__file__).parent / "resultados"

EMPTY_RESULT = {
    "condicion_evaluada": "con_kge",
    "pais_consultado": "",
    "resultado_final": {
        "resumen": "",
        "entidades_clave": [],
        "relaciones_detectadas": [],
        "inferencias_simbolicas": [],
        "inferencias_kge": [],
        "entidades_similares_kge": [],
        "eventos_relevantes": [],
        "fuentes_citadas": [],
        "recomendacion": "",
    },
    "trazabilidad": {
        "triplets_usados": 0,
        "triplets_con_articulo_verificado": 0,
        "score": 0.0,
    },
}


def sanitize(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name)
    return name[:120]


def main():
    if len(sys.argv) < 2:
        print("ERROR: Falta el nombre de la pregunta")
        sys.exit(1)

    pregunta = sys.argv[1]
    json_str = sys.argv[2] if len(sys.argv) >= 3 else None

    if json_str:
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON inválido — {e}. Guardando estructura vacía.")
            data = EMPTY_RESULT.copy()
            data["pais_consultado"] = pregunta
    else:
        data = EMPTY_RESULT.copy()
        data["pais_consultado"] = pregunta

    RESULTADOS_DIR.mkdir(exist_ok=True)
    filename = sanitize(pregunta) + ".json"
    path = RESULTADOS_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"GUARDADO: {path}")


if __name__ == "__main__":
    main()
