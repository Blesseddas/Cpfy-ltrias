"""Animación original en bucle perfecto (ciudad, mar o montaña) y miniatura.

Todo lo que se mueve es periódico con el largo del bucle, así que el video
se puede repetir sin que se note el corte.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PALETAS = {
    "medianoche": dict(cielo=[(10, 12, 34), (44, 40, 92)], capas=[(52, 50, 104), (30, 29, 66), (14, 14, 34)],
                       luz=(255, 196, 120), luna=(248, 240, 214)),
    "atardecer": dict(cielo=[(38, 24, 70), (238, 138, 112)], capas=[(128, 74, 112), (80, 46, 88), (38, 24, 54)],
                      luz=(255, 210, 140), luna=(255, 228, 186)),
    "lavanda": dict(cielo=[(22, 20, 54), (140, 110, 180)], capas=[(96, 80, 146), (60, 50, 104), (30, 26, 62)],
                    luz=(255, 220, 160), luna=(250, 242, 255)),
    "bosque": dict(cielo=[(6, 28, 38), (48, 110, 115)], capas=[(32, 84, 90), (18, 56, 62), (8, 30, 36)],
                   luz=(255, 200, 120), luna=(232, 250, 240)),
    "rosa": dict(cielo=[(26, 15, 46), (196, 90, 156)], capas=[(112, 52, 112), (70, 32, 80), (34, 17, 48)],
                 luz=(255, 190, 140), luna=(255, 236, 244)),
}

FUENTES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _fuente(tam):
    for f in FUENTES:
        if Path(f).exists():
            return ImageFont.truetype(f, tam)
    return ImageFont.load_default(size=tam)


def _mezclar(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


class Escena:
    def __init__(self, rng: np.random.Generator, tipo: str, paleta: str, clima: str,
                 ancho=1920, alto=1080, fps=24, segundos=20):
        self.rng, self.tipo, self.clima = rng, tipo, clima
        self.p = PALETAS[paleta]
        self.W, self.H, self.fps = ancho, alto, fps
        self.F = fps * segundos
        self.s = alto / 1080.0  # escala para tamaños
        self.fondo = self._fondo()
        self._preparar_dinamicos()

    # ------------------------------------------------------------ fondo
    def _fondo(self) -> Image.Image:
        W, H, rng, p, s = self.W, self.H, self.rng, self.p, self.s
        y = np.linspace(0, 1, H)[:, None, None] ** 1.3
        arriba, abajo = np.array(p["cielo"][0]), np.array(p["cielo"][1])
        cielo = (arriba + (abajo - arriba) * y) * np.ones((1, W, 1))
        img = Image.fromarray(cielo.astype(np.uint8), "RGB").convert("RGBA")

        # estrellas fijas
        d = ImageDraw.Draw(img)
        n_est = 60 if self.clima == "lluvia" else 260
        for _ in range(n_est):
            x, yy = rng.uniform(0, W), rng.uniform(0, H * 0.6)
            a = int(rng.uniform(60, 200) * (1 - yy / (H * 0.6)))
            r = rng.choice([0.6, 1.0, 1.4]) * s
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=(255, 255, 255, a))

        # luna con halo
        self.luna = (W * rng.uniform(0.62, 0.85), H * rng.uniform(0.14, 0.26))
        r = 62 * s
        halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)
        lx, ly = self.luna
        hd.ellipse([lx - r * 3, ly - r * 3, lx + r * 3, ly + r * 3], fill=p["luna"] + (60,))
        halo = halo.filter(ImageFilter.GaussianBlur(r * 1.2))
        img = Image.alpha_composite(img, halo)
        d = ImageDraw.Draw(img)
        d.ellipse([lx - r, ly - r, lx + r, ly + r], fill=p["luna"] + (255,))
        sombra = _mezclar(p["luna"], p["cielo"][0], 0.08)
        for _ in range(5):  # cráteres suaves
            cx, cy = lx + rng.uniform(-0.5, 0.5) * r, ly + rng.uniform(-0.5, 0.5) * r
            cr = rng.uniform(0.08, 0.2) * r
            d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=sombra + (255,))

        getattr(self, f"_fondo_{self.tipo}")(img)

        # niebla baja, viñeta y grano fijo
        arr = np.asarray(img.convert("RGB")).astype(np.float32)
        yy, xx = np.mgrid[0:H, 0:W]
        dist = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        arr *= (1 - 0.45 * np.clip(dist - 0.55, 0, 1) ** 1.5)[:, :, None]
        arr += rng.normal(0, 5, (H, W, 1))
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")

    def _fondo_ciudad(self, img):
        W, H, rng, p, s = self.W, self.H, self.rng, self.p, self.s
        d = ImageDraw.Draw(img)
        self.ventanas = []
        for capa, (color, alto_min, alto_max) in enumerate(
            [(p["capas"][0], 0.30, 0.55), (p["capas"][1], 0.22, 0.45), (p["capas"][2], 0.12, 0.34)]
        ):
            x = -rng.uniform(0, 80) * s
            while x < W:
                ancho = rng.uniform(70, 190) * s * (1 + capa * 0.2)
                alto = H * rng.uniform(alto_min, alto_max)
                top = H - alto
                d.rectangle([x, top, x + ancho, H], fill=color + (255,))
                if rng.random() < 0.25:  # antena
                    ax = x + ancho * rng.uniform(0.3, 0.7)
                    d.rectangle([ax, top - 40 * s, ax + 3 * s, top], fill=color + (255,))
                    if capa > 0:
                        d.ellipse([ax - 3 * s, top - 44 * s, ax + 6 * s, top - 37 * s], fill=(255, 90, 90, 200))
                if capa > 0:  # ventanas
                    vw, vh = 9 * s * (1 + capa * 0.3), 13 * s * (1 + capa * 0.3)
                    paso_x, paso_y = vw * 2.2, vh * 1.9
                    yy = top + paso_y
                    while yy < H - paso_y:
                        xx = x + paso_x * 0.6
                        while xx < x + ancho - paso_x * 0.6:
                            if rng.random() < 0.28:
                                k = rng.uniform(0.55, 1.0)
                                c = _mezclar(color, p["luz"], k)
                                caja = [xx, yy, xx + vw, yy + vh]
                                d.rectangle(caja, fill=c + (255,))
                                self.ventanas.append((caja, color, c))
                            xx += paso_x
                        yy += paso_y
                x += ancho + rng.uniform(0, 14) * s

    def _fondo_mar(self, img):
        W, H, rng, p, s = self.W, self.H, self.rng, self.p, self.s
        d = ImageDraw.Draw(img)
        self.horizonte = H * 0.64
        hz = self.horizonte
        # isla lejana
        pts = [(W * 0.05, hz)]
        for i in range(30):
            xx = W * 0.05 + i * W * 0.012
            pts.append((xx, hz - 40 * s * math.sin(math.pi * i / 29) ** 0.7 - rng.uniform(0, 6) * s))
        pts.append((W * 0.41, hz))
        d.polygon(pts, fill=p["capas"][0] + (255,))
        # agua
        mar = np.linspace(0, 1, int(H - hz))[:, None, None]
        a = np.array(_mezclar(p["cielo"][1], p["capas"][1], 0.5))
        b = np.array(p["capas"][2])
        agua = (a + (b - a) * mar) * np.ones((1, W, 1))
        img.paste(Image.fromarray(agua.astype(np.uint8), "RGB").convert("RGBA"), (0, int(hz)))
        d = ImageDraw.Draw(img)
        # acantilado y faro
        c = p["capas"][2]
        acantilado = [(W * 0.70, H), (W * 0.74, H * 0.80), (W * 0.80, H * 0.74), (W * 0.90, H * 0.72),
                      (W * 0.97, H * 0.76), (W, H * 0.75), (W, H)]
        d.polygon(acantilado, fill=c + (255,))
        bx, by = W * 0.86, H * 0.725
        alto_faro, base, cima = 230 * s, 34 * s, 22 * s
        d.polygon([(bx - base, by), (bx + base, by), (bx + cima, by - alto_faro), (bx - cima, by - alto_faro)],
                  fill=(232, 226, 220, 255))
        for k in range(3):  # franjas
            y0 = by - alto_faro * (0.15 + 0.28 * k)
            y1 = y0 - alto_faro * 0.12
            w0 = cima + (base - cima) * (by - y0) / alto_faro
            w1 = cima + (base - cima) * (by - y1) / alto_faro
            d.polygon([(bx - w0, y0), (bx + w0, y0), (bx + w1, y1), (bx - w1, y1)], fill=(190, 70, 70, 255))
        lt = by - alto_faro
        d.rectangle([bx - cima - 6 * s, lt - 6 * s, bx + cima + 6 * s, lt], fill=c + (255,))
        d.rectangle([bx - cima * 0.8, lt - 40 * s, bx + cima * 0.8, lt - 6 * s], fill=p["luz"] + (255,))
        d.polygon([(bx - cima - 4 * s, lt - 40 * s), (bx + cima + 4 * s, lt - 40 * s), (bx, lt - 70 * s)],
                  fill=c + (255,))
        self.lampara = (bx, lt - 23 * s)

    def _fondo_montana(self, img):
        W, H, rng, p, s = self.W, self.H, self.rng, self.p, self.s
        d = ImageDraw.Draw(img)
        xs = np.linspace(0, W, 200)
        for capa, (color, base, amp) in enumerate(
            [(p["capas"][0], 0.55, 0.16), (p["capas"][1], 0.68, 0.12), (p["capas"][2], 0.82, 0.08)]
        ):
            y = np.full_like(xs, H * base)
            for k in range(1, 6):
                y -= H * amp / k * np.abs(np.sin(xs / W * math.pi * k * rng.uniform(0.8, 1.6) + rng.uniform(0, 6)))
            d.polygon([(0, H)] + list(zip(xs, y)) + [(W, H)], fill=color + (255,))
            if capa == 2:
                self.suelo = y
        # pinos
        c = p["capas"][2]
        for _ in range(26):
            px = rng.uniform(0, W)
            py = float(np.interp(px, xs, self.suelo)) + 6 * s
            alto = rng.uniform(70, 150) * s
            for k in range(3):
                w = alto * (0.32 - k * 0.07)
                y0 = py - alto * k * 0.28
                d.polygon([(px - w, y0), (px + w, y0), (px, y0 - alto * 0.5)], fill=c + (255,))
        # cabaña con ventana encendida
        cx = W * rng.uniform(0.22, 0.38)
        cy = float(np.interp(cx, xs, self.suelo)) + 10 * s
        aw, ah = 150 * s, 90 * s
        d.rectangle([cx - aw / 2, cy - ah, cx + aw / 2, cy], fill=_mezclar(c, (0, 0, 0), 0.3) + (255,))
        d.polygon([(cx - aw / 2 - 18 * s, cy - ah), (cx + aw / 2 + 18 * s, cy - ah), (cx, cy - ah - 70 * s)],
                  fill=_mezclar(c, (0, 0, 0), 0.45) + (255,))
        d.rectangle([cx + aw * 0.2, cy - ah - 70 * s, cx + aw * 0.32, cy - ah - 20 * s],
                    fill=_mezclar(c, (0, 0, 0), 0.45) + (255,))
        vent = [cx - aw * 0.3, cy - ah * 0.7, cx - aw * 0.05, cy - ah * 0.35]
        d.rectangle(vent, fill=self.p["luz"] + (255,))
        self.ventana_cabana = vent
        self.chimenea = (cx + aw * 0.26, cy - ah - 74 * s)

    # ------------------------------------------------------- dinámicos
    def _preparar_dinamicos(self):
        rng, W, H, F, s = self.rng, self.W, self.H, self.F, self.s
        self.titilan = [(rng.uniform(0, W), rng.uniform(0, H * 0.5), int(rng.integers(1, 4)), rng.uniform(0, 6.28),
                         rng.uniform(1.0, 2.2) * s) for _ in range(40 if self.clima != "lluvia" else 10)]
        # estrella fugaz (una por vuelta del bucle)
        self.fugaz = (int(rng.integers(0, F)), rng.uniform(0.1, 0.6) * W, rng.uniform(0.05, 0.25) * H)
        if self.clima == "lluvia":
            self.gotas = []
            for capa, (n, largo, vel, alfa) in enumerate([(220, 18, 9, 60), (160, 30, 16, 95), (70, 48, 24, 140)]):
                for _ in range(n):
                    self.gotas.append((rng.uniform(-0.1, 1.1) * W, rng.uniform(0, 1), vel + int(rng.integers(0, 4)),
                                       largo * s, alfa))
        if self.clima == "nieve":
            self.copos = [(rng.uniform(0, W), rng.uniform(0, 1), int(rng.integers(1, 3)), rng.uniform(1.0, 3.6) * s,
                           rng.uniform(6, 28) * s, int(rng.integers(1, 4)), rng.uniform(0, 6.28)) for _ in range(320)]
        if self.tipo == "ciudad" and self.ventanas:
            sel = rng.choice(len(self.ventanas), size=min(14, len(self.ventanas)), replace=False)
            self.parpadeo = []
            for i in sel:
                a = int(rng.integers(0, F))
                b = a + int(rng.integers(F // 6, F // 2))
                self.parpadeo.append((self.ventanas[i], a, b))
        if self.tipo == "mar":
            hz = self.horizonte
            lx = self.luna[0]
            self.brillos = [(lx + rng.normal(0, 30 + (y - hz) * 0.35) * s, y, rng.uniform(10, 60) * s,
                             int(rng.integers(1, 4)), rng.uniform(0, 6.28))
                            for y in np.linspace(hz + 4, H, 90)]
            self.olas = [(rng.uniform(0, W), rng.uniform(hz + 10, H), rng.uniform(30, 160) * s,
                          int(rng.integers(1, 3)), rng.uniform(0, 6.28)) for _ in range(120)]

    def cuadro(self, f: int) -> Image.Image:
        W, H, F, s, p = self.W, self.H, self.F, self.s, self.p
        ph = 2 * math.pi * f / F
        capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)

        for x, y, m, fi, r in self.titilan:
            a = int(110 + 110 * math.sin(m * ph + fi))
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, max(0, a)))

        f0, fx, fy = self.fugaz
        k = (f - f0) % F
        dur = int(self.fps * 0.7)
        if k < dur:
            t = k / dur
            x1, y1 = fx + t * 420 * s, fy + t * 160 * s
            for j in range(12):
                tt = j / 12
                d.line([x1 - tt * 160 * s, y1 - tt * 60 * s, x1 - (tt + 0.09) * 160 * s, y1 - (tt + 0.09) * 60 * s],
                       fill=(255, 255, 255, int(220 * (1 - tt) * (1 - t))), width=max(1, int(2 * s)))

        if self.tipo == "ciudad":
            for (caja, apagada, encendida), a, b in self.parpadeo:
                if a <= f < b or a <= f + F < b:
                    d.rectangle(caja, fill=apagada + (255,))
        elif self.tipo == "mar":
            for x, y, w, m, fi in self.brillos:
                a = 0.5 + 0.5 * math.sin(m * ph + fi)
                ww = w * (0.4 + 0.6 * a)
                d.line([x - ww / 2, y, x + ww / 2, y], fill=p["luna"] + (int(150 * a),), width=max(1, int(2 * s)))
            for x, y, w, m, fi in self.olas:
                xx = x + 25 * s * math.sin(m * ph + fi)
                a = int(40 + 30 * math.sin(m * ph + fi + 1))
                d.line([xx, y, xx + w, y], fill=(255, 255, 255, a), width=max(1, int(s)))
            self._haz_faro(capa, ph)
        elif self.tipo == "montana":
            self._humo(capa, ph)

        if self.clima == "lluvia":
            pend = 0.18
            for x0, y0, v, largo, alfa in self.gotas:
                y = ((y0 + v * f / F) % 1.0) * (H + largo) - largo
                x = x0 + pend * y
                d.line([x, y, x + pend * largo, y + largo], fill=(200, 215, 255, alfa), width=max(1, int(1.4 * s)))
        if self.clima == "nieve":
            for x0, y0, v, r, amp, m, fi in self.copos:
                y = ((y0 + v * f / F) % 1.0) * (H + 2 * r) - r
                x = x0 + amp * math.sin(m * ph + fi)
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 200))

        out = self.fondo.convert("RGBA")
        out.alpha_composite(capa)
        return out.convert("RGB")

    def _haz_faro(self, capa, ph):
        """Haz giratorio, dibujado en baja resolución y difuminado."""
        k = 4
        W, H = self.W // k, self.H // k
        lx, ly = self.lampara[0] / k, self.lampara[1] / k
        th = 2 * ph  # dos vueltas por bucle
        c = math.cos(th)
        largo = W * 0.9 * abs(c)
        alfa = int(110 * abs(c) ** 0.5)
        chica = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(chica)
        sentido = 1 if c > 0 else -1
        if largo > 4:
            d.polygon([(lx, ly - 1), (lx + sentido * largo, ly - 14), (lx + sentido * largo, ly + 12), (lx, ly + 1)],
                      fill=self.p["luz"] + (alfa,))
        destello = max(0.0, math.sin(th)) * (1 - abs(c)) ** 2
        r = 4 + 18 * destello
        d.ellipse([lx - r, ly - r, lx + r, ly + r], fill=self.p["luz"] + (int(90 + 160 * destello),))
        chica = chica.filter(ImageFilter.GaussianBlur(3))
        capa.alpha_composite(chica.resize((self.W, self.H), Image.BILINEAR))

    def _humo(self, capa, ph):
        k = 4
        chica = Image.new("RGBA", (self.W // k, self.H // k), (0, 0, 0, 0))
        d = ImageDraw.Draw(chica)
        cx, cy = self.chimenea[0] / k, self.chimenea[1] / k
        for j in range(8):
            t = ((ph / (2 * math.pi)) * 2 + j / 8) % 1.0  # cada bocanada sube dos veces por bucle
            x = cx + 12 * t + 4 * math.sin(6 * t + j)
            y = cy - 60 * t
            r = 2 + 9 * t
            d.ellipse([x - r, y - r, x + r, y + r], fill=(220, 220, 230, int(70 * (1 - t))))
        # resplandor cálido de la ventana, como de chimenea encendida
        v = [c / k for c in self.ventana_cabana]
        a = int(70 + 30 * math.sin(3 * ph) + 18 * math.sin(7 * ph))
        mx, my, r = (v[0] + v[2]) / 2, (v[1] + v[3]) / 2, (v[2] - v[0]) * 1.4
        d.ellipse([mx - r, my - r, mx + r, my + r], fill=self.p["luz"] + (a,))
        chica = chica.filter(ImageFilter.GaussianBlur(2.5))
        capa.alpha_composite(chica.resize((self.W, self.H), Image.BILINEAR))

    # --------------------------------------------------------- salida
    def renderizar_bucle(self, ruta: Path):
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{self.W}x{self.H}", "-r", str(self.fps), "-i", "-",
               "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-tune", "animation",
               "-pix_fmt", "yuv420p", "-g", str(self.fps * 2), "-keyint_min", str(self.fps * 2),
               "-sc_threshold", "0", "-movflags", "+faststart", str(ruta)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for f in range(self.F):
                proc.stdin.write(self.cuadro(f).tobytes())
        finally:
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError("ffmpeg falló al crear el bucle de video")

    def miniatura(self, ruta: Path, titulo: str, subtitulo: str):
        img = self.cuadro(0).resize((1280, 720), Image.LANCZOS).convert("RGBA")
        # degradado oscuro abajo para que el texto se lea sobre cualquier fondo
        alfa = (np.clip((np.arange(720) - 330) / 390, 0, 1) ** 1.2 * 170).astype(np.uint8)
        degradado = np.zeros((720, 1280, 4), np.uint8)
        degradado[:, :, 3] = alfa[:, None]
        img = Image.alpha_composite(img, Image.fromarray(degradado, "RGBA"))
        sombra = Image.new("RGBA", img.size, (0, 0, 0, 0))
        texto = Image.new("RGBA", img.size, (0, 0, 0, 0))
        f1, f2 = _fuente(84), _fuente(40)
        lineas = _partir(titulo, f1, 1100)
        y = 720 - 90 - 92 * len(lineas) - 60
        for capa, desp, color in ((sombra, 4, (0, 0, 0, 200)), (texto, 0, (255, 255, 255, 255))):
            d = ImageDraw.Draw(capa)
            yy = y
            for linea in lineas:
                d.text((70 + desp, yy + desp), linea, font=f1, fill=color)
                yy += 92
            d.text((74 + desp, yy + 16 + desp), subtitulo, font=f2,
                   fill=color if capa is sombra else (255, 236, 200, 255))
        img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(6)))
        img = Image.alpha_composite(img, texto)
        img.convert("RGB").save(ruta, "JPEG", quality=90)


def _partir(texto, fuente, ancho):
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if fuente.getlength(prueba) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    return lineas + [actual]
