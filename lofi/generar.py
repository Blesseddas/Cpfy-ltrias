"""Genera un video lofi completo: música original, animación, miniatura y textos.

Uso:
    python lofi/generar.py --minutos 60 --salida lofi/salida
    python lofi/generar.py --minutos 3 --rapido        # prueba corta a 720p

Deja en la carpeta de salida:
    video.mp4       el video final (animación en bucle + música)
    miniatura.jpg   la miniatura 1280x720
    meta.json       título, descripción con capítulos y etiquetas para YouTube
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import subprocess
import time
import wave
from pathlib import Path

import numpy as np

import musica
import visual

SR = musica.SR

NOMBRES = [
    "café a medianoche", "ventana empañada", "luces de neón", "tren de las once", "cuaderno abierto",
    "azotea", "té de jazmín", "domingo lento", "farolas", "lluvia de abril", "radio vieja", "postales",
    "bufanda roja", "último tranvía", "noche de estudio", "páginas sueltas", "sueño ligero", "polaroid",
    "nubes de algodón", "luna de papel", "calle vacía", "humo de té", "eco", "marea baja", "cassette",
    "vinilo gastado", "despertar", "hojas secas", "invierno suave", "plantas en la ventana",
    "lámpara de escritorio", "memorias", "otoño", "paraguas", "bicicleta", "parque de noche",
    "estrellas fugaces", "cielo violeta", "brisa", "atardecer naranja", "lápiz y papel", "siesta",
    "madrugada", "rincón tranquilo", "gato dormido", "carta sin enviar", "pasos lentos", "faro", "olas",
    "musgo", "neblina", "cielo de agosto", "fin de semana", "suéter grande", "leche tibia",
    "galletas de avena", "mapa viejo", "constelaciones", "silencio", "luciérnagas", "andén",
    "reloj de pared", "nieve tranquila", "cabaña", "chimenea", "canela", "biblioteca",
    "escalera de incendios", "terraza", "mañana gris", "rayos de sol", "sombras largas", "reflejos",
    "cerezo", "orilla", "puerto", "cometa", "lunes otra vez", "taza tibia", "ciudad dormida",
]

TEMAS = {
    ("ciudad", "lluvia"): ["lluvia sobre la ciudad", "noche de lluvia en la ciudad", "calles mojadas a medianoche",
                           "ventanas con lluvia"],
    ("ciudad", "despejado"): ["luces de la ciudad", "la ciudad duerme", "azotea a medianoche",
                              "noche tranquila en la ciudad"],
    ("mar", "despejado"): ["noche junto al faro", "brisa del mar", "olas a medianoche", "el faro y la luna"],
    ("montana", "nieve"): ["nieve en la montaña", "cabaña en la nieve", "invierno en la cabaña", "noche de nieve"],
    ("montana", "despejado"): ["noche en la montaña", "estrellas sobre la cabaña", "cielo de montaña",
                               "refugio en el bosque"],
}
EMOJI = {("ciudad", "lluvia"): "☔", ("ciudad", "despejado"): "🌃", ("mar", "despejado"): "🌊",
         ("montana", "nieve"): "❄️", ("montana", "despejado"): "🏔️"}
SUFIJOS = [
    "beats lofi para estudiar y relajarse",
    "lofi hip hop para concentrarte",
    "música lofi para estudiar y trabajar",
    "lofi chill para descansar y dormir",
]
ETIQUETAS = [
    "lofi", "lofi hip hop", "lofi beats", "música lofi", "lofi en español", "música para estudiar",
    "música para concentrarse", "música para relajarse", "música para dormir", "beats para estudiar",
    "chill beats", "chillhop", "study music", "música instrumental", "jazzhop",
]


def semilla_entera(texto: str) -> int:
    return int.from_bytes(hashlib.sha256(texto.encode()).digest()[:8], "big")


def marca_tiempo(seg: float) -> str:
    seg = int(seg)
    h, m, s = seg // 3600, seg % 3600 // 60, seg % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class Escritor:
    """Escribe el WAV pista tras pista, encadenándolas con un pequeño solape
    y sumando un ambiente continuo (vinilo y, si toca, lluvia)."""

    def __init__(self, ruta: Path, ambiente: musica.Ambiente, solape=1.5):
        self.w = wave.open(str(ruta), "wb")
        self.w.setnchannels(2)
        self.w.setsampwidth(2)
        self.w.setframerate(SR)
        self.ambiente = ambiente
        self.cola = np.zeros((0, 2), np.float32)
        self.escritas = 0
        self.solape = int(solape * SR)

    @property
    def duracion(self) -> float:
        return (self.escritas + len(self.cola)) / SR

    def agregar(self, pista: np.ndarray) -> float:
        s = min(self.solape, len(self.cola), len(pista))
        pista = pista.copy()
        if s:
            pista[:s] += self.cola[len(self.cola) - s :]
        self._escribir(self.cola[: len(self.cola) - s])
        inicio = self.escritas / SR
        corte = max(0, len(pista) - self.solape)
        self._escribir(pista[:corte])
        self.cola = pista[corte:]
        return inicio

    def _escribir(self, x: np.ndarray):
        if not len(x):
            return
        x = np.clip(x + self.ambiente.generar(len(x)), -1.0, 1.0)
        self.w.writeframes((x * 32767).astype("<i2").tobytes())
        self.escritas += len(x)

    def cerrar(self):
        self._escribir(self.cola)
        self.w.close()


def main():
    ap = argparse.ArgumentParser(description="Genera un video lofi original listo para YouTube.")
    ap.add_argument("--minutos", type=float, default=60, help="duración aproximada del video")
    ap.add_argument("--salida", default="lofi/salida", help="carpeta de salida")
    ap.add_argument("--semilla", default=None, help="misma semilla = mismo video (por defecto, la fecha de hoy)")
    ap.add_argument("--canal", default=os.environ.get("LOFI_CANAL", ""), help="nombre del canal para la descripción")
    ap.add_argument("--rapido", action="store_true", help="720p, para pruebas")
    args = ap.parse_args()

    hoy = dt.date.today().isoformat()
    semilla = args.semilla or hoy
    rng = np.random.default_rng(semilla_entera(str(semilla)))
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    ancho, alto = (1280, 720) if args.rapido else (1920, 1080)
    fps, seg_bucle = 24, 20

    tipo = str(rng.choice(["ciudad", "mar", "montana"]))
    clima = {"ciudad": "lluvia" if rng.random() < 0.6 else "despejado",
             "mar": "despejado",
             "montana": "nieve" if rng.random() < 0.6 else "despejado"}[tipo]
    paleta = str(rng.choice(list(visual.PALETAS)))
    tema = str(rng.choice(TEMAS[(tipo, clima)]))
    sufijo = str(rng.choice(SUFIJOS))
    print(f"Semilla «{semilla}»: {tipo} / {clima} / paleta {paleta} — «{tema}»", flush=True)

    # 1. música
    t0 = time.time()
    ambiente = musica.Ambiente(rng, lluvia=(clima == "lluvia"))
    escritor = Escritor(salida / "audio.wav", ambiente)
    nombres = [str(n) for n in rng.permutation(NOMBRES)]
    temas = []
    objetivo = args.minutos * 60
    while escritor.duracion < objetivo:
        audio, info = musica.componer(rng)
        nombre = nombres[len(temas) % len(nombres)]
        inicio = escritor.agregar(audio)
        temas.append({"inicio": round(inicio, 2), "nombre": nombre, **info})
        print(f"  pista {len(temas):2d} {marca_tiempo(inicio):>8}  {nombre:<24} {info['tonalidad']}, "
              f"{info['bpm']} bpm, {info['melodia']}", flush=True)
    escritor.cerrar()
    dur = escritor.escritas / SR
    print(f"Música: {len(temas)} pistas, {marca_tiempo(dur)} en {time.time() - t0:.0f} s", flush=True)

    # 2. animación en bucle
    t0 = time.time()
    escena = visual.Escena(rng, tipo, paleta, clima, ancho, alto, fps, seg_bucle)
    escena.renderizar_bucle(salida / "bucle.mp4")
    print(f"Animación: bucle de {seg_bucle} s en {time.time() - t0:.0f} s", flush=True)

    # 3. video final: el bucle repetido + la música
    t0 = time.time()
    repeticiones = math.ceil(dur / seg_bucle) + 1
    (salida / "lista.txt").write_text("file 'bucle.mp4'\n" * repeticiones)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "concat", "-safe", "0", "-i", str(salida / "lista.txt"), "-i", str(salida / "audio.wav"),
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{dur:.3f}", "-movflags", "+faststart", str(salida / "video.mp4")],
        check=True,
    )
    (salida / "lista.txt").unlink()
    print(f"Video: {(salida / 'video.mp4').stat().st_size / 1e6:.0f} MB en {time.time() - t0:.0f} s", flush=True)

    # 4. miniatura y textos
    escena.miniatura(salida / "miniatura.jpg", tema, "lofi beats para estudiar y relajarse")
    emoji = EMOJI[(tipo, clima)]
    titulo = f"{tema} {emoji} {sufijo}"[:100]
    minutos = round(dur / 60)
    lista = "\n".join(f"{marca_tiempo(t['inicio'])} {t['nombre']}" for t in temas)
    firma = f"\n\n🎧 {args.canal}" if args.canal else ""
    descripcion = (
        f"{tema} {emoji} {minutos} minutos de beats lofi para estudiar, trabajar o descansar.\n\n"
        f"Lista de temas\n{lista}\n\n"
        "Toda la música y la animación de este video son originales: el canal las genera con su propio "
        "algoritmo, sin samples ni material de terceros.\n"
        "Hay un video nuevo cada día. Suscríbete para no perderte el siguiente."
        f"{firma}\n\n#lofi #lofihiphop #musicaparaestudiar"
    )
    meta = {
        "titulo": titulo,
        "descripcion": descripcion,
        "etiquetas": ETIQUETAS,
        "categoria": "10",
        "idioma": "es",
        "video": "video.mp4",
        "miniatura": "miniatura.jpg",
        "semilla": str(semilla),
        "escena": {"tipo": tipo, "clima": clima, "paleta": paleta},
        "duracion_seg": round(dur, 1),
        "temas": temas,
    }
    (salida / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    (salida / "audio.wav").unlink()
    (salida / "bucle.mp4").unlink()
    print(f"\nListo: {salida / 'video.mp4'}\nTítulo: {titulo}")


if __name__ == "__main__":
    main()
