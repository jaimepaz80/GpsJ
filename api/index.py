<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ColectoraGps - Topografía GNSS v4.2</title>
    <link rel="manifest" href="manifest.json">
    <meta name="theme-color" content="#2c3e50">
    
    <style>
        :root { --primary: #2c3e50; --accent: #e74c3c; --active: #27ae60; --bg: #ecf0f1; --text: #333; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); padding: 15px; display: flex; justify-content: center; margin: 0; }
        .app-container { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 500px; width: 100%; text-align: center; }
        h1 { color: var(--primary); font-size: 1.4rem; margin-top: 0; border-bottom: 2px solid #ddd; padding-bottom: 10px; }
        
        .whatsapp-banner { margin-bottom: 20px; padding: 15px; background-color: #f0fdf4; border: 1px solid #25d366; border-radius: 8px; font-size: 0.85rem; color: #2c3e50; text-align: center; }
        .whatsapp-btn { display: inline-block; margin-top: 10px; background-color: #25d366; color: white; padding: 10px 20px; text-decoration: none; font-weight: bold; border-radius: 5px; transition: 0.3s; font-size: 0.9rem; }
        .whatsapp-btn:hover { background-color: #128c7e; }

        .input-group { text-align: left; margin-bottom: 15px; }
        label { font-weight: bold; font-size: 0.85rem; color: #555; display: block; margin-bottom: 5px; }
        input[type="text"], select { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; font-size: 1rem; }

        .main-timer { font-size: 3.5rem; font-weight: bold; color: var(--primary); margin: 10px 0; font-family: monospace; letter-spacing: 2px;}

        .status-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 0.85rem; margin-bottom: 15px; background: #ddd; color: #555; transition: 0.3s; width: 80%;}
        .status-recording { animation: pulse 2s infinite; }
        
        .data-panel { background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #eee; text-align: left; margin-bottom: 15px; font-size: 0.9rem; }
        .data-row { display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px dashed #ccc; padding-bottom: 4px; }
        .data-row:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .label { font-weight: bold; color: var(--primary); }
        .value { font-family: monospace; font-size: 1rem; color: #2980b9; }

        .panel-promedio { display: none; background: #e8f8f5; border: 2px solid var(--active); padding: 15px; border-radius: 8px; text-align: left; margin-bottom: 15px; font-size: 0.95rem; }
        .panel-promedio h3 { margin: 0 0 10px 0; color: var(--active); font-size: 1.1rem; text-align: center; border-bottom: 1px solid #a3e4d7; padding-bottom: 5px;}
        .prom-val { font-family: monospace; font-weight: bold; color: #117a65; font-size: 1.1rem;}
        
        .panel-libreta { display: none; background: #ebf5fb; border: 2px solid #3498db; padding: 15px; border-radius: 8px; text-align: left; margin-bottom: 15px; }
        
        button { width: 100%; padding: 14px; font-size: 0.95rem; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; transition: 0.3s; margin-bottom: 10px; }
        #btnToggle { background: var(--primary); color: white; }
        #btnToggle.recording { background: var(--accent); }
        
        .action-buttons { display: none; gap: 10px; margin-top: 10px; }
        .btn-half { width: 50%; padding: 12px; font-size: 0.85rem;}
        #btnExport { background: #34495e; color: white; margin-bottom: 0;}
        #btnShare { background: #27ae60; color: white; margin-bottom: 0;}
        #btnDiscard { background: #e74c3c; color: white; display: none; margin-top: 10px; }

        #log { background: #111; color: #0f0; padding: 10px; border-radius: 6px; font-family: monospace; font-size: 0.75rem; height: 100px; overflow-y: auto; text-align: left; margin-top: 15px; }

        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(39, 174, 96, 0); } 100% { box-shadow: 0 0 0 0 rgba(39, 174, 96, 0); } }
    </style>
</head>
<body>
    <div class="app-container">
        <h1>ColectoraGps Pro</h1>

        <div class="whatsapp-banner">
            <p style="margin: 0 0 8px 0; font-size: 0.95rem; color: #1e8449;"><strong>Servicios de Procesamiento Diferencial (GpsJ)</strong></p>
            <p style="margin: 0; line-height: 1.4;">Uso libre. Para post-procesamiento geodésico avanzado acoplado en la nube con el Motor GpsJ, contácteme.</p>
            <a href="https://wa.me/584121043327" target="_blank" class="whatsapp-btn">💬 Contactar por WhatsApp</a>
        </div>
        
        <div class="input-group">
            <label>Identificador del Punto / Trayectoria:</label>
            <input type="text" id="puntoName" placeholder="Ejemplo: R-1, Canal-Sur..." autocomplete="off">
        </div>

        <div class="input-group">
            <label>Modo de Medición:</label>
            <select id="modoMedicion" style="background-color: #f4f6f7; border-color: #bdc3c7;">
                <option value="estatico" selected>Estático (Filtro Espacial Activado)</option>
                <option value="cinematico">Cinemático (Rastreo Libre sin Filtro)</option>
            </select>
        </div>

        <div id="mainTimer" class="main-timer">00:00</div>
        <div id="statusBadge" class="status-badge">ESPERANDO INICIO...</div>

        <div id="panelPromedio" class="panel-promedio">
            <h3 id="tituloPromedio">📍 PROMEDIO AUTÓNOMO (UTM)</h3>
            <div class="data-row"><span class="label">Norte (Y):</span> <span id="promN" class="prom-val">---</span></div>
            <div class="data-row"><span class="label">Este (X):</span> <span id="promE" class="prom-val">---</span></div>
            <div class="data-row"><span class="label">Cota (Z):</span> <span id="promZ" class="prom-val">---</span></div>
            <div class="data-row"><span class="label">Huso/Hem:</span> <span id="promHuso" class="prom-val" style="color:#333;">---</span></div>
            <div class="data-row"><span class="label" style="color:var(--accent);">Dispersión (RMS):</span> <span id="promAcc" class="prom-val" style="color:var(--accent);">---</span></div>
        </div>

        <div class="data-panel">
            <div class="data-row"><span class="label" style="color:#2980b9;">Norte (Y) Vivo:</span> <span id="valNorte" class="value" style="color:#2980b9;">---</span></div>
            <div class="data-row"><span class="label" style="color:#2980b9;">Este (X) Vivo:</span> <span id="valEste" class="value" style="color:#2980b9;">---</span></div>
            <div class="data-row"><span class="label">Cota (Z):</span> <span id="valEle" class="value">--- m</span></div>
            <div class="data-row"><span class="label">Precisión HDOP:</span> <span id="valAcc" class="value">---</span></div>
            <div class="data-row"><span class="label">Épocas Grabadas:</span> <span id="valPts" class="value" style="color:var(--active); font-weight:bold;">0</span></div>
            <div class="data-row"><span class="label" style="color:var(--accent);">Épocas Rechazadas:</span> <span id="valRechazados" class="value" style="color:var(--accent); font-weight:bold;">0</span></div>
        </div>

        <button id="btnToggle" onclick="toggleRecording()">INICIAR LEVANTAMIENTO</button>
        
        <div id="actionButtons" class="action-buttons">
            <button id="btnExport" class="btn-half" onclick="exportGPX(false)">💾 GPX PARA NUBE</button>
            <button id="btnShare" class="btn-half" onclick="exportGPX(true)">📲 COMPARTIR GPX</button>
        </div>
        <button id="btnDiscard" onclick="descartar()">🗑️ DESCARTAR MEDICIÓN ACTUAL</button>

        <div id="panelLibreta" class="panel-libreta">
            <div class="data-row"><span class="label" style="color:#2980b9;">Puntos en Libreta:</span> <span id="valMemoria" class="value" style="font-weight:bold;">0</span></div>
            
            <div style="display: flex; gap: 10px; margin-top: 15px;">
                <button onclick="descargarExcel()" style="margin:0; background: #27ae60; font-size:0.85rem;">📊 CSV (EXCEL)</button>
                <button onclick="descargarDXF()" style="margin:0; background: #8e44ad; color: white; font-size:0.85rem;">📐 DXF (CAD)</button>
            </div>
            <button onclick="vaciarLibreta()" style="background: #e74c3c; margin-top: 10px; font-size:0.85rem;">🗑️ VACIAR LIBRETA</button>
        </div>

        <div id="log">Sistema Web listo. Asigne un nombre al punto y presione Iniciar.</div>
    </div>

    <script>
        let watchId = null;
        let loopInterval = null; // CORRECCIÓN AUDITORÍA: Bucle activo de interrogación a 1Hz
        let isRecording = false;
        let trackpoints = [];
        let currentPuntoName = "Punto_GPS";
        let puntosAlmacenados = [];
        let timerInterval = null;
        let timeSeconds = 0;
        let rejectedCount = 0;
        let wakeLock = null;
        
        // Memoria caché del último punto vivo entregado por el hardware
        let cacheUltimaPosicion = null;

        const btnToggle = document.getElementById('btnToggle');
        const actionButtons = document.getElementById('actionButtons');
        const btnDiscard = document.getElementById('btnDiscard');
        const statusBadge = document.getElementById('statusBadge');
        const mainTimer = document.getElementById('mainTimer');
        const logPanel = document.getElementById('log');
        const inputName = document.getElementById('puntoName');
        const modoMedicion = document.getElementById('modoMedicion');
        const panelPromedio = document.getElementById('panelPromedio');
        const panelLibreta = document.getElementById('panelLibreta');
        const tituloPromedio = document.getElementById('tituloPromedio');

        function log(msg) {
            logPanel.innerHTML += `\n> ${msg}`;
            logPanel.scrollTop = logPanel.scrollHeight;
        }

        async function activarWakeLock() {
            try {
                if ('wakeLock' in navigator) {
                    wakeLock = await navigator.wakeLock.request('screen');
                    log("WakeLock Activo: Pantalla fijada contra suspensiones.");
                    document.addEventListener('visibilitychange', async () => {
                        if (wakeLock !== null && document.visibilityState === 'visible') {
                            wakeLock = await navigator.wakeLock.request('screen');
                        }
                    });
                }
            } catch (err) { console.log("WakeLock falló pasivamente."); }
        }

        function desactivarWakeLock() {
            if (wakeLock !== null) {
                wakeLock.release().then(() => { wakeLock = null; });
            }
        }

        function latLonToUTM(lat, lon) {
            const a = 6378137.0;
            const eccSquared = 0.00669438;
            const k0 = 0.9996;
            const zone = Math.floor((lon + 180) / 6) + 1;
            const lonOrigin = (zone - 1) * 6 - 180 + 3;
            const lonOriginRad = lonOrigin * Math.PI / 180.0;
            const latRad = lat * Math.PI / 180.0;
            const lonRad = lon * Math.PI / 180.0;
            const eccPrimeSquared = eccSquared / (1 - eccSquared);
            const N = a / Math.sqrt(1 - eccSquared * Math.sin(latRad) * Math.sin(latRad));
            const T = Math.tan(latRad) * Math.tan(latRad);
            const C = eccPrimeSquared * Math.cos(latRad) * Math.cos(latRad);
            const A = Math.cos(latRad) * (lonRad - lonOriginRad);
            const M = a * ((1 - eccSquared / 4 - 3 * eccSquared * eccSquared / 64 - 5 * Math.pow(eccSquared, 3) / 256) * latRad
                - (3 * eccSquared / 8 + 3 * eccSquared * eccSquared / 32 + 45 * Math.pow(eccSquared, 3) / 1024) * Math.sin(2 * latRad)
                + (15 * eccSquared * eccSquared / 256 + 45 * Math.pow(eccSquared, 3) / 1024) * Math.sin(4 * latRad)
                - (35 * Math.pow(eccSquared, 3) / 3072) * Math.sin(6 * latRad));
            const UTMEasting = (k0 * N * (A + (1 - T + C) * Math.pow(A, 3) / 6 + (5 - 18 * T + T * T + 72 * C - 58 * eccPrimeSquared) * Math.pow(A, 5) / 120) + 500000.0);
            let UTMNorthing = (k0 * (M + N * Math.tan(latRad) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * Math.pow(A, 4) / 24 + (61 - 58 * T + T * T + 600 * C - 330 * eccPrimeSquared) * Math.pow(A, 6) / 720)));
            if (lat < 0) UTMNorthing += 10000000.0; 
            return { e: UTMEasting, n: UTMNorthing, zone: zone, hemi: lat >= 0 ? 'N' : 'S' };
        }

        function getMedian(arr) {
            const sorted = [...arr].sort((a, b) => a - b);
            const half = Math.floor(sorted.length / 2);
            return sorted.length % 2 ? sorted[half] : (sorted[half - 1] + sorted[half]) / 2.0;
        }

        // Filtro MAD Estático
        function filterMAD(values) {
            if (values.length === 0) return [];
            const median = getMedian(values);
            const devs = values.map(v => Math.abs(v - median));
            let mad = getMedian(devs);
            if (mad < 0.000001) mad = 0.000001; 
            return values.filter(v => Math.abs(v - median) <= 6 * mad);
        }

        function calcularPromedioRobusto() {
            if (trackpoints.length === 0) return;

            let modo = modoMedicion.value;
            
            // CORRECCIÓN AUDITORÍA: El cálculo del promedio se ejecuta sobre coordenadas planas UTM reales,
            // no sobre aproximaciones de grados esféricos.
            let utm_e_vals = trackpoints.map(p => { let u = latLonToUTM(parseFloat(p.lat), parseFloat(p.lon)); return u.e; });
            let utm_n_vals = trackpoints.map(p => { let u = latLonToUTM(parseFloat(p.lat), parseFloat(p.lon)); return u.n; });
            let eles = trackpoints.map(p => parseFloat(p.ele));

            let fE = utm_e_vals;
            let fN = utm_n_vals;
            let fZ = eles;

            if (modo === 'estatico') {
                fE = filterMAD(utm_e_vals);
                fN = filterMAD(utm_n_vals);
                fZ = filterMAD(eles);
                
                if(fE.length === 0) fE = utm_e_vals;
                if(fN.length === 0) fN = utm_n_vals;
                if(fZ.length === 0) fZ = eles;
                
                tituloPromedio.innerText = "📍 PROMEDIO AUTÓNOMO (ESTÁTICO)";
            } else {
                tituloPromedio.innerText = "📍 CENTROIDE DE TRAYECTORIA (CINEMÁTICO)";
            }

            let finalE = fE.reduce((a, b) => a + b, 0) / fE.length;
            let finalN = fN.reduce((a, b) => a + b, 0) / fN.length;
            let finalZ = fZ.reduce((a, b) => a + b, 0) / fZ.length;

            // Extraer Huso de la primera época útil
            let muestraUTM = latLonToUTM(parseFloat(trackpoints[0].lat), parseFloat(trackpoints[0].lon));

            // Calcular Desviación Estándar (RMS) Plana Real
            let sumSq = 0;
            for(let i=0; i<utm_e_vals.length; i++) {
                let dE = utm_e_vals[i] - finalE;
                let dN = utm_n_vals[i] - finalN;
                sumSq += (dE*dE + dN*dN);
            }
            let rms = Math.sqrt(sumSq / trackpoints.length);

            panelPromedio.style.display = 'block';
            document.getElementById('promN').innerText = finalN.toFixed(3);
            document.getElementById('promE').innerText = finalE.toFixed(3);
            document.getElementById('promZ').innerText = finalZ.toFixed(3) + " m";
            document.getElementById('promHuso').innerText = muestraUTM.zone + " " + muestraUTM.hemi;
            document.getElementById('promAcc').innerText = "± " + rms.toFixed(2) + " m";

            puntosAlmacenados.push({
                nombre: currentPuntoName,
                norte: finalN.toFixed(3),
                este: finalE.toFixed(3),
                cota: finalZ.toFixed(3),
                huso: muestraUTM.zone + muestraUTM.hemi,
                rms: rms.toFixed(3),
                epocas: trackpoints.length
            });
            
            document.getElementById('valMemoria').innerText = puntosAlmacenados.length;
            panelLibreta.style.display = 'block';
        }

        function toggleRecording() {
            if (!isRecording) {
                if (!navigator.geolocation) { alert("Error de hardware."); return; }
                
                let nameVal = inputName.value.trim();
                if(!nameVal) { alert("Asigne un nombre."); inputName.focus(); return; }
                currentPuntoName = nameVal;

                trackpoints = [];
                timeSeconds = 0;
                rejectedCount = 0;
                cacheUltimaPosicion = null;
                
                document.getElementById('valPts').innerText = "0";
                document.getElementById('valRechazados').innerText = "0";
                mainTimer.innerText = "00:00";
                
                actionButtons.style.display = 'none';
                btnDiscard.style.display = 'none';
                inputName.disabled = true; 
                modoMedicion.disabled = true; 
                
                activarWakeLock();
                
                // Reloj de Cronómetro General
                timerInterval = setInterval(() => {
                    timeSeconds++;
                    let m = Math.floor(timeSeconds / 60).toString().padStart(2, '0');
                    let s = (timeSeconds % 60).toString().padStart(2, '0');
                    mainTimer.innerText = `${m}:${s}`;
                }, 1000);
                
                // Inicializar canal pasivo de actualización de hardware
                const options = { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 };
                watchId = navigator.geolocation.watchPosition((pos) => { cacheUltimaPosicion = pos; }, (err) => { log(`Err Hardware: ${err.message}`); }, options);
                
                // CORRECCIÓN DE AUDITORÍA: Bucle activo de inyección forzada a 1Hz exacto. 
                // Elimina la latencia estática del chip.
                loopInterval = setInterval(() => {
                    if (cacheUltimaPosicion !== null) {
                        procesarNodoTemporal(cacheUltimaPosicion);
                    }
                }, 1000);
                
                isRecording = true;
                btnToggle.innerText = "DETENER LEVANTAMIENTO";
                btnToggle.classList.add("recording");
                
                statusBadge.innerText = `ENGANCHANDO CONSTELACIÓN...`;
                statusBadge.classList.add("status-recording");
                statusBadge.style.background = "#f39c12"; 
                statusBadge.style.color = "white";

            } else {
                navigator.geolocation.clearWatch(watchId);
                clearInterval(timerInterval);
                clearInterval(loopInterval); // Apagar bucle activo de 1Hz
                isRecording = false;
                
                desactivarWakeLock();
                
                btnToggle.innerText = "NUEVO LEVANTAMIENTO";
                btnToggle.classList.remove("recording");
                statusBadge.innerText = "LEVANTAMIENTO DETENIDO";
                statusBadge.classList.remove("status-recording");
                statusBadge.style.background = "#ddd";
                statusBadge.style.color = "#555";
                
                inputName.disabled = false;
                modoMedicion.disabled = false;
                inputName.value = ''; 
                
                if(trackpoints.length > 0) {
                    calcularPromedioRobusto();
                    actionButtons.style.display = 'flex';
                    btnDiscard.style.display = 'block';
                }
            }
        }

        // Función del motor de 1Hz que extrae los datos de la caché sin latencia estática
        function procesarNodoTemporal(position) {
            const coords = position.coords;
            const lat = coords.latitude;
            const lon = coords.longitude;
            const ele = coords.altitude ? coords.altitude.toFixed(3) : "0.000";
            const accuracy = coords.accuracy; 
            const hdop = (accuracy / 4.0).toFixed(2); 
            const timeIso = new Date(position.timestamp).toISOString();

            const utmVivo = latLonToUTM(lat, lon);
            document.getElementById('valNorte').innerText = utmVivo.n.toFixed(3);
            document.getElementById('valEste').innerText = utmVivo.e.toFixed(3);
            document.getElementById('valEle').innerText = ele;
            document.getElementById('valAcc').innerText = `±${accuracy.toFixed(1)}m (HDOP: ${hdop})`;

            if(parseFloat(hdop) > 4.0) {
                rejectedCount++;
                document.getElementById('valRechazados').innerText = rejectedCount;
                statusBadge.innerText = `🔴 HDOP RECHAZABLE: ${hdop}`;
                statusBadge.style.background = "#e74c3c";
                return; 
            }

            statusBadge.innerText = `🟢 ADQUISICIÓN ESTABLE (HDOP: ${hdop})`;
            statusBadge.style.background = "#27ae60";

            // Inyectar a la matriz de almacenamiento temporal
            trackpoints.push({ lat: lat.toFixed(8), lon: lon.toFixed(8), ele, timeIso, hdop });
            document.getElementById('valPts').innerText = trackpoints.length;
        }

        function descartar() {
            if(confirm(`¿Descartar levantamiento?`)) {
                trackpoints = [];
                timeSeconds = 0;
                rejectedCount = 0;
                mainTimer.innerText = "00:00";
                document.getElementById('valPts').innerText = "0";
                document.getElementById('valRechazados').innerText = "0";
                actionButtons.style.display = 'none';
                btnDiscard.style.display = 'none';
                
                if(puntosAlmacenados.length > 0) {
                    puntosAlmacenados.pop();
                    document.getElementById('valMemoria').innerText = puntosAlmacenados.length;
                    if(puntosAlmacenados.length === 0) panelLibreta.style.display = 'none';
                }
            }
        }

        function descargarExcel() {
            if(puntosAlmacenados.length === 0) return;
            let csvData = "Identificador,Norte (Y),Este (X),Cota (Z),Huso,Precision_RMS(m),Epocas_Grabadas\n";
            puntosAlmacenados.forEach(pt => {
                csvData += `${pt.nombre},${pt.norte},${pt.este},${pt.cota},${pt.huso},${pt.rms},${pt.epocas}\n`;
            });
            const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Libreta_Pro_${new Date().getTime()}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }

        function descargarDXF() {
            if(puntosAlmacenados.length === 0) return;
            let dxf = "  0\r\nSECTION\r\n  2\r\nHEADER\r\n  9\r\n$ACADVER\r\n  1\r\nAC1009\r\n  0\r\nENDSEC\r\n";
            dxf += "  0\r\nSECTION\r\n  2\r\nTABLES\r\n  0\r\nENDSEC\r\n";
            dxf += "  0\r\nSECTION\r\n  2\r\nBLOCKS\r\n  0\r\nENDSEC\r\n";
            dxf += "  0\r\nSECTION\r\n  2\r\nENTITIES\r\n";

            puntosAlmacenados.forEach(pt => {
                dxf += "  0\r\nPOINT\r\n  8\r\nPuntos\r\n 10\r\n" + pt.este + "\r\n 20\r\n" + pt.norte + "\r\n 30\r\n" + pt.cota + "\r\n";
                dxf += "  0\r\nTEXT\r\n  8\r\nEtiquetas\r\n 10\r\n" + (parseFloat(pt.este) + 0.5).toFixed(3) + "\r\n 20\r\n" + (parseFloat(pt.norte) + 0.5).toFixed(3) + "\r\n 30\r\n" + pt.cota + "\r\n 40\r\n1.0\r\n  1\r\n" + pt.nombre + "\r\n";
            });

            if(puntosAlmacenados.length > 1) {
                dxf += "  0\r\nPOLYLINE\r\n  8\r\nPoligono\r\n 66\r\n1\r\n 10\r\n0.0\r\n 20\r\n0.0\r\n 30\r\n0.0\r\n 70\r\n8\r\n";
                puntosAlmacenados.forEach(pt => {
                    dxf += "  0\r\nVERTEX\r\n  8\r\nPoligono\r\n 10\r\n" + pt.este + "\r\n 20\r\n" + pt.norte + "\r\n 30\r\n" + pt.cota + "\r\n";
                });
                dxf += "  0\r\nSEQEND\r\n  8\r\nPoligono\r\n";
            }
            dxf += "  0\r\nENDSEC\r\n  0\r\nEOF\r\n";

            const blob = new Blob([dxf], { type: 'application/octet-stream' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Plano_Pro_${new Date().getTime()}.dxf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }

        function vaciarLibreta() {
            if(confirm("¿Vaciar libreta?")) {
                puntosAlmacenados = [];
                document.getElementById('valMemoria').innerText = "0";
                panelLibreta.style.display = 'none';
                panelPromedio.style.display = 'none';
            }
        }

        function generarGPXString() {
            let gpx = `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="ColectoraGps Web v4.2" xmlns="http://www.topografix.com/GPX/1/1">\n<metadata><name>${currentPuntoName}</name><time>${trackpoints[0].timeIso}</time></metadata>\n<trk><name>${currentPuntoName}</name><trkseg>\n`;
            trackpoints.forEach(pt => {
                gpx += `  <trkpt lat="${pt.lat}" lon="${pt.lon}">\n    <ele>${pt.ele}</ele><time>${pt.timeIso}</time><hdop>${pt.hdop}</hdop>\n  </trkpt>\n`;
            });
            gpx += `</trkseg></trk>\n</gpx>`;
            return gpx;
        }

        async function exportGPX(share) {
            if (trackpoints.length === 0) return;
            const gpxString = generarGPXString();
            const fileName = `${currentPuntoName}.gpx`;
            const file = new File([gpxString], fileName, { type: "application/gpx+xml" });

            if (share && navigator.share) {
                try { await navigator.share({ title: fileName, files: [file] }); } catch (e) {}
            } else {
                const link = document.createElement("a");
                link.href = URL.createObjectURL(file);
                link.download = fileName;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
        }
    </script>
</body>
</html>
