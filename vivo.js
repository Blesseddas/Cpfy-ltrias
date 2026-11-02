// Resultados de hoy casi al instante, para la portada, la herramienta y el dashboard.
// Junta hoy.json (lo escribe el robot de GitHub, que a veces tarda horas en correr) con los datos abiertos de
// loteriadela1.com (licencia CC BY 4.0), que el navegador puede leer directo y traen cada sorteo pocos minutos después.
// LoteDom Noche no está en loteriadela1: esa llega solo por hoy.json. Si las dos fuentes traen una quiniela, manda hoy.json.
var QHLNVivo = (function () {
  var MAPA = { // loteria.key|sesion -> quiniela; las mismas reglas que recolectar_loteriadela1.py
    "la-primera|dia": "La Primera Día", "la-primera|noche": "La Primera Noche",
    "la-suerte|dia": "La Suerte Día", "la-suerte|noche": "La Suerte Tarde",
    "lotedom|dia": "LoteDom Día", "loteka|dia": "Loteka Día", "loteka|noche": "Loteka Noche",
    "nacional|noche": "Nacional Noche", "real|dia": "Real Día", "real|noche": "Real Noche"
  };
  var rd = function (o) { return new Intl.DateTimeFormat(o.hour ? "es-DO" : "en-CA", Object.assign({ timeZone: "America/Santo_Domingo" }, o)).format(new Date()) };
  var hoyRD = function () { return rd({ year: "numeric", month: "2-digit", day: "2-digit" }) };
  var horaRD = function () { return rd({ hour: "2-digit", minute: "2-digit", hour12: false }) };
  function quiniela(s, domingo) {
    var k = s.loteria && s.loteria.key, j = (s.juego && s.juego.nombre) || "", ses = s.sesion;
    if (k === "nacional" && /^Gana M/.test(j)) return ses === "dia" ? "Nacional Gana Más" : null;
    if (j !== "Quiniela") return null;
    // Leidsa: el domingo vale el sorteo de las 3:55 pm ("dia"); los demás días, el de la noche
    if (k === "leidsa") return (domingo ? ses === "dia" : ses === "noche") ? "Leidsa Quiniela" : null;
    return MAPA[k + "|" + ses] || null;
  }
  function deLaUno(f) {
    return fetch("https://loteriadela1.com/datos/sorteos.json?desde=" + f + "&t=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null })
      .then(function (j) {
        var o = {}, dom = new Date(f + "T12:00:00Z").getUTCDay() === 0;
        ((j && j.sorteos) || []).forEach(function (s) {
          var q = s.fecha === f && quiniela(s, dom), x = (s.numeros || []).slice(0, 3);
          if (q && x.length === 3 && x.every(function (v) { return /^\d{2}$/.test(v) })) o[q] = x;
        });
        return o;
      }).catch(function () { return {} });
  }
  function delRobot() {
    return fetch("hoy.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null }).catch(function () { return null });
  }
  // Devuelve lo mismo que hoy.json: {fecha, actualizado, fuente, r: {quiniela: [1ra, 2da, 3ra]}}, o null si no hay nada
  function cargar() {
    var f = hoyRD();
    return Promise.all([delRobot(), deLaUno(f)]).then(function (a) {
      var H = a[0], L = a[1], nuevas = Object.keys(L).filter(function (k) { return !(H && H.fecha === f && H.r && H.r[k]) });
      if (!nuevas.length) return H && H.r ? H : null;
      var r = {}, base = H && H.fecha === f && H.r ? H.r : {};
      Object.keys(L).forEach(function (k) { r[k] = L[k] });
      Object.keys(base).forEach(function (k) { r[k] = base[k] });
      return { fecha: f, actualizado: horaRD(), fuente: Object.keys(base).length ? (H.fuente || "EnLotería") + " y loteriadela1.com" : "loteriadela1.com", r: r };
    });
  }
  return { cargar: cargar, hoy: hoyRD };
})();
