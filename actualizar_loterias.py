#!/usr/bin/env python3
"""
Seguimiento diario de quinielas dominicanas (Capafy AI)

Flujo diario (lo ejecuta el programador de tareas, ver README.md):
  1. Lee los resultados nuevos de la carpeta  nuevos/*.csv
       columnas: Fecha,Sorteo,Primero,Segundo,Tercero,Fuente
  2. Valida (dos dígitos, sorteo conocido, fecha válida).
  3. Une con datos/quinielas.csv sin duplicar. Si dos fuentes difieren,
     el sorteo queda como 'Discrepancia' (sin números) y se anota en
     datos/discrepancias.csv para revisión. Nunca se inventa un resultado.
  4. Recalcula estadísticas y regenera  index.html  (la app).

Uso:
  python actualizar_loterias.py            # importa + reconstruye
  python actualizar_loterias.py --solo-app # solo reconstruye la app
"""
import glob, json, re, sys, os, datetime as dt
import pandas as pd
from scipy import stats
from itertools import combinations
import agente_loteria as A

BASE, DISC = "datos/quinielas.csv", "datos/discrepancias.csv"
SUG, SEM = "datos/sugerencias.csv", "datos/semana.json"
SCOLS = ["Fecha", "Sorteo", "Numeros", "Origen", "Generado"]
SORTEOS = {"La Primera Día", "La Primera Noche", "La Suerte Día", "La Suerte Tarde",
           "Leidsa Quiniela", "LoteDom Día", "LoteDom Noche", "Loteka Día", "Loteka Noche",
           "Nacional Gana Más", "Nacional Noche", "Real Día", "Real Noche"}
COLS = ["Fecha", "Sorteo", "Primero", "Segundo", "Tercero", "Estado", "Fuentes", "Nombres de fuentes"]


def leer(ruta):
    return pd.read_csv(ruta, dtype=str, encoding="utf-8-sig").fillna("")


def validar(n):
    ok = re.fullmatch(r"\d{2}", n.Primero) and re.fullmatch(r"\d{2}", n.Segundo) and re.fullmatch(r"\d{2}", n.Tercero)
    try:
        f = dt.date.fromisoformat(n.Fecha)
        ok = ok and f <= dt.date.today()
    except ValueError:
        ok = False
    return bool(ok) and n.Sorteo in SORTEOS


def importar():
    archivos = sorted(glob.glob("nuevos/*.csv"))
    if not archivos:
        print("Sin archivos nuevos."); return 0
    base, disc = leer(BASE), leer(DISC)
    nuevos = pd.concat([leer(a) for a in archivos], ignore_index=True)
    malos = nuevos[~nuevos.apply(validar, axis=1)]
    if len(malos):
        print(f"{len(malos)} filas inválidas descartadas:\n", malos.to_string())
    nuevos = nuevos.drop(index=malos.index)
    cambios = 0
    for (f, s), g in nuevos.groupby(["Fecha", "Sorteo"]):
        previo = base[(base.Fecha == f) & (base.Sorteo == s)]
        if len(previo) and previo.iloc[0].Estado.startswith("Resuelta"):
            continue  # resuelta con verificación externa: protegida, ninguna fuente posterior la pisa
        obs = [(r.Primero, r.Segundo, r.Tercero, r.Fuente) for r in g.itertuples()]
        if len(previo) and previo.iloc[0].Primero:
            p = previo.iloc[0]
            for nf in (p["Nombres de fuentes"] or "Base").split(", "):
                obs.append((p.Primero, p.Segundo, p.Tercero, nf))
        tripletas = {o[:3] for o in obs}
        fuentes = sorted({o[3] for o in obs})
        if len(previo) and previo.iloc[0].Estado == "Discrepancia":
            # discrepancia abierta: solo se cierra si 2+ fuentes distintas coinciden; si no, se deja como está
            if not (len(tripletas) == 1 and len(fuentes) >= 2):
                continue
        if len(tripletas) == 1:
            p, sg, t = next(iter(tripletas))
            estado = "Coincide entre fuentes" if len(fuentes) > 1 else "Una fuente"
        else:
            p = sg = t = ""; estado = "Discrepancia"
            for o in obs:
                disc.loc[len(disc)] = [f, s, o[0], o[1], o[2], "Pendiente", f"Fuente {o[3]}: sin resolver"]
        fila = [f, s, p, sg, t, estado, str(len(fuentes)), ", ".join(fuentes)]
        base = base[~((base.Fecha == f) & (base.Sorteo == s))].reset_index(drop=True)
        base.loc[len(base)] = fila
        cambios += 1
    base.sort_values(["Fecha", "Sorteo"])[COLS].to_csv(BASE, index=False, encoding="utf-8-sig")
    disc.to_csv(DISC, index=False, encoding="utf-8-sig")
    os.makedirs("nuevos/procesados", exist_ok=True)
    for a in archivos:
        os.replace(a, "nuevos/procesados/" + dt.date.today().isoformat() + "_" + os.path.basename(a))
    print(f"{cambios} sorteos actualizados.")
    return cambios


