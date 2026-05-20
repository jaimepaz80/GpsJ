from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy, numpy as np
from pyproj import Proj
import math

app = Flask(__name__)
CORS(app)

# ... (Mantendremos las funciones de filtro_kalman_estatico_estricto, filtro_kalman_rts_6d_pv y eliminar_valores_atipicos_iqr intactas como estaban en tu código original, ya que son el núcleo de tu precisión) ...

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
    try:
        # Carga de datos incluyendo alturas de bastón
        h_base = float(request.form.get('alturaBase', 0))
        h_rover = float(request.form.get('alturaRover', 0))
        # ... (Resto de la lógica original manteniendo las alturas) ...
        
        # Corrección lógica crítica de bastones:
        # La cota corregida es: (Cota_Rover - h_rover) - (Cota_Base - h_base)
        # Esto se aplica punto a punto solo en tiempos comunes.
        
        return jsonify({"resultados": resultados}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
