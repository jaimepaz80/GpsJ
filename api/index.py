from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
from pyproj import Proj
import math

app = Flask(__name__)
CORS(app)

def eliminar_valores_atipicos_iqr(t, x, y, z):
    """
    Filtro Estadístico Espacial (Rango Intercuartílico).
    Detecta y elimina puntos satelitales con errores por rebote severo (multipath).
    """
    if len(x) < 4: return t, x, y, z # Muy pocos puntos para estadística
    
    # Calcular límites IQR para los 3 ejes
    q1_x, q3_x = np.percentile(x, [25, 75]); iqr_x = q3_x - q1_x
    q1_y, q3_y = np.percentile(y, [25, 75]); iqr_y = q3_y - q1_y
    q1_z, q3_z = np.percentile(z, [25, 75]); iqr_z = q3_z - q1_z
    
    lim_inf_x, lim_sup_x = q1_x - 1.5 * iqr_x, q3_x + 1.5 * iqr_x
    lim_inf_y, lim_sup_y = q1_y - 1.5 * iqr_y, q3_y + 1.5 * iqr_y
    lim_inf_z, lim_sup_z = q1_z - 1.5 * iqr_z, q3_z + 1.5 * iqr_z
    
    # Máscara booleana para mantener solo puntos dentro de la tolerancia
    mask = (x >= lim_inf_x) & (x <= lim_sup_x) & \
           (y >= lim_inf_y) & (y <= lim_sup_y) & \
           (z >= lim_inf_z) & (z <= lim_sup_z)
           
    return t[mask], x[mask], y[mask], z[mask]

def kalman_filter(mediciones):
    """
    Filtro de Kalman 1D optimizado.
    """
    n = len(mediciones)
    if n == 0: return 0.0, 0.0
        
    x_est = mediciones[0]
    p_est = 1.0
    # Calcular varianza como factor de ruido del sensor (R) dinámico
    r = np.var(mediciones) if n > 1 and np.var(mediciones) > 0 else 1.0 
    q = 0.001 # Ruido de proceso ajustado (menor incertidumbre teórica)
    
    estimaciones = []
    for z in mediciones:
        x_pred, p_pred = x_est, p_est + q
        k = p_pred / (p_pred + r)
        x_est = x_pred + k * (z - x_pred)
        p_est = (1 - k) * p_pred
        estimaciones.append(x_est)
        
    return float(x_est), float(np.std(estimaciones))

def procesar_gpx_crudo(file_stream, huso):
    """
    Extrae la matriz temporal y espacial del archivo GPX y la proyecta a UTM.
    """
    gpx = gpxpy.parse(file_stream)
    t_list, lats, lons, eles = [], [], [], []

    idx = 0
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.elevation is not None:
                    lats.append(pt.latitude)
                    lons.append(pt.longitude)
                    eles.append(pt.elevation)
                    # Extraer tiempo exacto si existe, sino usar índice secuencial
                    t_list.append(pt.time.timestamp() if pt.time else float(idx))
                    idx += 1

    if not lats: return None, None, None, None

    # Proyección rigurosa UTM
    myProj = Proj(f"+proj=utm +zone={huso} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")
    estes, nortes = myProj(np.array(lons), np.array(lats))
    
    return np.array(t_list), estes, nortes, np.array(eles)

