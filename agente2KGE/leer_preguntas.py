"""
Lee preguntas.json y las imprime numeradas para que el agente las procese.
Uso: python leer_preguntas.py
"""

import json
from pathlib import Path

PREGUNTAS_PATH = Path(__file__).parent / "preguntas.json"


def main():
    preguntas = json.loads(PREGUNTAS_PATH.read_text(encoding="utf-8"))
    total = len(preguntas)
    print(f"TOTAL:{total}")
    for i, item in enumerate(preguntas, 1):
        print(f"[{i}/{total}] {item['pregunta']}")


if __name__ == "__main__":
    main()
