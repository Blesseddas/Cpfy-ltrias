#!/usr/bin/env python3
"""
Segunda fuente: datos abiertos de Lotería de la 1 (CSV, licencia CC BY 4.0).
Atribución: https://loteriadela1.com/datos-abiertos

Configuración ÚNICA (una sola vez): copia el enlace del botón de descarga del CSV
en https://loteriadela1.com/datos-abiertos y guárdalo en GitHub como
variable de repositorio  L1_CSV_URL  (Settings > Secrets and variables > Actions > Variables).

Uso:
  L1_CSV_URL=https://... python recolectar_loteriadela1.py        # últimos 7 días
  python recolectar_loteriadela1.py --archivo datos.csv [--dias N] # archivo local
Escribe nuevos/AAAA-MM-DD_loteriadela1.csv. No escribe nada si falla.
"""
import sys, os, io, csv, datetime as dt, urllib.request
import pandas as pd

MAPA = {  # (loteria_key, juego_nombre, sesion) -> sorteo canónico
    ("la-primera", "Quiniela", "dia"): "La Primera Día", ("la-primera", "Quiniela", "noche"): "La Primera Noche",
    ("la-suerte", "Quiniela", "dia"): "La Suerte Día", ("la-suerte", "Quiniela", "noche"): "La Suerte Tarde",  # provisional
    ("leidsa", "Quiniela", "noche"): "Leidsa Quiniela", ("leidsa", "Quiniela", "dia"): "Leidsa Quiniela",
    ("lotedom", "Quiniela", "dia"): "LoteDom Día",
    ("loteka", "Quiniela", "dia"): "Loteka Día", ("loteka", "Quiniela", "noche"): "Loteka Noche",
    ("nacional", "Gana Más", "dia"): "Nacional Gana Más", ("nacional", "Quiniela", "noche"): "Nacional Noche",
    ("real", "Quiniela", "dia"): "Real Día", ("real", "Quiniela", "noche"): "Real Noche",
}


def procesar(df, dias=7):
    df = df.dropna(subset=["posicion_1", "posicion_2", "posicion_3"]).copy()
    df["sorteo"] = [MAPA.get(k) for k in zip(df.loteria_key, df.juego_nombre, df.sesion)]
    df = df[df.sorteo.notna()]
    desde = (dt.date.today() - dt.timedelta(days=dias)).isoformat()
    df = df[df.fecha >= desde]
    # Leidsa: los domingos el sorteo es el de las 3:55 pm ('dia'); el 'noche' del domingo es ambiguo
    dom = pd.to_datetime(df.fecha).dt.dayofweek == 6
    quitar = (df.loteria_key == "leidsa") & ((dom & (df.sesion == "noche")) | (~dom & (df.sesion == "dia")))
    df = df[~quitar]
    for c in ["posicion_1", "posicion_2", "posicion_3"]:
        df = df[df[c].str.fullmatch(r"\d{2}")]
    return df


def guardar(df):
    os.makedirs("nuevos", exist_ok=True)
    for fecha, g in df.groupby("fecha"):
        ruta = f"nuevos/{fecha}_loteriadela1.csv"
        with open(ruta, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["Fecha", "Sorteo", "Primero", "Segundo", "Tercero", "Fuente"])
            for r in g.drop_duplicates(["sorteo"]).itertuples():
                w.writerow([fecha, r.sorteo, r.posicion_1, r.posicion_2, r.posicion_3, "Lotería de la 1"])
    print(f"{df.fecha.nunique()} fechas, {len(df)} sorteos")


if __name__ == "__main__":
    a = sys.argv[1:]
    dias = int(a[a.index("--dias") + 1]) if "--dias" in a else 7
    try:
        if "--archivo" in a:
            raw = open(a[a.index("--archivo") + 1], encoding="utf-8").read()
        else:
            url = os.environ["L1_CSV_URL"]
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CapafyBot)"})
            raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
        guardar(procesar(pd.read_csv(io.StringIO(raw), dtype=str), dias))
    except KeyError:
        print("Falta la variable L1_CSV_URL (ver instrucciones al inicio del archivo)."); sys.exit(1)
    except Exception as e:
        print("ERROR:", e); sys.exit(1)