@app.route('/api/procesar', methods=['POST'])
def procesar():
    try:
        if 'base' not in request.files or 'rovers' not in request.files:
            return jsonify({"error": "No se detectaron archivos GPX."}), 400

        base_file = request.files['base']
        rover_files = request.files.getlist('rovers')
        
        baseE_oficial = float(request.form.get('baseE', 0))
        baseN_oficial = float(request.form.get('baseN', 0))
        baseZ_oficial = float(request.form.get('baseZ', 0))
        huso = int(request.form.get('huso', 19))
        alturaBase = float(request.form.get('alturaBase', 0))
        alturaRover = float(request.form.get('alturaRover', 0))

        # 1. PARSEAR LA BASE Y CALCULAR MATRIZ DE ERROR TEMPORAL
        t_base, e_base, n_base, z_base = procesar_gpx_crudo(base_file, huso)
        if t_base is None: return jsonify({"error": "Archivo Base corrupto o sin datos."}), 400
        
        # El error de la base para cada instante 't'
        err_E_matriz = e_base - baseE_oficial
        err_N_matriz = n_base - baseN_oficial
        err_Z_matriz = (z_base - alturaBase) - baseZ_oficial

        # Error absoluto promedio (Solo para la visualización del usuario)
        error_E_avg = float(np.mean(err_E_matriz))
        error_N_avg = float(np.mean(err_N_matriz))
        error_Z_avg = float(np.mean(err_Z_matriz))

        resultados = []
        
        # 2. PROCESAR CADA ROVER CON INTERPOLACIÓN TEMPORAL
        for rover_file in rover_files:
            t_rov, e_rov, n_rov, z_rov = procesar_gpx_crudo(rover_file, huso)
            if t_rov is None: continue
            
            puntos_iniciales = len(t_rov)

            # Interpolación Lineal: ¿Cuál era el error de la Base en el microsegundo que el Rover midió?
            err_E_interpolado = np.interp(t_rov, t_base, err_E_matriz)
            err_N_interpolado = np.interp(t_rov, t_base, err_N_matriz)
            err_Z_interpolado = np.interp(t_rov, t_base, err_Z_matriz)
            
            # Aplicar corrección diferencial punto a punto
            e_rov_corr = e_rov - err_E_interpolado
            n_rov_corr = n_rov - err_N_interpolado
            z_rov_corr = (z_rov - alturaRover) - err_Z_interpolado
            
            # Limpieza Estadística IQR: Eliminar basura antes de Kalman
            t_limpio, e_limpio, n_limpio, z_limpio = eliminar_valores_atipicos_iqr(t_rov, e_rov_corr, n_rov_corr, z_rov_corr)
            
            puntos_utiles = len(t_limpio)
            if puntos_utiles == 0: continue # Rover invalidado totalmente por ruido extremo
            
            # Filtro de Kalman Secuencial sobre la nube ya limpia y corregida diferencialmente
            final_E, rms_e = kalman_filter(e_limpio)
            final_N, rms_n = kalman_filter(n_limpio)
            final_Z, rms_z = kalman_filter(z_limpio)
            
            # Cálculo de Línea Base Promedio (para el reporte)
            base_e_centro, base_n_centro = np.mean(e_base), np.mean(n_base)
            dist_base = math.sqrt((final_E - base_e_centro)**2 + (final_N - base_n_centro)**2)
            
            # Control de Calidad
            rms_total = rms_e + rms_n + rms_z
            dop_estimado = round((rms_total / 3) + 0.8, 2)
            qa_str = "[ÓPTIMO 🟢]" if rms_total < 1.0 else ("[ACEPTABLE 🟡]" if rms_total < 2.5 else "[DEFICIENTE 🔴]")

            resultados.append({
                "roverName": rover_file.filename,
                "baseName": base_file.filename,
                "puntos": f"{puntos_utiles}/{puntos_iniciales} (IQR)", # Muestra cuántos sobrevivieron al filtro
                "csv": {
                    "qaStr": qa_str,
                    "dop": str(dop_estimado),
                    "distBase": str(round(dist_base, 3)),
                    "totalErrE": str(round(error_E_avg, 6)),
                    "totalErrN": str(round(error_N_avg, 6)),
                    "totalErrZ": str(round(error_Z_avg, 6)),
                    "winErrE": str(round(error_E_avg * 0.15, 6)), 
                    "winErrN": str(round(error_N_avg * 0.15, 6)),
                    "winErrZ": str(round(error_Z_avg * 0.15, 6)),
                    "rmsE": str(round(rms_e, 5)),
                    "rmsN": str(round(rms_n, 5)),
                    "rmsZ": str(round(rms_z, 5)),
                    "e": str(round(final_E, 4)),
                    "n": str(round(final_N, 4)),
                    "z": str(round(final_Z, 4))
                }
            })

        return jsonify({"resultados": resultados}), 200

    except Exception as e:
        return jsonify({"error": f"Error Matemático o de IO: {str(e)}"}), 500
