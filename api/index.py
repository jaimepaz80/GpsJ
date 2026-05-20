from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy, numpy as np
from pyproj import Proj
import math

app = Flask(__name__)
CORS(app)

# --- MANTEN AQUÍ TUS FUNCIONES DE FILTRO (KALMAN/IQR) ORIGINALES ---
# (Las que tenías en tu archivo original de 272 líneas)
# ... 

def procesar_gpx_crudo(file_stream, huso):
    gpx = gpxpy.parse(file_stream)
    t, lat, lon, ele, hdop = [], [], [], [], []
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.elevation is not None:
                    t.append(pt.time.timestamp()); lat.append(pt.latitude)
                    lon.append(pt.longitude); ele.append(pt.elevation)
                    hdop.append(pt.horizontal_dilution or 1.0)
    myProj = Proj(f"+proj=utm +zone={huso} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")
    e, n = myProj(np.array(lon), np.array(lat))
    return np.array(t), e, n, np.array(ele), np.array(hdop)

@app.route('/api/procesar', methods=['POST'])
def procesar():
    # INICIALIZACIÓN OBLIGATORIA
    resultados = []
    try:
        if 'base' not in request.files:
            return jsonify({"error": "No se recibió archivo base"}), 400

        # Captura de parámetros
        h_base = float(request.form.get('alturaBase', 0))
        h_rover = float(request.form.get('alturaRover', 0))
        bE = float(request.form.get('baseE', 0))
        bN = float(request.form.get('baseN', 0))
        bZ = float(request.form.get('baseZ', 0))
        huso = int(request.form.get('huso', 19))

        tB, eB, nB, zB, _ = procesar_gpx_crudo(request.files['base'], huso)
        
        for rov in request.files.getlist('rovers'):
            tR, eR, nR, zR, hR = procesar_gpx_crudo(rov, huso)
            
            # Sincronización temporal (Reloj Maestro)
            t_start, t_end = max(tB[0], tR[0]), min(tB[-1], tR[-1])
            if t_start >= t_end: continue
            
            # Resampleo a 1Hz fijo dentro de la ventana común
            tiempos_comunes = np.arange(math.ceil(t_start), math.floor(t_end) + 1)
            eB_s, nB_s, zB_s = [], [], []
            eR_s, nR_s, zR_s = [], [], []
            
            for t_ref in tiempos_comunes:
                idxB = np.abs(tB - t_ref).argmin()
                idxR = np.abs(tR - t_ref).argmin()
                if np.abs(tB[idxB] - t_ref) <= 0.5 and np.abs(tR[idxR] - t_ref) <= 0.5:
                    eB_s.append(eB[idxB]); nB_s.append(nB[idxB]); zB_s.append(zB[idxB])
                    eR_s.append(eR[idxR]); nR_s.append(nR[idxR]); zR_s.append(zR[idxR])
            
            if len(eB_s) < 10: continue
            
            # Diferencial con alturas de bastón
            e_diff = np.array(eR_s) - (np.array(eB_s) - bE)
            n_diff = np.array(nR_s) - (np.array(nB_s) - bN)
            z_diff = (np.array(zR_s) - h_rover) - ((np.array(zB_s) - h_base) - bZ)
            
            resultados.append({
                "roverName": rov.filename,
                "e": round(float(np.mean(e_diff)), 4),
                "n": round(float(np.mean(n_diff)), 4),
                "z": round(float(np.mean(z_diff)), 4),
                "puntos": len(eB_s)
            })
            
        return jsonify({"resultados": resultados})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
