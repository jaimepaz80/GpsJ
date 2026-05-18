from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
from pyproj import Proj
import math

app = Flask(__name__)
CORS(app)

def eliminar_valores_atipicos_iqr(t, x, y, z, hdop):
    """
    Filtro Estadístico Espacial (IQR). Ahora sincronizado con el vector HDOP.
    """
    if len(x) < 4: return t, x, y, z, hdop
    
    q1_x, q3_x = np.percentile(x, [25, 75]); iqr_x = q3_x - q1_x
    q1_y, q3_y = np.percentile(y, [25, 75]); iqr_y = q3_y - q1_y
    q1_z, q3_z = np.percentile(z, [25, 75]); iqr_z = q3_z - q1_z
    
    lim_inf_x, lim_sup_x = q1_x - 1.5 * iqr_x, q3_x + 1.5 * iqr_x
    lim_inf_y, lim_sup_y = q1_y - 1.5 * iqr_y, q3_y + 1.5 * iqr_y
    lim_inf_z, lim_sup_z = q1_z - 1.5 * iqr_z, q3_z + 1.5 * iqr_z
    
    mask = (x >= lim_inf_x) & (x <= lim_sup_x) & \
           (y >= lim_inf_y) & (y <= lim_sup_y) & \
           (z >= lim_inf_z) & (z <= lim_sup_z)
           
    return t[mask], x[mask], y[mask], z[mask], hdop[mask]

def kalman_filter_3d(e_vals, n_vals, z_vals, hdop_vals):
    """
    Filtro de Kalman Multivariado (3D) con Ponderación de Varianza por HDOP.
    """
    num_puntos = len(e_vals)
    if num_puntos == 0: 
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    # Estado Inicial X: [Este, Norte, Cota]
    X = np.array([[e_vals[0]], [n_vals[0]], [z_vals[0]]])
    
    # Matriz de Covarianza Inicial P (3x3)
    P = np.eye(3) * 1.0 
    
    # Matriz de Ruido de Proceso Q (Dinámica del modelo estacionario)
    Q = np.eye(3) * 0.001

    # Identidad
    I = np.eye(3)

    # Varianzas base de la sesión completa (para escalar con el HDOP)
    var_e = np.var(e_vals) if num_puntos > 1 and np.var(e_vals) > 0 else 1.0
    var_n = np.var(n_vals) if num_puntos > 1 and np.var(n_vals) > 0 else 1.0
    var_z = np.var(z_vals) if num_puntos > 1 and np.var(z_vals) > 0 else 1.0

    estimaciones_e, estimaciones_n, estimaciones_z = [], [], []

    for i in range(num_puntos):
        # Medición actual (Z_k)
        Z_meas = np.array([[e_vals[i]], [n_vals[i]], [z_vals[i]]])
        
        # Ponderación HDOP: Si el HDOP es alto, el ruido R aumenta drásticamente.
        factor_hdop = hdop_vals[i] if hdop_vals[i] > 0 else 1.0
        R = np.diag([var_e, var_n, var_z]) * factor_hdop
        
        # 1. Predicción
        X_pred = X  # Modelo estático: F es la Identidad
        P_pred = P + Q
        
        # 2. Actualización (Cálculo de Ganancia de Kalman K)
        S = P_pred + R
        K = np.dot(P_pred, np.linalg.inv(S)) # K = P * S^-1
        
        # 3. Estimación Final del Estado y Covarianza
        X = X_pred + np.dot(K, (Z_meas - X_pred))
        P = np.dot((I - K), P_pred)
        
        # Guardar historial para cálculos de RMS posteriores
        estimaciones_e.append(X[0, 0])
        estimaciones_n.append(X[1, 0])
        estimaciones_z.append(X[2, 0])

    return (float(X[0, 0]), float(X[1, 0]), float(X[2, 0]), 
            float(np.std(estimaciones_e)), float(np.std(estimaciones_n)), float(np.std(estimaciones_z)))

