#!/usr/bin/env python3
"""
Resultados del día para la página (Capafy AI).
Lee EnLotería y escribe hoy.json SOLO si hay cambios (para no llenar el historial).
No toca la base de datos histórica: eso lo sigue haciendo el flujo nocturno.

Uso:
  python resultados_hoy.py
  python resultados_hoy.py 2026-10-25 --archivo pagina.html     (prueba con página guardada)
"""
import json, os, sys, datetime as dt
import recolectar_enloteria as E

RD = dt.timezone(dt.timedelta(hours=-4))


def main(a):
    ahora = dt.datetime.now(RD)
    fecha = a[0] if a and not a[0].startswith("--") else ahora.date().isoformat()
    try:
        html = open(a[a.index("--archivo") + 1], encoding="utf-8", errors="replace").read() if "--archivo" in a else E.descargar(fecha)
        filas = [f for f in E.parsear(html) if f[0] == fecha]
    except Exception as e:
        print("AVISO:", e); return 1
    r = {s: [p, sg, t] for (_, s, p, sg, t) in filas}
    if not r:
        print("Aún no hay resultados de", fecha); return 0
    ant = json.load(open("hoy.json", encoding="utf-8")) if os.path.exists("hoy.json") else {}
    if ant.get("fecha") == fecha and ant.get("r") == r:
        print("Sin cambios"); return 0
    json.dump({"fecha": fecha, "actualizado": ahora.strftime("%H:%M"), "fuente": "EnLotería", "r": r},
              open("hoy.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"hoy.json actualizado: {len(r)} sorteos de {fecha}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