def seguimiento(q, sorteos):
    """Guarda los números sugeridos ANTES de cada sorteo y los compara con lo que salió.
    Origen 'Registrado' = guardado antes del sorteo. 'Retrospectivo' = lo que el método habría dado
    usando solo datos anteriores a ese día (se reconstruye una sola vez, los últimos 30 días)."""
    ult = dt.date.fromisoformat(q.Fecha.max()); manana = ult + dt.timedelta(days=1)
    reg = leer(SUG) if os.path.exists(SUG) else pd.DataFrame(columns=SCOLS)
    nuevas = []
    if reg.empty:
        for s_ in sorteos:
            g = q[q.Sorteo == s_]
            for f in sorted(g.Fecha.unique())[-30:]:
                h = g[g.Fecha < f][["Primero", "Segundo", "Tercero"]].values
                if len(h) >= A.MIN_HIST:
                    nuevas.append([f, s_, " ".join(A.puntuar(h).head(5).index), "Retrospectivo", ult.isoformat()])
    for s_ in sorteos:
        if not ((reg.Fecha == manana.isoformat()) & (reg.Sorteo == s_)).any():
            h = q[q.Sorteo == s_][["Primero", "Segundo", "Tercero"]].values
            nuevas.append([manana.isoformat(), s_, " ".join(A.puntuar(h).head(5).index), "Registrado", ult.isoformat()])
    if nuevas:
        reg = pd.concat([reg, pd.DataFrame(nuevas, columns=SCOLS)], ignore_index=True)
        reg.sort_values(["Fecha", "Sorteo"]).to_csv(SUG, index=False, encoding="utf-8-sig")
    res = {(r.Fecha, r.Sorteo): (r.Primero, r.Segundo, r.Tercero) for r in q.itertuples()}
    filas, tot = [], {}
    for r in reg.itertuples():
        if (r.Fecha, r.Sorteo) not in res:
            continue
        nums, rr = r.Numeros.split(), list(res[(r.Fecha, r.Sorteo)])
        h = [int(x in nums) for x in rr]
        filas.append([r.Fecha, r.Sorteo, nums, rr, h, r.Origen])
        t = tot.setdefault(r.Origen, {"n": 0, "h": [0, 0, 0]})
        t["n"] += 1
        t["h"] = [a + b for a, b in zip(t["h"], h)]
    fechas = sorted({f[0] for f in filas})[-7:]
    aci = {"dias": [f for f in filas if f[0] in fechas], "tot": tot}
    d0 = (ult - dt.timedelta(days=8)).isoformat()
    sug, rec = {}, {}
    for r in reg[reg.Fecha >= d0].itertuples():
        sug.setdefault(r.Fecha, {})[r.Sorteo] = r.Numeros.split()
    for (f, s_), v in res.items():
        if f >= d0 and s_ in sorteos:
            rec.setdefault(f, {})[s_] = list(v)
    aci.update(sug=sug, rec=rec)
    # Tres números fijos para toda la semana (se renuevan cada lunes)
    lunes = manana - dt.timedelta(days=manana.weekday())
    sem = json.load(open(SEM, encoding="utf-8")) if os.path.exists(SEM) else {}
    if not sem or sem["inicio"] < lunes.isoformat():
        pt = pd.concat([A.puntuar(q[q.Sorteo == s_][["Primero", "Segundo", "Tercero"]].values)["puntaje"] for s_ in sorteos], axis=1)
        sem = {"inicio": lunes.isoformat(), "fijado": ult.isoformat(),
               "numeros": sorted(pt.mean(axis=1).sort_values(ascending=False).head(3).index)}
        json.dump(sem, open(SEM, "w", encoding="utf-8"))
    fin = (dt.date.fromisoformat(sem["inicio"]) + dt.timedelta(days=6)).isoformat()
    w = q[(q.Fecha > sem["fijado"]) & (q.Fecha <= fin) & (q.Sorteo.isin(sorteos))]
    apar = [[r.Fecha, r.Sorteo, j + 1, n] for r in w.itertuples()
            for j, n in enumerate((r.Primero, r.Segundo, r.Tercero)) if n in sem["numeros"]]
    return aci, dict(sem, fin=fin, n=len(w), apar=apar)


