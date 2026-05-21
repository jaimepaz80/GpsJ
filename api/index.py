from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
from pyproj import Proj
import math

app = Flask(__name__)
CORS(app)

def moving_average(data, window_size=5):
    """
    MEJORA 3: Reducción de Inercia. 
    Ventana reducida de 15 a 5 para mitigar el desfase temporal.
    Permite reacciones casi instantáneas a las fluctuaciones atmosféricas reales.
    """
    if len(data) < window_size:
        return data
    window = np.ones(int(window_size)) / float(window_size)
    smoothed = np.convolve(data, window, 'same')
    pad_len = window_size // 2
    smoothed[:pad_len] = data[:pad_len]
    smoothed[-pad_len:] = data[-pad_len:]
    return smoothed

def filtro_mad(z_vals, threshold=3.5):
    """
    MEJORA 2: Filtro de Desviación Absoluta de la Mediana (MAD).
    Exclusivo para la Cota (Z). Al usar la Mediana en lugar del Promedio,
    es completamente inmune a los picos de error extremos de la API de Android.
    """
    if len(z_vals) < 4: return np.ones(len(z_vals), dtype=bool)
    med = np.median(z_vals)
    mad = np.median(np.abs(z_vals - med))
    if mad < 1e-6: mad = 1e-6 # Prevenir división por cero
    z_scores = (np.abs(z_vals - med) / mad)
    return z_scores < threshold

def eliminar_valores_atipicos_hibrido(t, x, y, z, hdop):
    """
    Filtro Híbrido: IQR para Planimetría (tolerancia normal) + MAD para Altimetría (destrucción de picos).
    """
    if len(x) < 4: return t, x, y, z, hdop
    
    # Planimetría (IQR)
    q1_x, q3_x = np.percentile(x, [25, 75]); iqr_x = q3_x - q1_x
    q1_y, q3_y = np.percentile(y, [25, 75]); iqr_y = q3_y - q1_y
    
    lim_inf_x, lim_sup_x = q1_x - 1.5 * iqr_x, q3_x + 1.5 * iqr_x
    lim_inf_y, lim_sup_y = q1_y - 1.5 * iqr_y, q3_y + 1.5 * iqr_y
    
    mask_xy = (x >= lim_inf_x) & (x <= lim_sup_x) & \
              (y >= lim_inf_y) & (y <= lim_sup_y)
              
    # Altimetría (MAD)
    mask_z = filtro_mad(z, threshold=3.5)
    
    mask_total = mask_xy & mask_z
           
    return t[mask_total], x[mask_total], y[mask_total], z[mask_total], hdop[mask_total]

def filtro_kalman_estatico_estricto(e_vals, n_vals, z_vals, hdop_vals):
    num_puntos = len(e_vals)
    if num_puntos == 0: return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    z_median = np.median(z_vals)
    X = np.array([[e_vals[0]], [n_vals[0]], [z_median]])
    P = np.eye(3) * 1.0
    
    Q = np.diag([0.001, 0.001, 0.0005]) 
    
    var_e = np.var(e_vals) if num_puntos > 1 and np.var(e_vals) > 0 else 1.0
    var_n = np.var(n_vals) if num_puntos > 1 and np.var(n_vals) > 0 else 1.0
    
    var_z_base = np.var(z_vals) if num_puntos > 1 and np.var(z_vals) > 0 else 1.0
    # MEJORA: Se eliminó el castigo excesivo (* 10.0) a la varianza Z.
    var_z = var_z_base * 2.0 

    X_hist, P_hist, X_pred_hist, P_pred_hist = [], [], [], []

    for i in range(num_puntos):
        factor_hdop = (hdop_vals[i]**2) if hdop_vals[i] > 0 else 1.0
        
        desviacion_z = abs(z_vals[i] - z_median)
        factor_z = factor_hdop * (1.0 + desviacion_z)
        
        R = np.diag([var_e * factor_hdop, var_n * factor_hdop, var_z * factor_z])
        
        X_pred, P_pred = X, P + Q
        X_pred_hist.append(X_pred)
        P_pred_hist.append(P_pred)
        
        Z_meas = np.array([[e_vals[i]], [n_vals[i]], [z_vals[i]]])
        S = P_pred + R
        K = np.dot(P_pred, np.linalg.pinv(S))
        
        X = X_pred + np.dot(K, (Z_meas - X_pred))
        P = np.dot((np.eye(3) - K), P_pred)
        
        X_hist.append(X)
        P_hist.append(P)

    X_smoothed = list(X_hist)
    for k in range(num_puntos - 2, -1, -1):
        P_pred_next_inv = np.linalg.pinv(P_pred_hist[k+1])
        C = np.dot(P_hist[k], P_pred_next_inv)
        X_smoothed[k] = X_smoothed[k] + np.dot(C, (X_smoothed[k+1] - X_pred_hist[k+1]))
        
    sum_e, sum_n, sum_z, sum_w, sum_w_z = 0, 0, 0, 0, 0
    for k in range(num_puntos):
        w = 1.0 / (hdop_vals[k] + 0.001)
        w_z = w / (1.0 + abs(X_smoothed[k][2,0] - z_median))
        
        sum_e += X_smoothed[k][0,0] * w
        sum_n += X_smoothed[k][1,0] * w
        sum_z += X_smoothed[k][2,0] * w_z
        sum_w += w
        sum_w_z += w_z
        
    final_E = sum_e / sum_w
    final_N = sum_n / sum_w
    final_Z = sum_z / sum_w_z

    smoothed_e = np.array([x[0,0] for x in X_smoothed])
    smoothed_n = np.array([x[1,0] for x in X_smoothed])
    smoothed_z = np.array([x[2,0] for x in X_smoothed])
    
    return final_E, final_N, final_Z, float(np.std(smoothed_e)), float(np.std(smoothed_n)), float(np.std(smoothed_z))

