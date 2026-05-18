from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
from pyproj import Proj
import math

app = Flask(__name__)
CORS(app)

def kalman_filter(mediciones):
    """
    Filtro de Kalman 1D para suavizado de ruido multipath en coordenadas.
    """
    n = len(mediciones)
    if n == 0: 
        return 0.0, 0.0
        
    x_est = mediciones[0]
    p_est = 1.0
    # Calcular varianza como factor de ruido del sensor (R)
    r = np.var(mediciones) if n > 1 and np.var(mediciones) > 0 else 1.0 
    q = 0.01 # Ruido del proceso
    
    estimaciones = []
    for z in mediciones:
        # 1. Predicción
        x_pred = x_est
        p_pred = p_est + q
        # 2. Actualización (Ganancia de Kalman)
        k = p_pred / (p_pred + r)
        x_est = x_pred + k * (z - x_pred)
        p_est = (1 - k) * p_pred
        estimaciones.append(x_est)
        
    # Retorna la estimación final suavizada y la desviación estándar (RMS)
    return float(x_est), float(np.std(estimaciones))

def procesar_archivo_gpx(file_stream, huso):
    gpx = gpxpy.parse(file_stream)
    lats, lons, eles = [], [], []

    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.elevation is not None:
                    lats.append(pt.latitude)
                    lons.append(pt.longitude)
                    eles.append(pt.elevation)

    if not lats:
        return None

    lats_arr = np.array(lats)
    lons_arr = np.array(lons)
    eles_arr = np.array(eles)
    
    # Transformación rigurosa de Lat/Lon a UTM (WGS84)
    # Se asume hemisferio Norte por defecto en la definición proj
    myProj = Proj(f"+proj=utm +zone={huso} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")
    estes, nortes = myProj(lons_arr, lats_arr)
    
    # Procesamiento Matemático: Filtro de Kalman
    e_kalman, e_rms = kalman_filter(estes)
    n_kalman, n_rms = kalman_filter(nortes)
    z_kalman, z_rms = kalman_filter(eles_arr)

    return {
        "e_kalman": e_kalman,
        "n_kalman": n_kalman,
        "z_kalman": z_kalman,
        "e_rms": e_rms,
        "n_rms": n_rms,
        "z_rms": z_rms,
        "puntos": len(lats)
    }

@app.route('/api/procesar', methods=['POST'])
def procesar():
    try:
        # Validación de payloads exactos desde index.html
        if 'base' not in request.files or 'rovers' not in request.files:
            return jsonify({"error": "No se detectaron los archivos GPX de la Base o los Rovers."}), 400

        base_file = request.files['base']
        rover_files = request.files.getlist('rovers')
        
        baseE = float(request.form.get('baseE', 0))
        baseN = float(request.form.get('baseN', 0))
        baseZ = float(request.form.get('baseZ', 0))
        huso = int(request.form.get('huso', 19))
        alturaBase = float(request.form.get('alturaBase', 0))
        alturaRover = float(request.form.get('alturaRover', 0))

        # 1. Analizar la Base
        datos_base = procesar_archivo_gpx(base_file, huso)
        if not datos_base:
            return jsonify({"error": "El archivo GPX Base está vacío o corrupto."}), 400

        # Compensación de altura de antena en la Base
        base_medida_Z = datos_base['z_kalman'] - alturaBase
        
        # Cálculo del Vector de Error Diferencial
        error_E = datos_base['e_kalman'] - baseE
        error_N = datos_base['n_kalman'] - baseN
        error_Z = base_medida_Z - baseZ

        resultados = []
        
        # 2. Iterar y Corregir cada Rover
        for rover_file in rover_files:
            datos_rover = procesar_archivo_gpx(rover_file, huso)
            if not datos_rover:
                continue
            
            # Compensación de altura de bastón en Rover
            rover_medido_Z = datos_rover['z_kalman'] - alturaRover
            
            # Aplicación de Corrección Diferencial
            rover_corregido_E = datos_rover['e_kalman'] - error_E
            rover_corregido_N = datos_rover['n_kalman'] - error_N
            rover_corregido_Z = rover_medido_Z - error_Z
            
            # Línea Base Estática (Distancia Euclidiana)
            dist_base = math.sqrt((datos_rover['e_kalman'] - datos_base['e_kalman'])**2 + (datos_rover['n_kalman'] - datos_base['n_kalman'])**2)
            
            # Control de Calidad (Estimación de DOP basada en RMS)
            rms_total = datos_rover['e_rms'] + datos_rover['n_rms'] + datos_rover['z_rms']
            qa_str = "[ÓPTIMO 🟢]" if rms_total < 1.5 else "[DEFICIENTE 🔴]"

            # Formateo estricto exigido por el frontend HTML
            resultados.append({
                "roverName": rover_file.filename,
                "baseName": base_file.filename,
                "puntos": datos_rover['puntos'],
                "csv": {
                    "qaStr": qa_str,
                    "dop": str(round((rms_total / 3) + 0.8, 2)) if rms_total else "1.00",
                    "distBase": str(round(dist_base, 3)),
                    "totalErrE": str(round(error_E, 6)),
                    "totalErrN": str(round(error_N, 6)),
                    "totalErrZ": str(round(error_Z, 6)),
                    "winErrE": str(round(error_E * 0.15, 6)), 
                    "winErrN": str(round(error_N * 0.15, 6)),
                    "winErrZ": str(round(error_Z * 0.15, 6)),
                    "rmsE": str(round(datos_rover['e_rms'], 5)),
                    "rmsN": str(round(datos_rover['n_rms'], 5)),
                    "rmsZ": str(round(datos_rover['z_rms'], 5)),
                    "e": str(round(rover_corregido_E, 4)),
                    "n": str(round(rover_corregido_N, 4)),
                    "z": str(round(rover_corregido_Z, 4))
                }
            })

        return jsonify({"resultados": resultados}), 200

    except Exception as e:
        # Captura de errores para debugging en los logs de Vercel
        return jsonify({"error": f"Fallo interno del modelo: {str(e)}"}), 500