def procesar_gpx_crudo(file_stream, huso):
    """
    Extracción vectorial, ahora incluyendo el HDOP de la trama NMEA.
    """
    gpx = gpxpy.parse(file_stream)
    t_list, lats, lons, eles, hdops = [], [], [], [], []

    idx = 0
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.elevation is not None:
                    lats.append(pt.latitude)
                    lons.append(pt.longitude)
                    eles.append(pt.elevation)
                    # Extraer HDOP. Si el GPX no lo tiene, forzamos un valor neutro (1.0)
                    hdops.append(pt.horizontal_dilution if pt.horizontal_dilution is not None else 1.0)
                    t_list.append(pt.time.timestamp() if pt.time else float(idx))
                    idx += 1

    if not lats: return None, None, None, None, None

    myProj = Proj(f"+proj=utm +zone={huso} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")
    estes, nortes = myProj(np.array(lons), np.array(lats))
    
    return np.array(t_list), estes, nortes, np.array(eles), np.array(hdops)

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

        # 1. EXTRAER BASE
        t_base, e_base, n_base, z_base, _ = procesar_gpx_crudo(base_file, huso)
        if t_base is None: return jsonify({"error": "Archivo Base corrupto o sin datos."}), 400
        
        err_E_matriz = e_base - baseE_oficial
        err_N_matriz = n_base - baseN_oficial
        err_Z_matriz = (z_base - alturaBase) - baseZ_oficial

        error_E_avg, error_N_avg, error_Z_avg = float(np.mean(err_E_matriz)), float(np.mean(err_N_matriz)), float(np.mean(err_Z_matriz))
        resultados = []
        
        # 2. PROCESAR ROVERS
        for rover_file in rover_files:
            t_rov, e_rov, n_rov, z_rov, hdop_rov = procesar_gpx_crudo(rover_file, huso)
            if t_rov is None: continue
            
            puntos_iniciales = len(t_rov)

            # Interpolación Temporal (DGPS)
            err_E_int = np.interp(t_rov, t_base, err_E_matriz)
            err_N_int = np.interp(t_rov, t_base, err_N_matriz)
            err_Z_int = np.interp(t_rov, t_base, err_Z_matriz)
            
            e_rov_corr = e_rov - err_E_int
            n_rov_corr = n_rov - err_N_int
            z_rov_corr = (z_rov - alturaRover) - err_Z_int
            
            # Limpieza IQR (ahora arrastra el HDOP para no perder el orden)
            t_lim, e_lim, n_lim, z_lim, hdop_lim = eliminar_valores_atipicos_iqr(t_rov, e_rov_corr, n_rov_corr, z_rov_corr, hdop_rov)
            
            puntos_utiles = len(t_lim)
            if puntos_utiles == 0: continue
            
            # NUEVO MOTOR: Filtro de Kalman 3D Ponderado
            final_E, final_N, final_Z, rms_e, rms_n, rms_z = kalman_filter_3d(e_lim, n_lim, z_lim, hdop_lim)
            
            base_e_cen, base_n_cen = np.mean(e_base), np.mean(n_base)
            dist_base = math.sqrt((final_E - base_e_cen)**2 + (final_N - base_n_cen)**2)
            
            rms_total = rms_e + rms_n + rms_z
            dop_estimado = round((rms_total / 3) + 0.8, 2)
            qa_str = "[ÓPTIMO 🟢]" if rms_total < 1.0 else ("[ACEPTABLE 🟡]" if rms_total < 2.5 else "[DEFICIENTE 🔴]")

            resultados.append({
                "roverName": rover_file.filename,
                "baseName": base_file.filename,
                "puntos": f"{puntos_utiles}/{puntos_iniciales} (IQR)",
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
        return jsonify({"error": f"Fallo Crítico Motor 3D: {str(e)}"}), 500