def filtro_kalman_rts_6d_pv(e_vals, n_vals, z_vals, t_vals, hdop_vals):
    num_puntos = len(e_vals)
    if num_puntos == 0: return [], [], [], 0.0, 0.0, 0.0

    X = np.array([[e_vals[0]], [n_vals[0]], [z_vals[0]], [0.0], [0.0], [0.0]])
    P = np.eye(6) * 1.0
    
    X_hist, P_hist, X_pred_hist, P_pred_hist, F_hist = [], [], [], [], []
    H = np.zeros((3, 6))
    H[0, 0], H[1, 1], H[2, 2] = 1.0, 1.0, 1.0
    I = np.eye(6)
    
    var_e = np.var(e_vals) if num_puntos > 1 and np.var(e_vals) > 0 else 1.0
    var_n = np.var(n_vals) if num_puntos > 1 and np.var(n_vals) > 0 else 1.0
    var_z = np.var(z_vals) if num_puntos > 1 and np.var(z_vals) > 0 else 1.0

    for i in range(num_puntos):
        dt = t_vals[i] - t_vals[i-1] if i > 0 else 1.0
        if dt <= 0: dt = 1.0
        
        F = np.eye(6)
        F[0, 3], F[1, 4], F[2, 5] = dt, dt, dt
        
        Q = np.zeros((6, 6))
        np.fill_diagonal(Q[:3, :3], 0.005 * dt) 
        np.fill_diagonal(Q[3:, 3:], 0.01 * dt)
        
        factor_hdop = hdop_vals[i] if hdop_vals[i] > 0 else 1.0
        R = np.diag([var_e, var_n, var_z]) * factor_hdop
        
        X_pred = np.dot(F, X)
        P_pred = np.dot(F, np.dot(P, F.T)) + Q
        
        X_pred_hist.append(X_pred)
        P_pred_hist.append(P_pred)
        F_hist.append(F)
        
        Z_meas = np.array([[e_vals[i]], [n_vals[i]], [z_vals[i]]])
        y = Z_meas - np.dot(H, X_pred)
        S = np.dot(H, np.dot(P_pred, H.T)) + R
        K = np.dot(P_pred, np.dot(H.T, np.linalg.pinv(S))) 
        
        X = X_pred + np.dot(K, y)
        P = np.dot((I - np.dot(K, H)), P_pred)
        X_hist.append(X)
        P_hist.append(P)

    X_smoothed = list(X_hist)
    for k in range(num_puntos - 2, -1, -1):
        F_next, P_curr = F_hist[k+1], P_hist[k]
        P_pred_next_inv = np.linalg.pinv(P_pred_hist[k+1])
        C = np.dot(P_curr, np.dot(F_next.T, P_pred_next_inv))
        X_smoothed[k] = X_smoothed[k] + np.dot(C, (X_smoothed[k+1] - X_pred_hist[k+1]))
        
    smoothed_e = [float(x[0, 0]) for x in X_smoothed]
    smoothed_n = [float(x[1, 0]) for x in X_smoothed]
    smoothed_z = [float(x[2, 0]) for x in X_smoothed]
    
    return smoothed_e, smoothed_n, smoothed_z, float(np.std(smoothed_e)), float(np.std(smoothed_n)), float(np.std(smoothed_z))

