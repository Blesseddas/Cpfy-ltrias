# Seguimiento automático de quinielas RD (Capafy AI)

## Configuración única (30 minutos, una sola vez)
1. Crea un repositorio en GitHub y sube el contenido de esta carpeta.
2. En **Settings > Pages** publica la rama principal (la app queda en `index.html`).
3. En **Actions** habilita los flujos de trabajo.
4. Abre https://loteriadela1.com/datos-abiertos, copia el enlace del botón de descarga del CSV y guárdalo en
   **Settings > Secrets and variables > Actions > Variables** con el nombre `L1_CSV_URL`.
5. En **Actions > Seguimiento diario > Run workflow**, ejecútalo una vez y confirma que termina en verde.

## Qué ocurre solo, cada noche (23:30 hora RD)
1. `recolectar_enloteria.py` lee EnLotería (ayer y hoy).
2. `recolectar_loteriadela1.py` lee el CSV abierto de Lotería de la 1 (últimos 7 días).
3. `actualizar_loterias.py` valida, une, detecta discrepancias y regenera `index.html`.
4. Se guarda todo en el repositorio.

## Reglas automáticas de calidad
- Si dos fuentes difieren, el sorteo queda como **Discrepancia**, sin números, y no entra en las estadísticas.
- Una discrepancia abierta solo se cierra sola cuando 2 o más fuentes distintas coinciden.
- Las filas **Resuelta (Alta/Media)** (verificadas externamente) están protegidas.
- Si los datos llevan más de 2 días sin avanzar, el flujo falla a propósito y GitHub te envía un correo.

## Límites reales
- Los sitios pueden bloquear las IP de GitHub o cambiar su formato. El sistema avisa, no inventa datos.
- Lotería de la 1 difirió de las otras fuentes en LoteDom Día y Nacional Gana Más (ago-sep 2026).
- Datos no certificados por actas oficiales. Atribución: Lotería de la 1 (CC BY 4.0), EnLotería, Datos Abiertos RD.
