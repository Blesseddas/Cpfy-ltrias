#!/usr/bin/env python3
"""
Agente de análisis de quinielas dominicanas (Capafy AI)

Uso:
    python agente_loteria.py quinielas.csv                  # todos los sorteos
    python agente_loteria.py quinielas.csv "Real Día"       # un sorteo
    python agente_loteria.py quinielas.csv --backtest       # prueba histórica

Qué hace:
  1. Carga el historial (Fecha, Sorteo, Primero, Segundo, Tercero).
  2. Prueba chi-cuadrado: ¿hay números que salgan más de lo normal?
  3. Puntúa cada número 00-99 con frecuencia + atraso (lo que hace
     cualquier "predictor") y devuelve el top por sorteo.
  4. Backtest: mide si ese ranking acierta más que el azar.

AVISO: es un juego de azar. Cada número tiene 1% de salir por posición
(3% de aparecer entre los tres premios). Esto es una herramienta de
entretenimiento y análisis, no una predicción.
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats

NUMS = [f"{i:02d}" for i in range(100)]
MIN_HIST = 120


def cargar(ruta):
    q = pd.read_csv(ruta, dtype=str, encoding="utf-8-sig")
    q = q.dropna(subset=["Primero", "Segundo", "Tercero"])
    return q.sort_values("Fecha")


def puntuar(hist):
    """hist: array (n_sorteos, 3). Devuelve DataFrame con puntaje por número."""
    n = len(hist)
    cnt = pd.Series(hist.ravel()).value_counts().reindex(NUMS, fill_value=0)
    ultimo = {k: -1 for k in NUMS}
    for i, fila in enumerate(hist):
        for x in fila:
            ultimo[x] = i
    atraso = pd.Series({k: n - 1 - v for k, v in ultimo.items()})
    z_frec = (cnt - cnt.mean()) / cnt.std()
    z_atr = (atraso - atraso.mean()) / atraso.std()
    score = 0.6 * z_frec + 0.4 * z_atr
    df = pd.DataFrame({"apariciones": cnt, "sorteos_sin_salir": atraso, "puntaje": score})
    return df.sort_values("puntaje", ascending=False)


def prueba_uniformidad(q):
    p = {}
    for col in ["Primero", "Segundo", "Tercero"]:
        c = q[col].value_counts().reindex(NUMS, fill_value=0)
        p[col] = stats.chisquare(c.values).pvalue
    return p


def sugerencias(q, sorteo=None, k=5):
    out = {}
    sorteos = [sorteo] if sorteo else sorted(q.Sorteo.unique())
    for s in sorteos:
        g = q[q.Sorteo == s]
        if len(g) < MIN_HIST:
            out[s] = None  # historial insuficiente
            continue
        hist = g[["Primero", "Segundo", "Tercero"]].values
        out[s] = puntuar(hist).head(k)
    return out


def backtest(q, k=5, semilla=1):
    rng = np.random.default_rng(semilla)
    r = {"modelo": [], "azar": []}
    for s, g in q.groupby("Sorteo"):
        if len(g) < MIN_HIST + 20:
            continue
        arr = g[["Primero", "Segundo", "Tercero"]].values
        for t in range(MIN_HIST, len(arr)):
            real = set(arr[t])
            top = set(puntuar(arr[:t]).head(k).index)
            rnd = set(NUMS[i] for i in rng.choice(100, k, replace=False))
            r["modelo"].append(len(top & real))
            r["azar"].append(len(rnd & real))
    esperado = k * 3 / 100
    return {m: np.mean(v) for m, v in r.items()}, esperado, len(r["modelo"])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    q = cargar(sys.argv[1])
    if "--backtest" in sys.argv:
        res, esp, n = backtest(q)
        print(f"Backtest sobre {n} sorteos (5 números por sorteo)")
        print(f"  Esperado por pura probabilidad: {esp:.3f} aciertos")
        for m, v in res.items():
            print(f"  {m:8s}: {v:.3f} aciertos por sorteo")
        sys.exit(0)

    sorteo = next((a for a in sys.argv[2:] if not a.startswith("--")), None)
    print("Prueba de uniformidad (p > 0.05 = sin evidencia de números 'calientes'):")
    for pos, p in prueba_uniformidad(q).items():
        print(f"  {pos}: p = {p:.3f}")
    print()
    for s, df in sugerencias(q, sorteo).items():
        if df is None:
            print(f"{s}: historial insuficiente (< {MIN_HIST} sorteos)")
            continue
        print(f"{s}: " + "  ".join(df.index) + "   (ranking por frecuencia + atraso)")
    print("\nRecordatorio: cada número tiene la misma probabilidad (1% por posición).")
