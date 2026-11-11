from config.database import mongo_db
from repositories.redis_repo import actualizar_ultima_posicion
from datetime import datetime, timedelta
import random

# --- MÓDULO IoT Y TELEMETRÍA ---
def generar_lectura_iot_coordenadas(id_envio, id_contenedor, id_sensor=None):
    """
    Busca automáticamente los sensores asociados al contenedor en PostgreSQL,
    calcula las coordenadas GPS reales en base a la ruta de Neo4j y actualiza Redis y MongoDB con hora local.
    """
    from config.database import get_pg_connection
    from repositories.neo4j_repo import buscar_camino_optimo

    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT origen_envio, destino_envio, estado_envio FROM envio WHERE id_envio = %s;", (id_envio,))
        envio_info = cursor.fetchone()
        if not envio_info:
            raise Exception(f"No existe el Envío #{id_envio}.")

        cursor.execute("SELECT id_contenedor FROM contenedor WHERE id_contenedor = %s AND id_envio = %s;", (id_contenedor, id_envio))
        if not cursor.fetchone():
            raise Exception(f"El Contenedor #{id_contenedor} no pertenece al Envío #{id_envio} o no existe.")

        if id_sensor is None:
            cursor.execute("""
                SELECT id_sensor FROM sensor_iot 
                WHERE id_contenedor = %s AND estado_sensor = TRUE 
                ORDER BY id_sensor ASC;
            """, (id_contenedor,))
            sensores_db = [r[0] for r in cursor.fetchall()]
            if not sensores_db:
                sensores_db = [1]
        else:
            sensores_db = [id_sensor]
    finally:
        cursor.close()
        conn.close()

    origen, destino, _ = envio_info

    ruta_neo4j = buscar_camino_optimo(origen, destino)
    if ruta_neo4j and len(ruta_neo4j[0]["puntos_gps"]) > 0:
        puntos_gps = ruta_neo4j[0]["puntos_gps"]
    else:
        puntos_gps = [
            {"codigo": "BUE", "nombre": "Puerto Buenos Aires", "lat": -34.5885, "lon": -58.3702},
            {"codigo": "ROS", "nombre": "Centro Distribución Rosario", "lat": -32.9442, "lon": -60.6505},
            {"codigo": "COR", "nombre": "Hub Logístico Córdoba", "lat": -31.4201, "lon": -64.1888},
            {"codigo": "MDZ", "nombre": "Aduana Mendoza", "lat": -32.8277, "lon": -70.0706},
            {"codigo": "SCL", "nombre": "Puerto San Antonio (Santiago de Chile)", "lat": -33.5933, "lon": -71.6153}
        ]

    coleccion_lecturas = mongo_db["lecturas_sensores"]
    lecturas_previas = coleccion_lecturas.count_documents({"envio_id": id_envio, "contenedor_id": id_contenedor})
    indice = min(lecturas_previas // len(sensores_db), len(puntos_gps) - 1)
    nodo_actual = puntos_gps[indice]

    lat_real = round(nodo_actual["lat"] + random.uniform(-0.015, 0.015), 6)
    lon_real = round(nodo_actual["lon"] + random.uniform(-0.015, 0.015), 6)

    regla_temp = mongo_db["reglas_iot"].find_one({"parametro": "TEMPERATURA"})
    umbral_temp = regla_temp["umbral_maximo"] if regla_temp else 8.0

    ultimo_doc = None
    for s_id in sensores_db:
        ultima = coleccion_lecturas.find_one({"envio_id": id_envio, "sensor_id": s_id}, sort=[("timestamp", -1)])
        bateria_ant = ultima["metricas"].get("bateria_pct", 100) if (ultima and "metricas" in ultima) else 100
        bateria = max(5, bateria_ant - random.randint(1, 4))

        es_anomalia = random.random() < 0.20
        temperatura = round(random.uniform(umbral_temp + 2.0, 22.0) if es_anomalia else random.uniform(-18.0, umbral_temp - 1.0), 2)
        humedad = round(random.uniform(45.0, 75.0), 2)
        vibracion = round(random.uniform(0.02, 0.45), 2)
        alerta_disparada = temperatura > umbral_temp or bateria < 15

        documento = {
            "envio_id": id_envio,
            "contenedor_id": id_contenedor,
            "sensor_id": s_id,
            "timestamp": datetime.now(),
            "ubicacion_actual": nodo_actual["nombre"],
            "coordenadas_gps": {"lat": lat_real, "lon": lon_real},
            "metricas": {
                "temperatura_c": temperatura,
                "humedad_pct": humedad,
                "bateria_pct": bateria,
                "vibracion_g": vibracion
            },
            "alerta_anomalia": alerta_disparada
        }
        coleccion_lecturas.insert_one(documento)

        actualizar_ultima_posicion(
            id_sensor=s_id,
            id_contenedor=id_contenedor,
            id_envio=id_envio,
            lat=lat_real,
            lon=lon_real,
            hub_nombre=nodo_actual["nombre"],
            temp=temperatura,
            humedad=humedad,
            bateria=bateria
        )

        if temperatura > umbral_temp:
            registrar_alerta(s_id, f"EXCESO_TEMPERATURA ({temperatura}°C > {umbral_temp}°C)")
        if bateria < 15:
            registrar_alerta(s_id, f"BATERIA_CRITICA ({bateria}%)")

        ultimo_doc = documento

    ultimo_doc["sensores_procesados"] = sensores_db
    return ultimo_doc


# --- MÓDULO LOGÍSTICO Y OPERATIVO ---
def registrar_evento_logistico(id_envio, tipo_evento, ubicacion, descripcion):
    coleccion = mongo_db["eventos_logisticos"]
    documento = {
        "id_envio": id_envio,
        "fecha_y_hora": datetime.now(),
        "tipo_evento": tipo_evento,
        "ubicacion": ubicacion,
        "descripcion": descripcion
    }
    coleccion.insert_one(documento)
    print(f"✅ Evento Logístico ('{tipo_evento}') registrado para el Envío #{id_envio}.")

def obtener_historial_eventos(id_envio):
    coleccion = mongo_db["eventos_logisticos"]
    return list(coleccion.find({"id_envio": id_envio}).sort("fecha_y_hora", 1))

def registrar_incidente(id_envio, tipo_incidente, severidad, descripcion):
    coleccion = mongo_db["incidentes"]
    documento = {
        "id_envio": id_envio,
        "tipo": tipo_incidente,
        "fecha": datetime.now(),
        "severidad": severidad.upper(),
        "estado": "ABIERTO",
        "descripcion": descripcion
    }
    coleccion.insert_one(documento)
    print(f"🚨 Incidente de severidad {severidad.upper()} registrado para el Envío #{id_envio}.")

def obtener_incidentes_por_envio(id_envio):
    coleccion = mongo_db["incidentes"]
    return list(coleccion.find({"id_envio": id_envio}).sort("fecha", -1))

def registrar_alerta(id_sensor, tipo_alerta, estado="ACTIVA", id_evento=None):
    coleccion = mongo_db["alertas"]
    documento = {
        "id_sensor": id_sensor,
        "id_evento": id_evento,
        "tipo": tipo_alerta,
        "fecha": datetime.now(),
        "estado": estado
    }
    coleccion.insert_one(documento)
    print(f"⚠️ Alerta automática ('{tipo_alerta}') disparada por el Sensor #{id_sensor}.")


# --- MÓDULO PREDICTIVO DE ATRASOS Y RIESGOS ---
def registrar_prediccion_riesgo(id_envio, probabilidad_demora, riesgo_climatico, riesgo_operativo):
    """
    Calcula cuántos días adicionales puede atrasarse el envío en base a la probabilidad,
    el clima y el riesgo operativo, proyectando la nueva fecha estimada de llegada.
    """
    from config.database import get_pg_connection
    conn = get_pg_connection()
    cursor = conn.cursor()
    fecha_base_llegada = datetime.now() + timedelta(days=3)
    try:
        cursor.execute("SELECT fecha_de_llegada_estimada FROM tramo WHERE id_envio = %s LIMIT 1;", (id_envio,))
        row = cursor.fetchone()
        if row and row[0]:
            fecha_base_llegada = row[0]
    finally:
        cursor.close()
        conn.close()

    # Cálculo de días de atraso proyectados según porcentaje de demora y factores
    dias_atraso = round((probabilidad_demora / 20.0), 1)
    if "ALTO" in riesgo_climatico.upper():
        dias_atraso += 2.0
    if "ALTO" in riesgo_operativo.upper():
        dias_atraso += 1.5
    dias_atraso = round(dias_atraso, 1)

    fecha_estimada_con_atraso = fecha_base_llegada + timedelta(days=dias_atraso)

    coleccion = mongo_db["predicciones_riesgos"]
    documento = {
        "id_envio": id_envio,
        "probabilidad_demora": probabilidad_demora,
        "riesgo_climatico": riesgo_climatico,
        "riesgo_operativo": riesgo_operativo,
        "dias_atraso_estimados": dias_atraso,
        "fecha_calculo": datetime.now(),
        "fecha_llegada_proyectada": fecha_estimada_con_atraso
    }
    coleccion.insert_one(documento)
    print(f"📈 Predicción registrada para Envío #{id_envio}: Atraso estimado de +{dias_atraso} días (Nueva llegada proyectada: {fecha_estimada_con_atraso.strftime('%Y-%m-%d')}).")

def reporte_analisis_predictivos():
    """Devuelve TODAS las predicciones de atrasos y riesgos ordenadas por probabilidad."""
    coleccion = mongo_db["predicciones_riesgos"]
    return list(coleccion.find().sort("probabilidad_demora", -1))


# --- MÓDULO DE COMUNICACIÓN (Mensajes) ---
def enviar_mensaje(remitente, destinatario, contenido, tipo="TEXTO"):
    coleccion = mongo_db["mensajes"]
    documento = {
        "fecha_y_hora": datetime.now(),
        "remitente": remitente,
        "destinatario": destinatario,
        "contenido": contenido,
        "tipo": tipo
    }
    coleccion.insert_one(documento)
    print(f"💬 Comunicación enviada de '{remitente}' a '{destinatario}'.")

def obtener_mensajes(usuario_nombre=None):
    """Lista todo el historial de comunicaciones de la empresa con las partes."""
    coleccion = mongo_db["mensajes"]
    return list(coleccion.find().sort("fecha_y_hora", 1))


# --- MÓDULO DE REPORTES E INCIDENTES ---
def guardar_reporte(usuario_generador, tipo_reporte, contenido, formato="JSON"):
    coleccion = mongo_db["reportes"]
    documento = {
        "usuario": usuario_generador,
        "tipo": tipo_reporte,
        "fecha_generacion": datetime.now(),
        "contenido": contenido,
        "formato": formato,
        "estado": "GENERADO"
    }
    return coleccion.insert_one(documento).inserted_id

def reporte_incidentes_abiertos():
    coleccion = mongo_db["incidentes"]
    return list(coleccion.find({"estado": "ABIERTO"}).sort("fecha", -1))

def deteccion_anomalias_temperatura():
    coleccion = mongo_db["lecturas_sensores"]
    return list(coleccion.find({"alerta_anomalia": True}).sort("timestamp", -1).limit(10))

def ranking_rutas_incidentes():
    coleccion = mongo_db["incidentes"]
    pipeline = [
        {"$group": {"_id": "$id_envio", "total_incidentes": {"$sum": 1}}},
        {"$sort": {"total_incidentes": -1}},
        {"$limit": 5}
    ]
    return list(coleccion.aggregate(pipeline))

def abm_reglas_y_alertas_menu():
    from repositories.pg_repo import input_seguro
    while True:
        print("\n--- [ABM Reglas IoT y Alertas de Sensores (MongoDB)] ---")
        print("1. Crear / Modificar Regla de Umbral (Ej. Temperatura Máxima)")
        print("2. Listar Reglas Activas")
        print("3. Listar Alertas Disparadas por Sensores")
        print("4. Cambiar Estado de una Alerta (ACTIVA -> RESUELTA)")
        print("5. Volver")
        op = input_seguro("Elegí una opción (1-5): ")
        if op == "5":
            break
        if op == "1":
            param = input_seguro("Parámetro a controlar [TEMPERATURA / BATERIA / HUMEDAD]: ").upper() or "TEMPERATURA"
            umbral = float(input_seguro("Valor umbral límite (ej. 8.0 para °C): ") or 8.0)
            mongo_db["reglas_iot"].update_one(
                {"parametro": param},
                {"$set": {"umbral_maximo": umbral, "estado": "ACTIVA", "actualizado": datetime.now()}},
                upsert=True
            )
            print(f"✅ Regla para '{param}' configurada con umbral máximo de {umbral}.")
        elif op == "2":
            reglas = list(mongo_db["reglas_iot"].find())
            print("\n⚙️ [ REGLAS Y UMBRALES CONFIGURADOS ]")
            if not reglas: print("   ⚠️ No hay reglas cargadas.")
            for r in reglas: print(f"   - Parámetro: {r.get('parametro')} | Umbral Máx: {r.get('umbral_maximo')} | Estado: {r.get('estado')}")
        elif op == "3":
            alertas = list(mongo_db["alertas"].find().sort("fecha", -1))
            print("\n🔔 [ ALERTAS DE SENSORES IoT ]")
            if not alertas: print("   ✅ No hay alertas registradas.")
            for a in alertas: print(f"   - ID Sensor #{a.get('id_sensor')} | Tipo: {a.get('tipo')} | Estado: {a.get('estado')} | Fecha: {a.get('fecha').strftime('%Y-%m-%d %H:%M')}")
        elif op == "4":
            id_s = int(input_seguro("Ingresá el ID del Sensor cuya alerta querés marcar como RESUELTA: "))
            res = mongo_db["alertas"].update_many({"id_sensor": id_s, "estado": "ACTIVA"}, {"$set": {"estado": "RESUELTA"}})
            if res.modified_count > 0:
                print(f"✅ {res.modified_count} alerta(s) del Sensor #{id_s} marcadas como RESUELTAS.")
            else:
                print(f"⚠️ El Sensor #{id_s} no tenía alertas activas pendientes.")

def reporte_promedio_incidentes_multicriterio():
    from config.database import get_pg_connection
    incidentes = list(mongo_db["incidentes"].find())
    
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT e.id_envio, e.estado_envio, c.pais, c.razon_social
            FROM envio e
            JOIN cliente c ON e.id_cliente = c.id_cliente;
        """)
        envios_pg = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    if not envios_pg:
        return {}

    conteo_por_envio = {}
    for inc in incidentes:
        eid = inc.get("id_envio")
        conteo_por_envio[eid] = conteo_por_envio.get(eid, 0) + 1

    por_pais, por_estado, por_cliente = {}, {}, {}
    for eid, estado, pais, cliente in envios_pg:
        cant = conteo_por_envio.get(eid, 0)
        por_pais.setdefault(pais or "Argentina", []).append(cant)
        por_estado.setdefault(estado, []).append(cant)
        por_cliente.setdefault(cliente, []).append(cant)

    return {
        "por_pais": {k: round(sum(v)/len(v), 2) for k, v in por_pais.items()},
        "por_estado": {k: round(sum(v)/len(v), 2) for k, v in por_estado.items()},
        "por_cliente": {k: round(sum(v)/len(v), 2) for k, v in por_cliente.items()}
    }