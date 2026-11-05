# Canal lofi automático

Cada día, GitHub Actions crea un video lofi **original** de ~1 hora y lo publica en tu canal de YouTube,
con su miniatura, su descripción y capítulos por tema. No necesitas una computadora encendida.

| Qué | Cómo se hace |
|---|---|
| Música | `musica.py` compone y sintetiza cada pista: acordes de jazz (7.ª y 9.ª), batería con swing, bajo, melodía (vibráfono, flauta, guitarra o piano eléctrico), reverb, cinta gastada y vinilo. Sin samples. |
| Animación | `visual.py` dibuja una escena (ciudad con lluvia, faro junto al mar o cabaña en la montaña con nieve) en 5 paletas, con lluvia, nieve, estrellas, humo y haz de faro en bucle perfecto de 20 s. |
| Textos | `generar.py` crea el título, la descripción con la lista de temas en minutos (YouTube la convierte en capítulos) y las etiquetas. |
| Publicación | `subir_youtube.py` sube el video por la API oficial de YouTube (subida reanudable), pone la miniatura y, si quieres, lo añade a una lista. |

Cada día sale distinto: escena, paleta, tonalidades, tempo, progresiones, instrumentos y nombres de temas
cambian según la fecha.

## Probarlo en tu computadora

```bash
pip install -r lofi/requirements.txt     # y tener ffmpeg instalado
python lofi/generar.py --minutos 5 --rapido --salida lofi/salida
```

Abre `lofi/salida/video.mp4`, `miniatura.jpg` y `meta.json`.

## Configuración única (unos 30 minutos)

### 1. El canal
1. Crea el canal en YouTube y **verifícalo por teléfono** en <https://www.youtube.com/verify>.
   Sin verificar, YouTube no deja subir videos de más de 15 minutos ni poner miniaturas propias.

### 2. Acceso a la API de YouTube (Google Cloud)
1. En <https://console.cloud.google.com> crea un proyecto (por ejemplo «canal-lofi»).
2. **APIs y servicios > Biblioteca**: activa **YouTube Data API v3**.
3. **Pantalla de consentimiento OAuth**: tipo *Externo*, pon tu correo y añádete como usuario de prueba.
   Después pulsa **Publicar app** (pasar a *En producción*). Si se queda en *Prueba*, Google invalida el token
   cada 7 días y la subida automática deja de funcionar.
4. **Credenciales > Crear credenciales > ID de cliente OAuth**, tipo **App de escritorio**.
   Anota el *Client ID* y el *Client secret*.
5. **Solicita la auditoría de la API**: Google bloquea en «privado» los videos que suben los proyectos nuevos
   no auditados. Pídela en el formulario
   [YouTube API Services – Audit and Quota Extension](https://support.google.com/youtube/contact/yt_api_form).
   Mientras la aprueban (puede tardar semanas), mira la opción B más abajo.

### 3. El token (una sola vez, en tu computadora)
```bash
python lofi/obtener_token.py TU_CLIENT_ID TU_CLIENT_SECRET
```
Se abre el navegador: entra con la cuenta del canal y acepta (Google avisará de que la app no está
verificada; es tu propia app: *Configuración avanzada > Ir a…*). Copia el token que aparece.
Añade `--listas` al final si quieres que los videos se agreguen solos a una lista de reproducción.

### 4. GitHub
En **Settings > Secrets and variables > Actions**:

| Tipo | Nombre | Valor |
|---|---|---|
| Secret | `YT_CLIENT_ID` | el Client ID |
| Secret | `YT_CLIENT_SECRET` | el Client secret |
| Secret | `YT_REFRESH_TOKEN` | el token del paso 3 |
| Variable (opcional) | `LOFI_CANAL` | nombre del canal, para la firma de la descripción |
| Variable (opcional) | `LOFI_MINUTOS` | duración diaria (por defecto 60) |
| Variable (opcional) | `LOFI_PRIVACIDAD` | `public`, `unlisted` o `private` (por defecto `public`) |
| Variable (opcional) | `LOFI_PLAYLIST_ID` | ID de una lista de reproducción (empieza por `PL`) |

### 5. Encenderlo
1. Une esta rama a `main`: GitHub solo ejecuta los horarios desde la rama principal.
2. **Actions > Canal lofi (video diario) > Run workflow** para la primera prueba (tarda ~10–15 min).
3. Desde entonces se publica solo todos los días a las 9:17 a. m. (hora RD). Para cambiar la hora,
   edita el `cron` en `.github/workflows/lofi.yml` (está en UTC).

**Opción B (sin API o mientras llega la auditoría):** ejecuta el flujo con «Subir a YouTube» desmarcado,
o sin los secretos. El video, la miniatura y `meta.json` quedan en la ejecución como artefacto
descargable durante 3 días; lo subes tú en YouTube Studio y programas la hora de publicación.

## Transmisión en vivo 24/7 (opcional)

`en_vivo.sh` transmite sin parar los videos de una carpeta a YouTube Live. Necesita un servidor siempre
encendido (un VPS pequeño basta, porque no recodifica el video), porque GitHub Actions corta a las 6 horas.

```bash
YT_STREAM_KEY=tu-clave-de-transmision ./lofi/en_vivo.sh carpeta_con_videos
```

La clave está en YouTube Studio > Emitir en directo. La primera vez que activas los directos,
YouTube tarda hasta 24 horas en habilitarlos.

## Antes de publicar, ten en cuenta
- **Monetización:** YouTube no paga por contenido «inauténtico» (producido en masa o repetitivo). La variedad
  diaria ayuda, pero no lo garantiza. Para el Programa de Socios conviene darle identidad propia al canal:
  un nombre, un personaje o una mascota tuyos, y tu propia curaduría.
- **Originalidad:** todo lo que genera este código es propio. No uses el nombre, el personaje ni las imágenes
  de otros canales (por ejemplo, Lofi Girl) en títulos, etiquetas o miniaturas: infringe sus derechos y las
  normas de spam de YouTube.
- **Cuota de la API:** un proyecto tiene 10 000 unidades al día; una subida diaria cabe con margen.
- **Tamaño:** un video de 1 hora a 1080p pesa entre 1.3 y 2.4 GB según la escena (la lluvia es la más pesada).
