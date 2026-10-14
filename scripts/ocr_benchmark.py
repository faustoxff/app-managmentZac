"""Mide qué tan bien lee el OCR las planillas de turnos.

Uso:
    python scripts/ocr_benchmark.py CARPETA [--tessdata DIR]

CARPETA tiene fotos (.jpg/.jpeg/.png) y un esperado.json con [[nombre, telefono], ...]: los
pacientes que tiene la planilla. Todas las fotos de la carpeta son de la misma planilla (la
original y variantes difíciles). Las fotos tienen datos de pacientes: NO van al repo.

Por cada foto informa cuántos pacientes salieron con nombre y teléfono correctos, y cuántas filas
sobran (cosas que el OCR tomó por pacientes y no lo son).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
import ocr_import  # noqa: E402


def puntuar(candidatos, esperado):
    exp = [(db.normalizar_nombre(n), t) for n, t in esperado]
    usados = set()
    nombres = telefonos = completos = 0
    for c in candidatos:
        nombre = db.normalizar_nombre(c.nombre)
        tel = "".join(ch for ch in (c.contacto or "") if ch.isdigit())
        match = next(
            (i for i, (n, t) in enumerate(exp) if i not in usados and (n == nombre or (tel and t == tel))),
            None,
        )
        if match is None:
            continue
        usados.add(match)
        ok_n, ok_t = exp[match][0] == nombre, exp[match][1] == tel
        nombres += ok_n
        telefonos += ok_t
        completos += ok_n and ok_t
    return {
        "completos": completos,
        "nombres": nombres,
        "telefonos": telefonos,
        "sobran": len(candidatos) - len(usados),
        "total": len(exp),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("carpeta", type=Path)
    parser.add_argument("--tessdata", help="carpeta con spa/eng.traineddata a usar")
    args = parser.parse_args()
    if args.tessdata:
        os.environ["TESSDATA_PREFIX"] = args.tessdata

    esperado = json.loads((args.carpeta / "esperado.json").read_text(encoding="utf-8"))
    fotos = sorted(p for p in args.carpeta.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    suma = {"completos": 0, "total": 0, "sobran": 0}
    for foto in fotos:
        inicio = time.time()
        r = puntuar(ocr_import.extraer_candidatos(str(foto)), esperado)
        seg = time.time() - inicio
        print(
            f"{foto.stem:18} completos {r['completos']:2}/{r['total']}  nombres {r['nombres']:2}  "
            f"teléfonos {r['telefonos']:2}  sobran {r['sobran']}  ({seg:.1f}s)"
        )
        for k in suma:
            suma[k] += r[k]
    print(f"{'TOTAL':18} completos {suma['completos']}/{suma['total']}  sobran {suma['sobran']}")


if __name__ == "__main__":
    main()
