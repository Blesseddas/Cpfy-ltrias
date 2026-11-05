"""Sube a YouTube el video que dejó generar.py (API de datos v3, subida reanudable).

Variables de entorno obligatorias (en GitHub: Settings > Secrets and variables > Actions > Secrets):
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Opcionales:
    YT_PRIVACIDAD    public | unlisted | private   (por defecto: public)
    YT_PLAYLIST_ID   lista de reproducción a la que añadir el video

Uso:
    python lofi/subir_youtube.py lofi/salida
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
SUBIDA_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
MINIATURA_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
LISTA_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
TROZO = 32 * 1024 * 1024  # múltiplo de 256 KiB, como pide la API


def token_acceso() -> str:
    faltan = [v for v in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") if not os.environ.get(v)]
    if faltan:
        sys.exit(f"Faltan variables de entorno: {', '.join(faltan)}")
    r = requests.post(TOKEN_URL, timeout=30, data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    })
    if r.status_code != 200:
        pista = ""
        if "invalid_grant" in r.text:
            pista = ("\nEl refresh token caducó o fue revocado. Si la pantalla de consentimiento OAuth está en modo "
                     "«Prueba», Google lo invalida a los 7 días: pásala a «En producción» y vuelve a ejecutar "
                     "obtener_token.py.")
        sys.exit(f"No se pudo renovar el acceso a YouTube ({r.status_code}): {r.text}{pista}")
    return r.json()["access_token"]


def _limpiar(texto: str, max_bytes: int) -> str:
    texto = texto.replace("<", "").replace(">", "")  # YouTube rechaza estos caracteres
    return texto.encode("utf-8")[:max_bytes].decode("utf-8", "ignore")


def iniciar_subida(token: str, meta: dict, tamano: int, privacidad: str) -> str:
    cuerpo = {
        "snippet": {
            "title": _limpiar(meta["titulo"], 400)[:100],
            "description": _limpiar(meta["descripcion"], 5000),
            "tags": meta["etiquetas"],
            "categoryId": meta.get("categoria", "10"),
            "defaultLanguage": meta.get("idioma", "es"),
        },
        "status": {"privacyStatus": privacidad, "selfDeclaredMadeForKids": False, "embeddable": True},
    }
    r = requests.post(
        SUBIDA_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(tamano),
            "X-Upload-Content-Type": "video/mp4",
        },
        data=json.dumps(cuerpo),
        timeout=60,
    )
    if r.status_code != 200:
        pista = "\nSe agotó la cuota diaria de la API; se reinicia a medianoche (hora del Pacífico)." \
            if "quotaExceeded" in r.text else ""
        sys.exit(f"YouTube rechazó la subida ({r.status_code}): {r.text}{pista}")
    return r.headers["Location"]


def _consultar(url: str, token: str, tamano: int):
    """Pregunta cuántos bytes llegaron. Devuelve (siguiente_byte, id_video_si_terminó)."""
    r = requests.put(url, headers={"Authorization": f"Bearer {token}", "Content-Length": "0",
                                   "Content-Range": f"bytes */{tamano}"}, timeout=60, allow_redirects=False)
    if r.status_code in (200, 201):
        return tamano, r.json()["id"]
    if r.status_code == 308:
        rango = r.headers.get("Range")
        return (int(rango.split("-")[1]) + 1 if rango else 0), None
    raise RuntimeError(f"estado {r.status_code}: {r.text[:300]}")


def subir_video(url: str, ruta: Path, token: str) -> str:
    tamano = ruta.stat().st_size
    inicio, fallos = 0, 0
    with open(ruta, "rb") as f:
        while True:
            f.seek(inicio)
            datos = f.read(TROZO)
            fin = inicio + len(datos) - 1
            try:
                r = requests.put(url, data=datos, timeout=600, allow_redirects=False, headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Length": str(len(datos)),
                    "Content-Range": f"bytes {inicio}-{fin}/{tamano}",
                })
                codigo = r.status_code
            except requests.RequestException as e:
                r, codigo = None, f"red: {e}"
            if codigo in (200, 201):
                return r.json()["id"]
            if codigo == 308:
                rango = r.headers.get("Range")
                inicio = int(rango.split("-")[1]) + 1 if rango else 0
                fallos = 0
                print(f"  {inicio / tamano:6.1%} subido", flush=True)
                continue
            if codigo == 401:
                token = token_acceso()
                continue
            if isinstance(codigo, int) and codigo not in (408, 429, 500, 502, 503, 504):
                sys.exit(f"Error al subir ({codigo}): {r.text[:500]}")
            fallos += 1
            if fallos > 8:
                sys.exit(f"La subida falló demasiadas veces (último error: {codigo}).")
            espera = min(2**fallos, 120)
            print(f"  error temporal ({codigo}); reintento en {espera} s", flush=True)
            time.sleep(espera)
            try:
                inicio, vid = _consultar(url, token, tamano)
                if vid:
                    return vid
            except (requests.RequestException, RuntimeError) as e:
                print(f"  no se pudo consultar el estado: {e}", flush=True)


def poner_miniatura(token: str, video_id: str, ruta: Path):
    r = requests.post(MINIATURA_URL, params={"videoId": video_id, "uploadType": "media"},
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                      data=ruta.read_bytes(), timeout=120)
    if r.status_code == 200:
        print("Miniatura puesta.")
    else:
        print(f"AVISO: no se pudo poner la miniatura ({r.status_code}). Las miniaturas personalizadas "
              f"requieren verificar el canal por teléfono en youtube.com/verify. Detalle: {r.text[:300]}")


def agregar_a_lista(token: str, video_id: str, lista: str):
    r = requests.post(LISTA_URL, params={"part": "snippet"}, timeout=60,
                      headers={"Authorization": f"Bearer {token}"},
                      json={"snippet": {"playlistId": lista,
                                        "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
    if r.status_code == 200:
        print("Añadido a la lista de reproducción.")
    else:
        print(f"AVISO: no se pudo añadir a la lista ({r.status_code}). Para listas, el token debe pedirse "
              f"con «obtener_token.py --listas». Detalle: {r.text[:300]}")


def main():
    carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else "lofi/salida")
    meta = json.loads((carpeta / "meta.json").read_text())
    video = carpeta / meta["video"]
    privacidad = os.environ.get("YT_PRIVACIDAD") or "public"
    if privacidad not in ("public", "unlisted", "private"):
        sys.exit(f"YT_PRIVACIDAD no válida: {privacidad}")

    token = token_acceso()
    print(f"Subiendo «{meta['titulo']}» ({video.stat().st_size / 1e6:.0f} MB, {privacidad})…", flush=True)
    url = iniciar_subida(token, meta, video.stat().st_size, privacidad)
    video_id = subir_video(url, video, token)
    enlace = f"https://youtu.be/{video_id}"
    print(f"Video subido: {enlace}")

    token = token_acceso()
    poner_miniatura(token, video_id, carpeta / meta["miniatura"])
    if os.environ.get("YT_PLAYLIST_ID"):
        agregar_a_lista(token, video_id, os.environ["YT_PLAYLIST_ID"])

    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a") as f:
            f.write(f"### Video publicado\n\n[{meta['titulo']}]({enlace}) · {privacidad}\n")


if __name__ == "__main__":
    main()
