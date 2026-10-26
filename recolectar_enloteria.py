#!/usr/bin/env python3
"""
Recolector de EnLotería (Capafy AI)

Lee los datos estructurados (JSON-LD, tipo Event) de la página
https://enloteria.com/resultados-loterias-AAAA-MM-DD y escribe
nuevos/AAAA-MM-DD_enloteria.csv para actualizar_loterias.py.

Uso:
  python recolectar_enloteria.py                 # ayer y hoy (hora RD)
  python recolectar_enloteria.py 2026-10-25      # una fecha
  python recolectar_enloteria.py --archivo pagina.html   # página guardada

Si el sitio bloquea la descarga o cambia el formato, NO escribe nada y
termina con error (código 1) para que se note; nunca rellena con supuestos.
"""
import sys, re, json, csv, os, datetime as dt, urllib.request, urllib.error

MAPA = {  # nombre en EnLotería -> sorteo canónico
    "La Primera": "La Primera Día", "La Primera Noche": "La Primera Noche",
    "La Suerte": "La Suerte Día", "La Suerte 6PM": "La Suerte Tarde",
    "Real": "Real Día", "Real Noche": "Real Noche",
    "Loteka Tarde": "Loteka Día", "Loteka": "Loteka Noche",
    "Leidsa": "Leidsa Quiniela",
    "LoteDom": "LoteDom Día", "LoteDom Noche": "LoteDom Noche",
    "Nacional Gana Más": "Nacional Gana Más", "Nacional Noche": "Nacional Noche",
}
URL = "https://enloteria.com/resultados-loterias-{}"


def parsear(html):
    """Devuelve lista de (fecha, sorteo, p, s, t). Ignora juegos no mapeados."""
    filas = []
    for bloque in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            datos = json.loads(bloque)
        except json.JSONDecodeError:
            continue
        pila = [datos]
        while pila:
            x = pila.pop()
            if isinstance(x, list):
                pila.extend(x)
            elif isinstance(x, dict):
                pila.extend(v for v in x.values() if isinstance(v, (list, dict)))
                if x.get("@type") == "Event" and x.get("name") in MAPA:
                    pr = {p.get("name"): str(p.get("value")) for p in x.get("additionalProperty", [])}
                    t = (pr.get("Primer Premio"), pr.get("Segundo Premio"), pr.get("Tercer Premio"))
                    fecha = pr.get("Fecha del Sorteo") or x.get("startDate", "")[:10]
                    if all(t) and all(re.fullmatch(r"\d{2}", v) for v in t):
                        filas.append((fecha, MAPA[x["name"]], *t))
    return filas


def descargar(fecha):
    req = urllib.request.Request(URL.format(fecha), headers={"User-Agent": "Mozilla/5.0 (CapafyBot; seguimiento academico)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def guardar(filas, fecha):
    filas = [f for f in filas if f[0] == fecha]  # solo la fecha pedida
    if not filas:
        raise RuntimeError(f"Sin resultados para {fecha}")
    os.makedirs("nuevos", exist_ok=True)
    ruta = f"nuevos/{fecha}_enloteria.csv"
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["Fecha", "Sorteo", "Primero", "Segundo", "Tercero", "Fuente"])
        for f in sorted(set(filas)):
            w.writerow([*f, "EnLotería"])
    print(f"{ruta}: {len(set(filas))} sorteos")


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if a and a[0] == "--archivo":
            html = open(a[1], encoding="utf-8", errors="replace").read()
            filas = parsear(html)
            for fecha in sorted({f[0] for f in filas}):
                guardar(filas, fecha)
        else:
            hoy = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).date()
            fechas = a or [(hoy - dt.timedelta(days=1)).isoformat(), hoy.isoformat()]
            ok = 0
            for fecha in fechas:
                try:
                    guardar(parsear(descargar(fecha)), fecha); ok += 1
                except (urllib.error.URLError, RuntimeError, OSError) as e:
                    print(f"AVISO {fecha}: {e}")
            if not ok:
                sys.exit(1)
    except Exception as e:
        print("ERROR:", e); sys.exit(1)
