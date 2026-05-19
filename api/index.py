from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
from pyproj import Proj
import math

app = Flask(__name__)
CORS(app)

# Aproximación ligera de EGM96 (Corrección Geoidal)
def obtener_separacion_geoidal(lat, lon):
    # Modelo simplificado: Corrección sin carga de archivos pesados
    # Basado en la fórmula de gravedad normalizada (aproximación)
    return 30.0 * np.sin(np.radians(lat)) * np.cos(np.radians(lon))

def resamplear_a_1hz(t, e, n, z, hdop, t_min, t_max):
    # Crea rejilla de tiempo exacta a 1Hz
    tiempos_fijos = np.arange(math.ceil(t_min), math.floor(t_max) + 1)
    e_res, n_res, z_res, h_res = [], [], [], []
    
    for t_ref in tiempos_fijos:
        idx = np.abs(t - t_ref).argmin()
        if np.abs(t[idx] - t_ref) <= 0.5: # Ventana de tolerancia 0.5s
            e_res.append(e[idx])
            n_res.append(n[idx])
            z_res.append(z[idx])
            h_res.append(hdop[idx])
        else:
            e_res.append(np.nan)
            n_res.append(np.nan)
            z_res.append(np.nan)
            h_res.append(np.nan)
    return np.array(tiempos_fijos), np.array(e_res), np.array(n_res), np.array(z_res), np.array(h_res)

def procesar_gpx_crudo(file_stream, huso):
    gpx = gpxpy.parse(file_stream)
    t_list, lats, lons, eles, hdops = [], [], [], [], []
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.elevation is not None:
                    lats.append(pt.latitude)
                    lons.append(pt.longitude)
                    eles.append(pt.elevation)
                    hdops.append(pt.horizontal_dilution if pt.horizontal_dilution is not None else 1.0)
                    t_list.append(pt.time.timestamp())
    
    if not t_list: return None, None, None, None, None
    myProj = Proj(f"+proj=utm +zone={huso} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")
    estes, nortes = myProj(np.array(lons), np.array(lats))
    return np.array(t_list), estes, nortes, np.array(eles), np.array(hdops), np.array(lats), np.array(lons)

@app.route('/api/procesar', methods=['POST'])
def procesar():
    try:
        base_file = request.files['base']
        rover_files = request.files.getlist('rovers')
        huso = int(request.form.get('huso', 19))
        baseE_of = float(request.form.get('baseE', 0))
        baseN_of = float(request.form.get('baseN', 0))
        baseZ_of = float(request.form.get('baseZ', 0))
        h_base = float(request.form.get('alturaBase', 0))
        h_rover = float(request.form.get('alturaRover', 0))

        # Procesar Base
        tB, eB, nB, zB, _, latB, lonB = procesar_gpx_crudo(base_file, huso)
        tB, eB, nB, zB, _ = resamplear_a_1hz(tB, eB, nB, zB, np.ones_like(tB), tB[0], tB[-1])
        
        # Calcular corrección geoidal promedio desde la base
        N_geo = np.mean(zB - obtener_separacion_geoidal(latB, lonB)) - baseZ_of
        
        resultados = []
        for rov in rover_files:
            tR, eR, nR, zR, hR, latR, lonR = procesar_gpx_crudo(rov, huso)
            
            # Intersección de tiempos
            t_start = max(tB[0], tR[0])
            t_end = min(tB[-1], tR[-1])
            if t_start >= t_end: continue
            
            tB_v, eB_v, nB_v, zB_v, _ = resamplear_a_1hz(tB, eB, nB, zB, _, t_start, t_end)
            tR_v, eR_v, nR_v, zR_v, hR_v = resamplear_a_1hz(tR, eR, nR, zR, hR, t_start, t_end)
            
            # Filtro de sincronía: Solo usar donde ambos tengan datos
            mask = ~np.isnan(eB_v) & ~np.isnan(eR_v)
            if not np.any(mask): continue
            
            # Diferencial Simple (Rover - Base)
            e_diff = eR_v[mask] - (eB_v[mask] - baseE_of)
            n_diff = nR_v[mask] - (nB_v[mask] - baseN_of)
            z_diff = (zR_v[mask] - h_rover) - ((zB_v[mask] - h_base) - baseZ_of)
            
            resultados.append({
                "roverName": rov.filename,
                "csv": {
                    "e": round(np.mean(e_diff), 4),
                    "n": round(np.mean(n_diff), 4),
                    "z": round(np.mean(z_diff) - N_geo, 4), # Aplicación corrección global
                    "puntos": np.sum(mask)
                }
            })
        return jsonify({"resultados": resultados})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