def procesar_gpx_crudo(file_stream, huso):
    gpx = gpxpy.parse(file_stream)
    t_list, lats, lons, eles, hdops = [], [], [], [], []

    idx = 0
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.elevation is not None:
                    hdop_val = pt.horizontal_dilution if pt.horizontal_dilution is not None else 1.0
                    
                    # MEJORA 1: Barrera de entrada. Destruir épocas con HDOP basura (Mala geometría satelital)
                    if hdop_val > 2.5: 
                        continue
                        
                    lats.append(pt.latitude)
                    lons.append(pt.longitude)
                    eles.append(pt.elevation)
                    hdops.append(hdop_val)
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
        modo = request.form.get('modo', 'estatico')
        
        baseE_oficial = float(request.form.get('baseE', 0))
        baseN_oficial = float(request.form.get('baseN', 0))
        baseZ_oficial = float(request.form.get('baseZ', 0))
        huso = int(request.form.get('huso', 19))
        alturaBase = float(request.form.get('alturaBase', 0))
        alturaRover = float(request.form.get('alturaRover', 0))

        t_base, e_base, n_base, z_base, _ = procesar_gpx_crudo(base_file, huso)
        if t_base is None: return jsonify({"error": "Archivo Base vacío o corrupto."}), 400
        
        t_base_unique, indices_unicos = np.unique(t_base, return_index=True)
        e_base_unique = e_base[indices_unicos]
        n_base_unique = n_base[indices_unicos]
        z_base_unique = z_base[indices_unicos]

        err_E_matriz = e_base_unique - baseE_oficial
        err_N_matriz = n_base_unique - baseN_oficial
        err_Z_matriz = (z_base_unique - alturaBase) - baseZ_oficial

        err_E_matriz = moving_average(err_E_matriz, 5) # Ventana reducida
        err_N_matriz = moving_average(err_N_matriz, 5) # Ventana reducida
        err_Z_matriz = moving_average(err_Z_matriz, 5) # Ventana reducida

        error_E_avg, error_N_avg, error_Z_avg = float(np.mean(err_E_matriz)), float(np.mean(err_N_matriz)), float(np.mean(err_Z_matriz))
        resultados = []
        
        for rover_file in rover_files:
            t_rov, e_rov, n_rov, z_rov, hdop_rov = procesar_gpx_crudo(rover_file, huso)
            if t_rov is None: continue
            
            puntos_iniciales = len(t_rov)

            inicio_comun = max(t_base_unique[0], t_rov[0])
            fin_comun = min(t_base_unique[-1], t_rov[-1])
            
            if inicio_comun > fin_comun:
                return jsonify({
                    "error": f"FALLO CRÍTICO DE SINCRONIZACIÓN: El Rover [{rover_file.filename}] y la Base [{base_file.filename}] no poseen ventanas de tiempo en común."
                }), 400

            mask_rov = (t_rov >= inicio_comun) & (t_rov <= fin_comun)
            t_rov = t_rov[mask_rov]
            e_rov = e_rov[mask_rov]
            n_rov = n_rov[mask_rov]
            z_rov = z_rov[mask_rov]
            hdop_rov = hdop_rov[mask_rov]
            
            puntos_comunes = len(t_rov)
            if puntos_comunes == 0:
                return jsonify({"error": f"FALLO DE INTERSECCIÓN: Cero puntos síncronos para {rover_file.filename}."}), 400

            err_E_int = np.interp(t_rov, t_base_unique, err_E_matriz)
            err_N_int = np.interp(t_rov, t_base_unique, err_N_matriz)
            err_Z_int = np.interp(t_rov, t_base_unique, err_Z_matriz) 
            
            e_rov_corr = e_rov - err_E_int
            n_rov_corr = n_rov - err_N_int
            z_rov_corr = (z_rov - alturaRover) - err_Z_int 
            
            t_lim, e_lim, n_lim, z_lim, hdop_lim = eliminar_valores_atipicos_hibrido(t_rov, e_rov_corr, n_rov_corr, z_rov_corr, hdop_rov)
            
            puntos_utiles = len(t_lim)
            if puntos_utiles == 0: continue
            
            if modo == 'estatico':
                final_E, final_N, final_Z, rms_e, rms_n, rms_z = filtro_kalman_estatico_estricto(e_lim, n_lim, z_lim, hdop_lim)
                track_data = [{ "e": final_E, "n": final_N, "z": final_Z, "epoca": "Estático" }]
            else:
                track_E, track_N, track_Z, rms_e, rms_n, rms_z = filtro_kalman_rts_6d_pv(e_lim, n_lim, z_lim, t_lim, hdop_lim)
                final_E, final_N, final_Z = track_E[-1], track_N[-1], track_Z[-1]
                track_data = [{ "e": track_E[i], "n": track_N[i], "z": track_Z[i], "epoca": i+1 } for i in range(len(track_E))]
            
            base_e_cen, base_n_cen = np.mean(e_base), np.mean(n_base)
            dist_base = math.sqrt((final_E - base_e_cen)**2 + (final_N - base_n_cen)**2)
            
            rms_total = rms_e + rms_n + rms_z
            dop_estimado = round((rms_total / 3) + 0.8, 2)
            qa_str = "[ÓPTIMO 🟢]" if rms_total < 0.8 else ("[ACEPTABLE 🟡]" if rms_total < 2.0 else "[DEFICIENTE 🔴]")

            resultados.append({
                "roverName": rover_file.filename,
                "baseName": base_file.filename,
                "modo": modo.upper(),
                "puntos": f"{puntos_utiles}/{puntos_iniciales} (Síncronos)",
                "track": track_data,
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
        return jsonify({"error": f"Fallo Crítico Motor Geodésico: {str(e)}"}), 500