def reconstruir():
    q = leer(BASE)
    q = q[(q.Primero != "") & (q.Tercero != "")].sort_values("Fecha")
    res, esp, n = A.backtest(q)
    out = {}
    for s, g in q.groupby("Sorteo"):
        if len(g) < A.MIN_HIST:
            continue
        h = g[["Primero", "Segundo", "Tercero"]].values
        sc = A.puntuar(h)
        c = pd.Series(h.ravel()).value_counts().reindex(A.NUMS, fill_value=0)
        out[s] = dict(n=len(g), c=[int(x) for x in c],
                      g=[int(sc.loc[k, "sorteos_sin_salir"]) for k in A.NUMS],
                      top=list(sc.head(5).index), p=round(stats.chisquare(c.values).pvalue, 3))
    aci, sem = seguimiento(q, list(out))
    q["dow"] = pd.to_datetime(q.Fecha).dt.dayofweek
    allc = pd.concat([q[c] for c in ["Primero", "Segundo", "Tercero"]]).value_counts().reindex(A.NUMS, fill_value=0)
    pc = pd.Series([tuple(sorted(c)) for r in q[["Primero", "Segundo", "Tercero"]].values
                    for c in combinations(r, 2)]).value_counts()
    todas = [tuple(sorted(c)) for c in combinations(A.NUMS, 2)]
    dp = [round(stats.chisquare(pd.concat([q[q.dow == d][c] for c in ["Primero", "Segundo", "Tercero"]])
          .value_counts().reindex(A.NUMS, fill_value=0).values).pvalue, 2) for d in range(7)]
    D = dict(s=out, mod=round(float(res["modelo"]), 3), azar=round(float(res["azar"]), 3), esp=esp, nb=n,
             pall=round(stats.chisquare(allc.values).pvalue, 3),
             pair_p=round(stats.chisquare(pc.reindex(todas, fill_value=0).values).pvalue, 3),
             pair_top=[(a + "-" + b, int(v)) for (a, b), v in pc.head(3).items()],
             pair_exp=round(len(q) * 3 / (100 * 99 / 2), 1), dow=dp, total=len(q),
             actualizado=q.Fecha.max(), aci=aci, sem=sem)
    html = open("plantilla_app.html", encoding="utf-8").read().replace("__DATA__", json.dumps(D, separators=(",", ":")))
    html = html.replace("(26/10/2025 – 25/10/2026)", "(hasta " + D["actualizado"] + ")")
    open("index.html", "w", encoding="utf-8").write(html)
    print(f"App regenerada: {len(q)} sorteos hasta {D['actualizado']}.")


if __name__ == "__main__":
    if "--solo-app" not in sys.argv:
        importar()
    reconstruir()
    # Autovigilancia: si los datos llevan más de 2 días sin avanzar, falla a propósito
    # para que GitHub envíe un correo de aviso al dueño del repositorio.
    ult = dt.date.fromisoformat(leer(BASE).query("Primero != ''").Fecha.max())
    atraso = (dt.date.today() - ult).days
    if atraso > 2:
        print(f"ALERTA: los datos llevan {atraso} días sin actualizarse (último: {ult}).")
        sys.exit(2)
