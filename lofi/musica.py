"""Compositor y sintetizador de pistas lofi originales.

Todo el sonido se crea aquí con matemáticas (síntesis FM, Karplus-Strong,
ruido filtrado). No se usan samples, loops ni música de terceros, así que
cada pista es material propio del canal.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

SR = 44100
NOMBRES_NOTAS = ["Do", "Do#", "Re", "Mib", "Mi", "Fa", "Fa#", "Sol", "Lab", "La", "Sib", "Si"]

ACORDES = {
    "maj7": [0, 4, 7, 11],
    "maj9": [0, 4, 7, 11, 14],
    "m7": [0, 3, 7, 10],
    "m9": [0, 3, 7, 10, 14],
    "m11": [0, 3, 7, 10, 14, 17],
    "7": [0, 4, 7, 10],
    "9": [0, 4, 7, 10, 14],
    "13": [0, 4, 10, 14, 21],
    "m7b5": [0, 3, 6, 10],
    "6/9": [0, 4, 7, 9, 14],
}

# (modo, [(grado en semitonos desde la tónica, tipo de acorde), ...])
PROGRESIONES = [
    ("mayor", [(2, "m9"), (7, "9"), (0, "maj9"), (9, "m7")]),       # ii V I vi
    ("mayor", [(0, "maj7"), (9, "m9"), (2, "m7"), (7, "13")]),      # I vi ii V
    ("mayor", [(5, "maj9"), (4, "m7"), (2, "m9"), (0, "maj7")]),    # IV iii ii I
    ("mayor", [(9, "m9"), (2, "m7"), (7, "9"), (0, "maj9")]),       # vi ii V I
    ("mayor", [(0, "maj9"), (5, "maj7"), (4, "m7"), (9, "m11")]),   # I IV iii vi
    ("mayor", [(5, "maj7"), (7, "9"), (4, "m7"), (9, "m9")]),       # IV V iii vi
    ("mayor", [(0, "6/9"), (4, "m7"), (5, "maj9"), (7, "13")]),     # I iii IV V
    ("menor", [(0, "m9"), (5, "m7"), (10, "9"), (3, "maj7")]),      # i iv VII III
    ("menor", [(0, "m9"), (8, "maj7"), (3, "maj9"), (10, "9")]),    # i VI III VII
    ("menor", [(2, "m7b5"), (7, "7"), (0, "m9"), (0, "m11")]),      # ii° V i i
    ("menor", [(0, "m11"), (3, "maj7"), (8, "maj9"), (7, "m7")]),   # i III VI v
]

PENTATONICA = {"mayor": [0, 2, 4, 7, 9], "menor": [0, 3, 5, 7, 10]}


# ---------------------------------------------------------------- utilidades
def _hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


def _t(n):
    return np.arange(n, dtype=np.float64) / SR


def _filtro(x, tipo, fc, orden=2):
    sos = signal.butter(orden, fc, btype=tipo, fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def _rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12)


def _rms_activo(x):
    """RMS solo de las partes que suenan (ignora silencios)."""
    m = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    activo = x[m > 1e-4]
    return _rms(activo) if len(activo) else 1e-12


def _db(d):
    return 10.0 ** (d / 20.0)


def _normalizar(x):
    p = np.max(np.abs(x))
    return x / p if p > 0 else x


def _poner(bus, y, seg, gan=1.0, pan=0.0):
    """Suma la señal mono `y` en el bus estéreo a partir de `seg` segundos."""
    i = int(round(seg * SR))
    if i < 0:
        y, i = y[-i:], 0
    if i >= len(bus):
        return
    y = y[: len(bus) - i]
    bus[i : i + len(y), 0] += y * gan * min(1.0, 1.0 - pan)
    bus[i : i + len(y), 1] += y * gan * min(1.0, 1.0 + pan)


def _swing(pos_tiempo, swing):
    """Desplaza las corcheas a contratiempo según el swing (0.5 = recto)."""
    b = np.floor(pos_tiempo)
    f = pos_tiempo - b
    f2 = f / 0.5 * swing if f < 0.5 else swing + (f - 0.5) / 0.5 * (1.0 - swing)
    return b + f2


# ----------------------------------------------------------- instrumentos
def piano_electrico(f, dur, vel):
    """Piano eléctrico tipo 'tine' con síntesis FM 1:1."""
    n = int((dur + 1.4) * SR)
    t = _t(n)
    indice = (0.7 + 1.5 * vel) * np.exp(-t * 4.0)
    y = np.sin(2 * np.pi * f * t + indice * np.sin(2 * np.pi * f * t))
    y += 0.10 * vel * np.sin(2 * np.pi * f * 7.0 * t) * np.exp(-t * 28.0)
    amp = np.exp(-t * (0.6 + f / 1300.0))
    ataque = np.minimum(1.0, t / 0.003)
    rel = np.where(t < dur, 1.0, np.exp(-(t - dur) * 6.0))
    return y * amp * ataque * rel * vel


def bajo(f, dur, vel):
    n = int((dur + 0.15) * SR)
    t = _t(n)
    fase = 2 * np.pi * f * t
    y = np.sin(fase) + 0.3 * np.sin(2 * fase) + 0.08 * np.sin(3 * fase)
    env = np.minimum(1.0, t / 0.008) * np.exp(-t * 1.1)
    env *= np.where(t < dur, 1.0, np.exp(-(t - dur) * 30.0))
    return np.tanh(1.6 * y * env) * vel


def vibrafono(f, dur, vel):
    n = int((dur + 1.6) * SR)
    t = _t(n)
    y = np.sin(2 * np.pi * f * t)
    y += 0.30 * np.sin(2 * np.pi * 3.0 * f * t) * np.exp(-t * 6.0)
    y += 0.12 * np.sin(2 * np.pi * 4.2 * f * t) * np.exp(-t * 10.0)
    amp = np.exp(-t * 1.7) * (1.0 + 0.25 * np.sin(2 * np.pi * 5.5 * t))
    rel = np.where(t < dur + 0.3, 1.0, np.exp(-(t - dur - 0.3) * 5.0))
    return y * amp * np.minimum(1.0, t / 0.002) * rel * vel


def flauta(f, dur, vel, rng):
    n = int((dur + 0.2) * SR)
    t = _t(n)
    vibrato = 1.0 + 0.004 * np.sin(2 * np.pi * 5.0 * t) * np.minimum(1.0, t / 0.35)
    fase = 2 * np.pi * np.cumsum(f * vibrato) / SR
    y = np.sin(fase) + 0.18 * np.sin(2 * fase) + 0.05 * np.sin(3 * fase)
    soplo = _filtro(rng.standard_normal(n), "band", [f * 1.5, min(f * 4.0, 12000)]) * 0.08
    env = np.minimum(1.0, t / 0.07) * np.where(t < dur, 1.0, np.exp(-(t - dur) * 25.0))
    return (y + soplo) * env * vel * (1.0 - 0.15 * np.minimum(1.0, t / max(dur, 0.1)))


def guitarra(f, dur, vel, rng):
    """Cuerda pulsada (Karplus-Strong), afinada con remuestreo final."""
    n = int((dur + 0.9) * SR)
    periodo_real = SR / f
    p = max(2, int(periodo_real))
    total = n + p + 1
    y = np.zeros(total)
    y[: p + 1] = _filtro(rng.uniform(-1, 1, p + 1), "low", min(4000, SR / 2 - 100))
    perdida = 0.996
    s = p + 1
    while s < total:
        e = min(s + p, total)
        y[s:e] = perdida * 0.5 * (y[s - p : e - p] + y[s - p - 1 : e - p - 1])
        s = e
    # el promedio de dos muestras añade medio periodo: se corrige la afinación
    r = (p + 0.5) / periodo_real
    idx = np.arange(n) * r
    idx = idx[idx < total - 1]
    out = np.interp(idx, np.arange(total), y)
    tt = _t(len(out))
    out *= np.where(tt < dur, 1.0, np.exp(-(tt - dur) * 8.0))
    return _normalizar(out) * vel


def colchon(fs, dur, vel, rng):
    """Pad suave de sierras ligeramente desafinadas."""
    n = int((dur + 1.0) * SR)
    t = _t(n)
    y = np.zeros(n)
    for f in fs:
        for d in (-0.004, 0.004):
            y += signal.sawtooth(2 * np.pi * f  * (1 + d) * t + rng.uniform(0, 6.28))
    env = np.minimum(1.0, t / 0.7) * np.where(t < dur, 1.0, np.exp(-(t - dur) * 3.5))
    return y * env * vel / max(1, len(fs))


def bombo(rng):
    n = int(0.5 * SR)
    t = _t(n)
    f = 44.0 + 85.0 * np.exp(-t * 30.0)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.0)
    golpe = _filtro(rng.standard_normal(n) * np.exp(-t * 350.0), "low", 2500) * 0.4
    return _normalizar(np.tanh(1.8 * (y + golpe)))


def caja(rng, tipo):
    if tipo == "aro":
        n = int(0.15 * SR)
        t = _t(n)
        y = 0.5 * np.sin(2 * np.pi * 1700 * t) * np.exp(-t * 90.0)
        y += 0.4 * np.sin(2 * np.pi * 420 * t) * np.exp(-t * 60.0)
        y += 0.6 * _filtro(rng.standard_normal(n), "band", [2000, 8000]) * np.exp(-t * 110.0)
    elif tipo == "palmas":
        n = int(0.3 * SR)
        t = _t(n)
        env = np.exp(-t * 22.0)
        for d in (0.0, 0.011, 0.022):
            env = np.maximum(env, np.where(t >= d, np.exp(-(t - d) * 180.0), 0.0))
        y = _filtro(rng.standard_normal(n), "band", [900, 3500]) * env
    else:
        n = int(0.35 * SR)
        t = _t(n)
        y = 0.7 * _filtro(rng.standard_normal(n), "band", [900, 6000]) * np.exp(-t * 16.0)
        y += 0.6 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30.0)
        y += 0.3 * np.sin(2 * np.pi * 330 * t) * np.exp(-t * 40.0)
    return _normalizar(y)


def platillo(rng, abierto=False):
    n = int((0.45 if abierto else 0.09) * SR)
    t = _t(n)
    y = _filtro(rng.standard_normal(n), "high", 7000) * np.exp(-t * (9.0 if abierto else 55.0))
    return _normalizar(y)


def _respuesta_reverb(rng, segundos, brillo):
    n = int(segundos * SR)
    t = _t(n)
    ir = rng.standard_normal((n, 2)) * np.exp(-t * (6.9 / segundos))[:, None]
    ir = _filtro(ir, "low", brillo)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.sqrt(np.sum(ir**2, axis=0))


# ------------------------------------------------------------- composición
PATRONES_BOMBO = [[0, 10], [0, 7, 10], [0, 3, 10], [0, 8, 10], [0, 3, 8, 11], [0, 6, 10]]
PATRONES_TECLADO = [
    [(0, 4.0)],
    [(0, 2.5), (2.5, 1.5)],
    [(0, 1.5), (1.5, 2.5)],
    [(0, 1.0), (1.5, 0.5), (2.5, 1.5)],
]
PATRONES_BAJO = [
    [(0, 2.5, "r"), (2.5, 1.0, "r"), (3.5, 0.5, "ap")],
    [(0, 1.5, "r"), (1.5, 1.0, "r"), (3.0, 1.0, "5")],
    [(0, 3.5, "r"), (3.5, 0.5, "ap")],
    [(0, 0.75, "r"), (0.75, 1.75, "r"), (2.5, 1.5, "8")],
]


def _voicing(raiz_pc, tipo, centro_previo):
    """Acorde sin fundamental (la toca el bajo), cerca del acorde anterior."""
    iv = ACORDES[tipo]
    notas = [48 + raiz_pc + i for i in iv[1:]]
    objetivo = 62.0 if centro_previo is None else 0.5 * centro_previo + 31.0
    k = round((objetivo - float(np.mean(notas))) / 12.0)
    return [n + 12 * k for n in notas]


def _frase(rng, densidad, idx):
    """Frase melódica de 2 compases en una rejilla de corcheas."""
    slots = sorted({s for s in range(14) if rng.random() < densidad} | {int(rng.integers(0, 3))})
    notas = []
    for k, s in enumerate(slots):
        sig = slots[k + 1] if k + 1 < len(slots) else 16
        idx = int(np.clip(idx + rng.choice([-2, -1, -1, 0, 1, 1, 2]), 1, 9))
        notas.append([s, min(sig - s, 4), idx])
    return notas


def componer(rng: np.random.Generator) -> tuple[np.ndarray, dict]:
    """Compone y sintetiza una pista completa. Devuelve (audio estéreo, info)."""
    modo, prog = PROGRESIONES[rng.integers(len(PROGRESIONES))]
    tonica = int(rng.integers(0, 12))
    bpm = float(rng.uniform(68, 88))
    swing = float(rng.uniform(0.55, 0.63))
    tiempo = 60.0 / bpm
    compas = 4 * tiempo
    tipo_caja = rng.choice(["caja", "aro", "palmas"], p=[0.5, 0.35, 0.15])
    melodia_inst = rng.choice(["vibrafono", "flauta", "guitarra", "piano"])
    con_colchon = rng.random() < 0.5
    pat_bombo = PATRONES_BOMBO[rng.integers(len(PATRONES_BOMBO))]
    pat_teclado = PATRONES_TECLADO[rng.integers(len(PATRONES_TECLADO))]
    pat_bajo = PATRONES_BAJO[rng.integers(len(PATRONES_BAJO))]
    corte = float(rng.uniform(3200, 6000))

    if rng.random() < 0.5:
        estructura = [("intro", 4), ("A", 8), ("B", 8), ("A", 8), ("outro", 4)]
    else:
        estructura = [("intro", 4), ("A", 8), ("B", 8), ("A", 4), ("B", 8), ("outro", 4)]
    total_compases = sum(c for _, c in estructura)
    dur = total_compases * compas + 4.0
    n = int(dur * SR)

    teclas = np.zeros((n, 2))
    bajo_bus = np.zeros((n, 2))
    bateria = np.zeros((n, 2))
    melo = np.zeros((n, 2))
    pad = np.zeros((n, 2))
    golpes_bombo = []

    s_bombo = bombo(rng)
    s_caja = caja(rng, tipo_caja)
    s_hat = platillo(rng)
    s_hat_ab = platillo(rng, abierto=True)

    # melodía: 4 frases (A A' B A) que se reutilizan en cada sección B
    escala = PENTATONICA[modo]
    base = 60 + tonica

    def nota_escala(i):
        return base + 12 * (i // 5) + escala[i % 5]

    densidad = float(rng.uniform(0.3, 0.5))
    fa = _frase(rng, densidad, 5)
    fa2 = [list(x) for x in fa]
    for x in fa2[-2:]:
        x[2] = int(np.clip(x[2] + rng.choice([-2, -1, 1, 2]), 1, 9))
    fb = _frase(rng, densidad, 7)
    frases = [fa, fa2, fb, fa]

    centro = None
    compas_i = 0
    for nombre, ncomp in estructura:
        for c in range(ncomp):
            t0 = compas_i * compas
            grado, tipo = prog[compas_i % len(prog)]
            raiz_pc = (tonica + grado) % 12
            sig_grado, _ = prog[(compas_i + 1) % len(prog)]
            ultimo = nombre == "outro" and c == ncomp - 1
            if ultimo:  # el final descansa en el acorde de tónica
                raiz_pc, tipo = tonica, ("maj9" if modo == "mayor" else "m9")
            voces = _voicing(raiz_pc, tipo, centro)
            centro = float(np.mean(voces))

            # teclado
            patron = [(0, 4.0)] if nombre in ("intro", "outro") else pat_teclado
            if ultimo:
                patron = [(0, 6.0)]
            for pos, d in patron:
                ts = t0 + _swing(pos, swing) * tiempo + rng.normal(0, 0.006)
                rasgueo = rng.uniform(0.006, 0.02)
                vel = rng.uniform(0.55, 0.8) if pos == 0 else rng.uniform(0.4, 0.6)
                for k, m in enumerate(voces):
                    y = piano_electrico(_hz(m), d * tiempo, vel * rng.uniform(0.85, 1.0))
                    _poner(teclas, y, ts + k * rasgueo, pan=rng.uniform(-0.2, 0.2))

            # colchón
            if con_colchon and nombre in ("A", "B"):
                y = colchon(_hz(voces), compas, 0.5, rng)
                _poner(pad, y, t0, pan=0.0)

            # bajo
            if nombre in ("A", "B"):
                raiz_bajo = 36 + raiz_pc
                if raiz_bajo > 44:
                    raiz_bajo -= 12
                sig_bajo = 36 + (tonica + sig_grado) % 12
                if sig_bajo > 44:
                    sig_bajo -= 12
                for pos, d, g in pat_bajo:
                    m = {
                        "r": raiz_bajo,
                        "5": raiz_bajo + 7,
                        "8": raiz_bajo + 12,
                        "ap": sig_bajo + rng.choice([-1, 1]),
                    }[g]
                    ts = t0 + _swing(pos, swing) * tiempo + rng.normal(0, 0.004)
                    _poner(bajo_bus, bajo(_hz(m), d * tiempo * 0.95, rng.uniform(0.75, 0.95)), ts)

            # batería
            if nombre in ("A", "B"):
                fin_seccion = c == ncomp - 1
                for paso in range(16):
                    if fin_seccion and paso >= 12 and rng.random() < 0.5:
                        break  # pequeño corte antes de la siguiente sección
                    pos = paso / 4.0
                    ts = t0 + _swing(pos, swing) * tiempo + rng.normal(0, 0.005)
                    if paso in pat_bombo:
                        _poner(bateria, s_bombo, ts, gan=rng.uniform(0.85, 1.0))
                        golpes_bombo.append(ts)
                    if paso in (4, 12):
                        _poner(bateria, s_caja, ts, gan=rng.uniform(0.8, 0.95))
                    elif paso in (7, 9, 15) and rng.random() < 0.18:
                        _poner(bateria, s_caja, ts, gan=rng.uniform(0.12, 0.22))
                    if paso % 2 == 0:
                        acento = 0.75 if paso % 4 == 0 else 0.5
                        if nombre == "B" and paso == 14 and rng.random() < 0.35:
                            _poner(bateria, s_hat_ab, ts, gan=0.35, pan=0.25)
                        else:
                            _poner(bateria, s_hat, ts, gan=acento * rng.uniform(0.7, 1.0), pan=0.25)
                    elif rng.random() < 0.12:
                        _poner(bateria, s_hat, ts, gan=rng.uniform(0.2, 0.35), pan=0.25)

            # melodía (en las secciones B)
            if nombre == "B":
                frase = frases[(c // 2) % 4]
                acorde_pcs = {(raiz_pc + i) % 12 for i in ACORDES[tipo]}
                for s, d, idx in frase:
                    if s // 8 != c % 2:
                        continue
                    pos = (s % 8) / 2.0
                    if s % 4 == 0:  # en tiempos fuertes, preferir notas del acorde
                        for delta in (0, 1, -1, 2, -2):
                            j = int(np.clip(idx + delta, 0, 10))
                            if nota_escala(j) % 12 in acorde_pcs:
                                idx = j
                                break
                    m = nota_escala(idx)
                    ts = t0 + _swing(pos, swing) * tiempo + rng.normal(0, 0.006)
                    dd = d * 0.5 * tiempo * 0.9
                    vel = rng.uniform(0.6, 0.85)
                    if melodia_inst == "vibrafono":
                        y = vibrafono(_hz(m), dd, vel)
                    elif melodia_inst == "flauta":
                        y = flauta(_hz(m), dd, vel, rng)
                    elif melodia_inst == "guitarra":
                        y = guitarra(_hz(m), dd, vel, rng)
                    else:
                        y = piano_electrico(_hz(m + 12), dd, vel)
                    _poner(melo, y, ts, pan=-0.15)
            compas_i += 1

    # ------------------------------------------------------------ mezcla
    t = _t(n)
    # trémolo estéreo del piano eléctrico
    trem = 0.12 * np.sin(2 * np.pi * 4.2 * t)
    teclas[:, 0] *= 1 + trem
    teclas[:, 1] *= 1 - trem
    teclas = _filtro(teclas, "low", 2800)
    bajo_bus = _filtro(bajo_bus, "low", 380)
    pad = _filtro(pad, "low", 1000)
    melo = _filtro(melo, "low", 4500)

    # batería sucia: reducción de muestreo + saturación + filtro
    bateria[1::2] = bateria[0::2][: len(bateria[1::2])]
    bateria = np.tanh(1.4 * _filtro(bateria, "low", 7500))

    # niveles relativos (dB RMS sobre las partes que suenan)
    def nivel(x, db):
        return x * (_db(db) / _rms_activo(x)) if np.any(x) else x

    teclas = nivel(teclas, -19)
    bajo_bus = nivel(bajo_bus, -20)
    bateria = nivel(bateria, -18)
    melo = nivel(melo, -23)
    pad = nivel(pad, -30)

    # reverb para piano y melodía
    ir = _respuesta_reverb(rng, float(rng.uniform(1.6, 2.6)), 3500)
    envio = (teclas.sum(axis=1) * 0.5 + melo.sum(axis=1) * 0.7)
    humedo = np.stack([signal.oaconvolve(envio, ir[:, k])[:n] for k in range(2)], axis=1)

    # compresión lateral (el bombo "empuja" a los demás)
    duck = np.zeros(n)
    largo = int(0.25 * SR)
    curva = 0.28 * np.exp(-_t(largo) / 0.12)
    for tb in golpes_bombo:
        i = int(tb * SR)
        if 0 <= i < n:
            seg = curva[: n - i]
            duck[i : i + len(seg)] = np.maximum(duck[i : i + len(seg)], seg)
    gan = (1.0 - duck)[:, None]

    musica = (teclas + pad + melo + 0.35 * humedo) * gan + bajo_bus * gan

    # barrido de filtro: la intro y el final suenan "detrás de una puerta"
    oscuro = _filtro(musica, "low", 900)
    w = np.ones(n)
    fin_intro = 4 * compas
    ini_outro = (total_compases - 4) * compas
    w[t < fin_intro] = np.clip(t[t < fin_intro] / fin_intro, 0, 1) ** 2
    m_out = t >= ini_outro
    w[m_out] = np.clip(1 - (t[m_out] - ini_outro) / (4 * compas), 0, 1) ** 1.5
    musica = musica * w[:, None] + oscuro * (1 - w)[:, None]

    mezcla = musica + bateria
    mezcla = _filtro(mezcla, "low", corte)
    mezcla = _filtro(mezcla, "high", 35)

    # cinta: wow & flutter
    retardo = 40.0 * (1 + np.sin(2 * np.pi * 0.45 * t + rng.uniform(0, 6.28)))
    retardo += 0.6 * np.sin(2 * np.pi * 6.0 * t)
    idx = np.clip(np.arange(n) - retardo, 0, n - 1)
    base_idx = np.arange(n)
    mezcla = np.stack([np.interp(idx, base_idx, mezcla[:, k]) for k in range(2)], axis=1)

    # nivel final y suavizado de picos
    mezcla *= _db(-16) / _rms(mezcla[int(fin_intro * SR) : int(ini_outro * SR)])
    mezcla = np.tanh(mezcla / 0.9) * 0.9
    fade_in = int(0.03 * SR)
    fade_out = int(2.5 * SR)
    mezcla[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    mezcla[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None] ** 2

    info = {
        "tonalidad": f"{NOMBRES_NOTAS[tonica]} {modo}",
        "bpm": round(bpm),
        "duracion": round(n / SR, 1),
        "melodia": str(melodia_inst),
    }
    return mezcla.astype(np.float32), info


# -------------------------------------------------------------- ambiente
class Ambiente:
    """Ruido de vinilo y lluvia continuos para todo el video."""

    def __init__(self, rng: np.random.Generator, lluvia: bool):
        self.rng = rng
        self.lluvia = lluvia
        self.sos_siseo = signal.butter(2, [600, 5000], "band", fs=SR, output="sos")
        self.sos_click = signal.butter(2, [800, 6000], "band", fs=SR, output="sos")
        self.sos_lluvia = signal.butter(2, [350, 7000], "band", fs=SR, output="sos")
        z = lambda sos: np.zeros((sos.shape[0], 2, 2))
        self.z_siseo, self.z_click, self.z_lluvia = z(self.sos_siseo), z(self.sos_click), z(self.sos_lluvia)
        self.muestras = 0

    def generar(self, n: int) -> np.ndarray:
        rng = self.rng
        siseo, self.z_siseo = signal.sosfilt(self.sos_siseo, rng.standard_normal((n, 2)), axis=0, zi=self.z_siseo)
        clicks = np.zeros((n, 2))
        k = rng.poisson(n / SR * 7)
        pos = rng.integers(0, n, k)
        clicks[pos, rng.integers(0, 2, k)] = rng.exponential(0.5, k) * rng.choice([-1, 1], k)
        clicks, self.z_click = signal.sosfilt(self.sos_click, clicks, axis=0, zi=self.z_click)
        out = siseo * _db(-52) + clicks * 0.25
        if self.lluvia:
            ll, self.z_lluvia = signal.sosfilt(self.sos_lluvia, rng.standard_normal((n, 2)), axis=0, zi=self.z_lluvia)
            t = (self.muestras + np.arange(n)) / SR
            mod = 1.0 + 0.25 * np.sin(2 * np.pi * 0.07 * t) + 0.1 * np.sin(2 * np.pi * 0.23 * t)
            out += ll * _db(-33) * mod[:, None]
        self.muestras += n
        return out.astype(np.float32)
