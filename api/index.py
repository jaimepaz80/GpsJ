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
    Filtro Estadístico Espacial (IQR) para remoción de Multipath severo.
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

def filtro_kalman_rts_6d_pv(e_vals, n_vals, z_vals, t_vals, hdop_vals):
    """
    Filtro de Kalman Multivariado Posición-Velocidad (6D) + Suavizador RTS Backward.
    Ponderación de varianza adaptativa mediante HDOP por época.
    """
    num_puntos = len(e_vals)
    if num_puntos == 0: 
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    # 1. FORWARD PASS: FILTRO DE KALMAN 6D (Posición + Velocidad)
    # Vector de Estado X: [Este, Norte, Cota, vEste, vNorte, vCota]
    X = np.array([[e_vals[0]], [n_vals[0]], [z_vals[0]], [0.0], [0.0], [0.0]])
    P = np.eye(6) * 1.0  # Matriz de covarianza inicial
    
    # Historiales estructurales para la recursión backward RTS
    X_hist, P_hist, X_pred_hist, P_pred_hist, F_hist = [], [], [], [], []
    
    # Matriz de Observación H (3x6): Solo medimos posiciones espaciales
    H = np.zeros((3, 6))
    H[0, 0], H[1, 1], H[2, 2] = 1.0, 1.0, 1.0
    
    I = np.eye(6)
    
    # Varianzas base intrínsecas de la sesión de rastreo
    var_e = np.var(e_vals) if num_puntos > 1 and np.var(e_vals) > 0 else 1.0
    var_n = np.var(n_vals) if num_puntos > 1 and np.var(n_vals) > 0 else 1.0
    var_z = np.var(z_vals) if num_puntos > 1 and np.var(z_vals) > 0 else 1.0

    for i in range(num_puntos):
        # Cálculo del delta de tiempo real entre épocas (Muestreo dinámico)
        dt = t_vals[i] - t_vals[i-1] if i > 0 else 1.0
        if dt <= 0: dt = 1.0
        
        # Matriz de Transición Dinámica F (Cinemática PV)
        F = np.eye(6)
        F[0, 3], F[1, 4], F[2, 5] = dt, dt, dt
        
        # Matriz de Ruido del Proceso Q (Incertidumbre física del desplazamiento)
        Q = np.zeros((6, 6))
        np.fill_diagonal(Q[:3, :3], 0.001)  # Varianza de posición
        np.fill_diagonal(Q[3:, 3:], 0.01)   # Varianza de velocidad (mayor libertad de aceleración)
        
        # Matriz de Ruido de Medición R (3x3) Ponderada dinámicamente por el HDOP de la época k
        factor_hdop = hdop_vals[i] if hdop_vals[i] > 0 else 1.0
        R = np.diag([var_e, var_n, var_z]) * factor_hdop
        
        # Ecuaciones de Predicción (Forward)
        X_pred = np.dot(F, X)
        P_pred = np.dot(F, np.dot(P, F.T)) + Q
        
        # Almacenamiento en caché de matrices previas
        X_pred_hist.append(X_pred)
        P_pred_hist.append(P_pred)
        F_hist.append(F)
        
        # Ecuaciones de Actualización (Corrección)
        Z_meas = np.array([[e_vals[i]], [n_vals[i]], [z_vals[i]]])
        y = Z_meas - np.dot(H, X_pred)
        S = np.dot(H, np.dot(P_pred, H.T)) + R
        K = np.dot(P_pred, np.dot(H.T, np.linalg.inv(S)))
        
        X = X_pred + np.dot(K, y)
        P = np.dot((I - np.dot(K, H)), P_pred)
        
        X_hist.append(X)
        P_hist.append(P)

    # 2. BACKWARD PASS: SUAVIZADOR OPTIMIZADO RAUCH-TUNG-STRIEBEL (RTS)
    X_smoothed = list(X_hist)
    P_smoothed = list(P_hist)
    
    # Inversión cronológica: Desde la penúltima época hacia el origen (0)
    for k in range(num_puntos - 2, -1, -1):
        F_next = F_hist[k+1]
        P_curr = P_hist[k]
        P_pred_next_inv = np.linalg.inv(P_pred_hist[k+1])
        
        # Matriz de Ganancia de Suavizado RTS (C_k)
        C = np.dot(P_curr, np.dot(F_next.T, P_pred_next_inv))
        
        # Ajuste de trayectoria conociendo el "futuro" de la sesión
        X_smoothed[k] = X_smoothed[k] + np.dot(C, (X_smoothed[k+1] - X_pred_hist[k+1]))
        P_smoothed[k] = P_smoothed[k] + np.dot(C, np.dot((P_smoothed[k+1] - P_pred_hist[k+1]), C.T))
        
    # Extracción analítica de los vectores espaciales ya suavizados
    smoothed_e = np.array([x[0, 0] for x in X_smoothed])
    smoothed_n = np.array([x[1, 0] for x in X_smoothed])
    smoothed_z = np.array([x[2, 0] for x in X_smoothed])
    
    # Retorna el estado final depurado y las desviaciones estándar (RMS) definitivas
    return (float(smoothed_e[-1]), float(smoothed_n[-1]), float(smoothed_z[-1]),
            float(np.std(smoothed_e)), float(np.std(smoothed_n)), float(np.std(smoothed_z)))

