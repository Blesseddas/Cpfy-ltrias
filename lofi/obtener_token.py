"""Obtiene el YT_REFRESH_TOKEN una sola vez, desde tu computadora.

1. En Google Cloud crea un cliente OAuth de tipo «App de escritorio» (ver lofi/README.md).
2. Ejecuta en tu computadora (no en GitHub):
       python obtener_token.py TU_CLIENT_ID TU_CLIENT_SECRET
   Añade --listas si quieres que los videos se agreguen solos a una lista de reproducción.
3. Se abre el navegador: entra con la cuenta del canal y acepta.
4. Copia el refresh token que aparece y guárdalo en GitHub como secreto YT_REFRESH_TOKEN.

Solo usa la biblioteca estándar de Python.
"""
import base64
import hashlib
import http.server
import json
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser

PUERTO = 8765
REDIRECCION = f"http://127.0.0.1:{PUERTO}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit("Uso: python obtener_token.py CLIENT_ID CLIENT_SECRET [--listas]")
    client_id, client_secret = args
    alcances = ["https://www.googleapis.com/auth/youtube.upload"]
    if "--listas" in sys.argv:
        alcances.append("https://www.googleapis.com/auth/youtube")

    verificador = secrets.token_urlsafe(64)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    estado = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECCION,
        "response_type": "code",
        "scope": " ".join(alcances),
        "access_type": "offline",
        "prompt": "consent",
        "state": estado,
        "code_challenge": reto,
        "code_challenge_method": "S256",
    })

    recibido = {}

    class Manejador(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" not in q and "error" not in q:
                self.send_response(404)
                self.end_headers()
                return
            recibido.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<p>Listo. Ya puedes cerrar esta pestaña y volver a la terminal.</p>".encode())

        def log_message(self, *a):
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", PUERTO), Manejador)
    print("Abriendo el navegador. Si no se abre, copia esta dirección:\n\n" + url + "\n")
    webbrowser.open(url)
    while not recibido:
        servidor.handle_request()

    if "error" in recibido:
        sys.exit(f"Google devolvió un error: {recibido['error']}")
    if recibido.get("state") != estado:
        sys.exit("La respuesta no coincide con la solicitud (state distinto). Vuelve a intentarlo.")

    datos = urllib.parse.urlencode({
        "code": recibido["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECCION,
        "grant_type": "authorization_code",
        "code_verifier": verificador,
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=datos) as r:
        respuesta = json.load(r)
    if "refresh_token" not in respuesta:
        sys.exit(f"Google no devolvió refresh token: {respuesta}")
    print("Tu YT_REFRESH_TOKEN (guárdalo como secreto en GitHub y no lo compartas):\n")
    print(respuesta["refresh_token"])


if __name__ == "__main__":
    main()
