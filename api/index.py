        // FUNCIÓN DEFINITIVA: ENVIAR DATOS AL BACKEND DE VERCEL
        btnCalcular.addEventListener('click', async () => {
            const base = document.getElementById('fileBase').files[0];
            const rovers = document.getElementById('fileRovers').files;

            if (!base || rovers.length === 0) { alert("Cargue la Base y al menos un Rover."); return; }
            if (!document.getElementById('baseZ').value) { alert("Debe ingresar la Cota (Z) de la Base Oficial."); return; }

            terminal.innerHTML = "[SISTEMA] Conectando con el Servidor Cloud GpsN...\n";
            terminal.innerHTML += "[AUDITORÍA] Verificando sesión...\n";
            
            try {
                // Auditoría en Firestore
                const auditRef = doc(db, "auditoria_procesamiento", Date.now().toString());
                setDoc(auditRef, {
                    usuario: auth.currentUser.email,
                    fecha: serverTimestamp(),
                    accion: "Cálculo Solicitado"
                });
            } catch(e) {}
            
            terminal.innerHTML += "[PROCESANDO] Transfiriendo paquetes a la RAM de Vercel y ejecutando Filtros Kalman...\n";
            
            const fd = new FormData();
            fd.append('base', base);
            for(let r of rovers) fd.append('rovers', r);
            fd.append('baseE', document.getElementById('baseE').value);
            fd.append('baseN', document.getElementById('baseN').value);
            fd.append('baseZ', document.getElementById('baseZ').value);
            fd.append('alturaBase', document.getElementById('alturaBase').value);
            fd.append('alturaRover', document.getElementById('alturaRover').value);
            fd.append('huso', document.getElementById('huso').value);

            try {
                // LLAMADA AL API DE VERCEL (NUBE) - ¡Esta es la magia!
                const resp = await fetch('/api/procesar', { method:'POST', body:fd });
                const data = await resp.json();

                if (data.error) { terminal.innerHTML += `\n[ERROR CLOUD] ${data.error}`; } 
                else {
                    terminal.innerHTML = "";
                    data.resultados.forEach(r => {
                        terminal.innerHTML += `>> PUNTO: ${r.roverName} (Base: ${r.baseName})\n`;
                        terminal.innerHTML += `Status: ${r.csv.qaStr}\n`;
                        terminal.innerHTML += `Puntos Sincronizados: ${r.puntos} | DOP Medio: ${r.csv.dop}\n`;
                        terminal.innerHTML += `Línea Base (Distancia a Base): ${r.csv.distBase}m\n`;
                        terminal.innerHTML += `ERROR TOTAL BASE (SESIÓN) -> E:${r.csv.totalErrE}m | N:${r.csv.totalErrN}m | Z:${r.csv.totalErrZ}m\n`;
                        terminal.innerHTML += `ERROR BASE (VENTANA)      -> E:${r.csv.winErrE}m | N:${r.csv.winErrN}m | Z:${r.csv.winErrZ}m\n`;
                        terminal.innerHTML += `RUIDO BASE (RMS)          -> E:±${r.csv.rmsE}m | N:±${r.csv.rmsN}m | Z:±${r.csv.rmsZ}m\n`;
                        terminal.innerHTML += `COORD. FINAL (KALMAN)     -> E:${r.csv.e} | N:${r.csv.n} | Z:${r.csv.z}\n`;
                        terminal.innerHTML += `--------------------------------------------------\n`;
                    });
                }
            } catch (e) { terminal.innerHTML += "\n[ERROR] El servidor en la nube no responde."; }
        });

