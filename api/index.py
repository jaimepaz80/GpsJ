from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
from pyproj import Proj
import math

app = Flask(__name__)
CORS(app)

def resamplear_a_1hz(t, e, n, z, t_min, t_max):
    tiempos_fijos = np.arange(math.ceil(t_min), math.floor(t_max) + 1)
    e_res, n_res, z_res = [], [], []
    for t_ref in tiempos_fijos:
        idx = np.abs(t - t_ref).argmin()
        if np.abs(t[idx] - t_ref) <= 0.5:
            e_res.append(e[idx]); n_res.append(n[idx]); z_res.append(z[idx])
        else:
            e_res.append(np.nan); n_res.append(np.nan); z_res.append(np.nan)
    return np.array(tiempos_fijos), np.array(e_res), np.array(n_res), np.array(z_res)

def procesar_gpx_crudo(file_stream, huso):
    gpx = gpxpy.parse(file_stream)
    t_list, lats, lons, eles = [], [], [], []
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.elevation is not None:
                    t_list.append(pt.time.timestamp())
                    lats.append(pt.latitude); lons.append(pt.longitude); eles.append(pt.elevation)
    myProj = Proj(f"+proj=utm +zone={huso} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")
    estes, nortes = myProj(np.array(lons), np.array(lats))
    return np.array(t_list), estes, nortes, np.array(eles)

@app.route('/api/procesar', methods=['POST'])
def procesar():
    try:
        # Validación inicial
        if 'base' not in request.files: return jsonify({"error": "Falta archivo base"}), 400
        
        # Procesamiento
        tB, eB, nB, zB = procesar_gpx_crudo(request.files['base'], int(request.form.get('huso', 19)))
        tB, eB, nB, zB = resamplear_a_1hz(tB, eB, nB, zB, tB[0], tB[-1])
        
        resultados = []
        for rov in request.files.getlist('rovers'):
            tR, eR, nR, zR = procesar_gpx_crudo(rov, int(request.form.get('huso', 19)))
            t_start, t_end = max(tB[0], tR[0]), min(tB[-1], tR[-1])
            
            if t_start >= t_end:
                return jsonify({"error": f"Sin solapamiento temporal en {rov.filename}"}), 400
                
            tB_v, eB_v, nB_v, zB_v = resamplear_a_1hz(tB, eB, nB, zB, t_start, t_end)
            tR_v, eR_v, nR_v, zR_v = resamplear_a_1hz(tR, eR, nR, zR, t_start, t_end)
            
            mask = ~np.isnan(eB_v) & ~np.isnan(eR_v)
            if np.sum(mask) < 10:
                return jsonify({"error": f"Puntos insuficientes en {rov.filename}. Verifique sincronía."}), 400
            
            # Cálculo
            e_diff = eR_v[mask] - (eB_v[mask] - float(request.form.get('baseE', 0)))
            n_diff = nR_v[mask] - (nB_v[mask] - float(request.form.get('baseN', 0)))
            z_diff = (zR_v[mask] - float(request.form.get('alturaRover', 0))) - ((zB_v[mask] - float(request.form.get('alturaBase', 0))) - float(request.form.get('baseZ', 0)))
            
            resultados.append({
                "rover": rov.filename,
                "e": round(np.mean(e_diff), 4), "n": round(np.mean(n_diff), 4), "z": round(np.mean(z_diff), 4),
                "puntos": int(np.sum(mask)), "status": "ÉXITO"
            })
        return jsonify({"resultados": resultados})
    except Exception as e:
        return jsonify({"error": f"Fallo en Motor Geodésico: {str(e)}"}), 500
