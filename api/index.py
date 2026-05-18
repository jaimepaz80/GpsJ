from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
import traceback

app = Flask(__name__)
CORS(app)

def procesar_archivo_gpx(file_stream):
    """
    Parsea el GPX, limpia el ruido (HDOP) y calcula el promedio geométrico puro.
    Versión estable y ligera sin dependencias geoidales pesadas.
    """
    gpx = gpxpy.parse(file_stream)
    lats, lons, eles = [], [], []

    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                # Filtro de Ruido Atmosférico Básico
                if pt.horizontal_dilution and pt.horizontal_dilution > 3.0:
                    continue 
                
                lats.append(pt.latitude)
                lons.append(pt.longitude)
                eles.append(pt.elevation)

    if not lats:
        return None

    # Cálculo del Centroide (Promedio robusto)
    return {
        "lat_promedio": np.mean(lats),
        "lon_promedio": np.mean(lons),
        "ele_promedio": np.mean(eles),
        "epocas_utiles": len(lats)
    }

@app.route('/api/procesar_diferencial', methods=['POST'])
def procesar_diferencial():
    try:
        # 1. Validación de Archivos
        if 'base_gpx' not in request.files or 'rover_gpx' not in request.files:
            return jsonify({"error": "Faltan archivos GPX (Base o Rover)"}), 400

        base_file = request.files['base_gpx']
        rover_file = request.files['rover_gpx']
        
        # 2. Extracción segura de coordenadas Oficiales de la Base
        def parse_float_seguro(val):
            try:
                return float(val) if val else 0.0
            except ValueError:
                return 0.0

        base_oficial_lat = parse_float_seguro(request.form.get('base_lat_oficial'))
        base_oficial_lon = parse_float_seguro(request.form.get('base_lon_oficial'))
        base_oficial_ele = parse_float_seguro(request.form.get('base_ele_oficial'))

        # 3. Procesamiento de Nubes de Puntos
        datos_base = procesar_archivo_gpx(base_file)
        datos_rover = procesar_archivo_gpx(rover_file)

        if not datos_base or not datos_rover:
            return jsonify({"error": "Archivos GPX vacíos o con demasiado ruido (HDOP muy alto)."}), 400

        # 4. MATEMÁTICA DIFERENCIAL (Cálculo del Vector de Error de la Base)
        error_lat = datos_base['lat_promedio'] - base_oficial_lat
        error_lon = datos_base['lon_promedio'] - base_oficial_lon
        error_ele = datos_base['ele_promedio'] - base_oficial_ele

        # 5. CORRECCIÓN DEL ROVER (Aplicando el vector de error)
        rover_corregido_lat = datos_rover['lat_promedio'] - error_lat
        rover_corregido_lon = datos_rover['lon_promedio'] - error_lon
        rover_corregido_ele = datos_rover['ele_promedio'] - error_ele

        # 6. Reporte Final JSON para la interfaz
        respuesta = {
            "status": "exito",
            "analisis_base": {
                "epocas_usadas": datos_base['epocas_utiles'],
                "error_detectado_m": {
                    "latitud_y": round(error_lat * 111320, 3), 
                    "longitud_x": round(error_lon * 111320 * np.cos(np.radians(base_oficial_lat)), 3),
                    "cota_z": round(error_ele, 3)
                }
            },
            "resultado_rover_corregido": {
                "latitud": round(rover_corregido_lat, 8),
                "longitud": round(rover_corregido_lon, 8),
                "cota_z": round(rover_corregido_ele, 3) 
            }
        }
        return jsonify(respuesta), 200

    except Exception as e:
        error_trace = traceback.format_exc()
        return jsonify({
            "error": "Error interno en el cálculo del servidor.",
            "detalle": str(e),
            "traza": error_trace
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