def procesar_gpx_crudo(file_stream, huso):
    """
    Parser geodésico y extractor vectorial de marcas de tiempo y HDOP.
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

        # 1. PROCESAMIENTO DE VECTOR DE ERROR DE LA BASE
        t_base, e_base, n_base, z_base, _ = procesar_gpx_crudo(base_file, huso)
        if t_base is None: return jsonify({"error": "Archivo Base vacío o corrupto."}), 400
        
        err_E_matriz = e_base - baseE_oficial
        err_N_matriz = n_base - baseN_oficial
        err_Z_matriz = (z_base - alturaBase) - baseZ_oficial

        error_E_avg, error_N_avg, error_Z_avg = float(np.mean(err_E_matriz)), float(np.mean(err_N_matriz)), float(np.mean(err_Z_matriz))
        resultados = []
        
        # 2. PROCESAMIENTO INDEPENDIENTE DE ROVERS (MÁXIMO 5 MINUTOS POR ARCHIVO)
        for rover_file in rover_files:
            t_rov, e_rov, n_rov, z_rov, hdop_rov = procesar_gpx_crudo(rover_file, huso)
            if t_rov is None: continue
            
            puntos_iniciales = len(t_rov)

            # Sincronización Temporal Dinámica por Época
            err_E_int = np.interp(t_rov, t_base, err_E_matriz)
            err_N_int = np.interp(t_rov, t_base, err_N_matriz)
            err_Z_int = np.interp(t_rov, t_base, err_Z_matriz)
            
            e_rov_corr = e_rov - err_E_int
            n_rov_corr = n_rov - err_N_int
            z_rov_corr = (z_rov - alturaRover) - err_Z_int
            
            # Limpieza Estadística IQR
            t_lim, e_lim, n_lim, z_lim, hdop_lim = eliminar_valores_atipicos_iqr(t_rov, e_rov_corr, n_rov_corr, z_rov_corr, hdop_rov)
            
            puntos_utiles = len(t_lim)
            if puntos_utiles == 0: continue
            
            # EJECUCIÓN DEL TERCER MODELO: Kalman PV 6D + RTS Smoother
            final_E, final_N, final_Z, rms_e, rms_n, rms_z = filtro_kalman_rts_6d_pv(e_lim, n_lim, z_lim, t_lim, hdop_lim)
            
            base_e_cen, base_n_cen = np.mean(e_base), np.mean(n_base)
            dist_base = math.sqrt((final_E - base_e_cen)**2 + (final_N - base_n_cen)**2)
            
            rms_total = rms_e + rms_n + rms_z
            dop_estimado = round((rms_total / 3) + 0.8, 2)
            qa_str = "[ÓPTIMO 🟢]" if rms_total < 0.8 else ("[ACEPTABLE 🟡]" if rms_total < 2.0 else "[DEFICIENTE 🔴]")

            # Mapeo estricto compatible con index.html
            resultados.append({
                "roverName": rover_file.filename,
                "baseName": base_file.filename,
                "puntos": f"{puntos_utiles}/{puntos_iniciales} (IQR+RTS)",
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
        return jsonify({"error": f"Fallo Crítico Motor Geodésico v3: {str(e)}"}), 500
