from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
import traceback

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------
# INICIALIZACIÓN BLINDADA (TOLERANCIA A FALLOS)
# Si Vercel colapsa por memoria al cargar pyproj, el servidor 
# sobrevivirá y seguirá procesando el cálculo diferencial.
# ---------------------------------------------------------
USE_GEOID = False
GEOID_ERROR = ""
try:
    from pyproj import Transformer
    # Intenta cargar la matriz global EGM96
    geoid_transformer = Transformer.from_crs("EPSG:4979", "EPSG:4326+5773", always_xy=True)
    USE_GEOID = True
except Exception as e:
    USE_GEOID = False
    GEOID_ERROR = str(e)


def procesar_archivo_gpx(file_stream, es_base=False):
    """
    Parsea el GPX, limpia el ruido (HDOP) y aplica el modelo Geoidal si está activo.
    """
    gpx = gpxpy.parse(file_stream)
    lats, lons, eles = [], [], []

    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                # 1. Filtro de Ruido Atmosférico
                if pt.horizontal_dilution and pt.horizontal_dilution > 2.5:
                    continue 
                
                # 2. Motor Geoidal Seguro
                lon_geo, lat_geo, alt = pt.longitude, pt.latitude, pt.elevation
                if USE_GEOID:
                    try:
                        lon_geo, lat_geo, alt = geoid_transformer.transform(pt.longitude, pt.latitude, pt.elevation)
                    except:
                        pass # Si falla un punto, mantiene la cota cruda

                lats.append(lat_geo)
                lons.append(lon_geo)
                eles.append(alt)

    if not lats:
        return None

    # 3. Cálculo del Centroide
    return {
        "lat_promedio": np.mean(lats),
        "lon_promedio": np.mean(lons),
        "ele_promedio": np.mean(eles),
        "epocas_utiles": len(lats)
    }


@app.route('/api/procesar_diferencial', methods=['POST'])
def procesar_diferencial():
    try:
        # Validación de Archivos
        if 'base_gpx' not in request.files or 'rover_gpx' not in request.files:
            return jsonify({"error": "Faltan archivos GPX (Base o Rover)"}), 400

        base_file = request.files['base_gpx']
        rover_file = request.files['rover_gpx']
        
        # Extracción segura de coordenadas del formulario
        def parse_float_seguro(val):
            try:
                return float(val) if val else 0.0
            except ValueError:
                return 0.0

        base_oficial_lat = parse_float_seguro(request.form.get('base_lat_oficial'))
        base_oficial_lon = parse_float_seguro(request.form.get('base_lon_oficial'))
        base_oficial_ele = parse_float_seguro(request.form.get('base_ele_oficial'))

        # Procesamiento de Nubes de Puntos
        datos_base = procesar_archivo_gpx(base_file, es_base=True)
        datos_rover = procesar_archivo_gpx(rover_file, es_base=False)

        if not datos_base or not datos_rover:
            return jsonify({"error": "Archivos GPX vacíos o con demasiado ruido (HDOP > 2.5)."}), 400

        # MATEMÁTICA DIFERENCIAL (Vector de Error)
        error_lat = datos_base['lat_promedio'] - base_oficial_lat
        error_lon = datos_base['lon_promedio'] - base_oficial_lon
        error_ele = datos_base['ele_promedio'] - base_oficial_ele

        # CORRECCIÓN DEL ROVER
        rover_corregido_lat = datos_rover['lat_promedio'] - error_lat
        rover_corregido_lon = datos_rover['lon_promedio'] - error_lon
        rover_corregido_ele = datos_rover['ele_promedio'] - error_ele

        # Reporte Final JSON
        respuesta = {
            "status": "exito",
            "analisis_base": {
                "epocas_usadas": datos_base['epocas_utiles'],
                "error_ionosferico_detectado_m": {
                    "latitud_y": round(error_lat * 111320, 3), 
                    "longitud_x": round(error_lon * 111320 * np.cos(np.radians(base_oficial_lat)), 3),
                    "cota_z": round(error_ele, 3)
                }
            },
            "resultado_rover_corregido": {
                "latitud": round(rover_corregido_lat, 8),
                "longitud": round(rover_corregido_lon, 8),
                "cota_z": round(rover_corregido_ele, 3) 
            },
            "auditoria_servidor": {
                "motor_geoidal_activo": USE_GEOID,
                "diagnostico_interno": GEOID_ERROR if not USE_GEOID else "Operativo al 100%"
            }
        }
        return jsonify(respuesta), 200

    except Exception as e:
        # Si algo explota, se envía el error exacto al teléfono, no un bloqueo silencioso.
        error_trace = traceback.format_exc()
        return jsonify({
            "error": "El servidor en la nube experimentó un fallo matemático.",
            "detalle_tecnico": str(e),
            "traza": error_trace
        }), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
