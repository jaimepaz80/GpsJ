from flask import Flask, request, jsonify
from flask_cors import CORS
import utm, math
import xml.etree.ElementTree as ET
from datetime import datetime

app = Flask(__name__)
CORS(app)

def parse_gpx_memory(file_obj, huso):
    """Parsea GPX directamente desde la RAM (sin disco duro) y extrae el nombre."""
    pts = {}
    utm_list = []
    nombre_punto = "Punto_Desconocido"
    
    try:
        tree = ET.parse(file_obj)
        root = tree.getroot()
        
        # Extracción automática del Nombre inyectado por la Colectora
        name_node = root.find('.//{*}metadata/{*}name')
        if name_node is None:
            name_node = root.find('.//{*}trk/{*}name')
        if name_node is not None and name_node.text:
            nombre_punto = name_node.text

        for trkpt in root.findall('.//{*}trkpt'):
            lat, lon = float(trkpt.get('lat')), float(trkpt.get('lon'))
            
            ele_node = trkpt.find('{*}ele')
            ele = float(ele_node.text) if ele_node is not None else 0.0
            
            sat_node = trkpt.find('{*}sat')
            sat = int(sat_node.text) if sat_node is not None else 1
            
            hdop_node = trkpt.find('{*}hdop')
            pdop_node = trkpt.find('{*}pdop')
            if hdop_node is not None: dop = float(hdop_node.text)
            elif pdop_node is not None: dop = float(pdop_node.text)
            else: dop = 1.0 
            
            time_node = trkpt.find('{*}time')
            if time_node is not None:
                time_str = time_node.text.replace('Z', '')
                try: dt = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%f')
                except: dt = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S')
                
                e, n, _, _ = utm.from_latlon(lat, lon, force_zone_number=huso)
                pts[dt] = (lat, lon, ele, sat, e, n, dop)
                utm_list.append((e, n, ele))
    except Exception as e: 
        print(f"Error parseando RAM: {e}")
        
    return pts, utm_list, nombre_punto

def filtro_kalman_estatico(mediciones, sats, dops):
    if not mediciones: return 0.0
    x_est, P, Q = mediciones[0], 10.0, 1e-5
    for z, sat, dop in zip(mediciones, sats, dops):
        P += Q
        R = (20.0 * max(dop, 0.1)) / (sat if sat > 0 else 1)
        K = P / (P + R)
        x_est += K * (z - x_est)
        P *= (1 - K)
    return x_est

@app.route('/api/procesar', methods=['POST'])
def procesar():
    try:
        huso = int(request.form.get('huso', 19))
        bE_know = float(request.form.get('baseE'))
        bN_know = float(request.form.get('baseN'))
        bZ_know = float(request.form.get('baseZ'))
        hB = float(request.form.get('alturaBase') or 0.0)
        hR = float(request.form.get('alturaRover') or 0.0)
        
        base_file = request.files['base']
        # Parseo directo en RAM
        base_data, base_utm_all, base_name = parse_gpx_memory(base_file.stream, huso)
        
        avg_bE = sum(p[0] for p in base_utm_all) / len(base_utm_all)
        avg_bN = sum(p[1] for p in base_utm_all) / len(base_utm_all)
        avg_bZ = sum(p[2] for p in base_utm_all) / len(base_utm_all)
        
        totalErrE = bE_know - avg_bE
        totalErrN = bN_know - avg_bN
        totalErrZ = bZ_know - (avg_bZ - hB)

        resultados = []
        rovers = request.files.getlist('rovers')
        tiempos_base = sorted(list(base_data.keys()))

        for r_file in rovers:
            rover_data, _, r_name = parse_gpx_memory(r_file.stream, huso)
            
            cE, cN, cZ, cSat, cDop, dE, dN, dZ = [], [], [], [], [], [], [], []
            
            for tR, (rLat, rLon, rEle, rSat, rE_raw, rN_raw, rDop) in rover_data.items():
                cercanos = [t for t in tiempos_base if abs((tR - t).total_seconds()) <= 1.0]
                if cercanos:
                    tB = min(cercanos, key=lambda t: abs((tR - t).total_seconds()))
                    _, _, bEle, _, bE_raw, bN_raw, _ = base_data[tB]
                    
                    errE, errN, errZ = bE_know - bE_raw, bN_know - bN_raw, bZ_know - (bEle - hB)
                    cE.append(rE_raw + errE)
                    cN.append(rN_raw + errN)
                    cZ.append((rEle - hR) + errZ)
                    cSat.append(rSat)
                    cDop.append(rDop)
                    dE.append(errE); dN.append(errN); dZ.append(errZ)

            if cE:
                winE, winN, winZ = sum(dE)/len(dE), sum(dN)/len(dN), sum(dZ)/len(dZ)
                rmsE = math.sqrt(sum((x-winE)**2 for x in dE)/len(dE))
                rmsN = math.sqrt(sum((x-winN)**2 for x in dN)/len(dN))
                rmsZ = math.sqrt(sum((x-winZ)**2 for x in dZ)/len(dZ))
                
                max_rms = max(rmsE, rmsN, rmsZ)
                qa_status = "[EXCELENTE 🟢]" if max_rms < 0.05 else "[ACEPTABLE 🟡]" if max_rms <= 0.15 else "[DEFICIENTE 🔴]"

                resE = filtro_kalman_estatico(cE, cSat, cDop)
                resN = filtro_kalman_estatico(cN, cSat, cDop)
                resZ = filtro_kalman_estatico(cZ, cSat, cDop)
                
                dist_base = math.sqrt((resE - bE_know)**2 + (resN - bN_know)**2)
                avg_dop = sum(cDop)/len(cDop)
                
                resultados.append({
                    "roverName": r_name, "baseName": base_name, "puntos": len(cE),
                    "csv": {
                        "baseName": base_name, "roverName": r_name, "puntos": len(cE),
                        "qaStr": qa_status, "dop": f"{avg_dop:.2f}", "distBase": f"{dist_base:.3f}",
                        "totalErrE": f"{totalErrE:.6f}", "totalErrN": f"{totalErrN:.6f}", "totalErrZ": f"{totalErrZ:.6f}",
                        "winErrE": f"{winE:.6f}", "winErrN": f"{winN:.6f}", "winErrZ": f"{winZ:.6f}",
                        "rmsE": f"{rmsE:.6f}", "rmsN": f"{rmsN:.6f}", "rmsZ": f"{rmsZ:.6f}",
                        "e": f"{resE:.6f}", "n": f"{resN:.6f}", "z": f"{resZ:.6f}"
                    }
                })
        return jsonify({"resultados": resultados})
    except Exception as e: return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run()
