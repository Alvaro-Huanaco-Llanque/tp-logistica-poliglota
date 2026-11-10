from config.database import mongo_db
from repositories.redis_repo import actualizar_ultima_posicion
from datetime import datetime
import random

# --- MÓDULO IoT Y TELEMETRÍA (sensor) ---

def generar_lectura_iot_coordenadas(id_envio, id_contenedor, id_sensor=1):
    """
    Obtiene los Hubs de Neo4j para el envío, calcula la coordenada (lat, lon) real,
    actualiza Redis en tiempo real y persiste el histórico en MongoDB.
    """
    from config.database import get_pg_connection
    from repositories.neo4j_repo import buscar_camino_optimo

    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT origen_envio, destino_envio, estado_envio FROM envio WHERE id_envio = %s;", (id_envio,))
        envio_info = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    origen = envio_info[0] if envio_info else "BUE"
    destino = envio_info[1] if envio_info else "SCL"
    estado_envio = envio_info[2] if envio_info else "EN_TRANSITO"

    ruta_neo4j = buscar_camino_optimo(origen, destino)
    if ruta_neo4j and len(ruta_neo4j[0]["puntos_gps"]) > 0:
        puntos_gps = ruta_neo4j[0]["puntos_gps"]
    else:
        # Fallback con coordenadas reales si no matchea el nombre exacto
        puntos_gps = [
            {"codigo": "BUE", "nombre": "Puerto Buenos Aires", "lat": -34.5885, "lon": -58.3702},
            {"codigo": "ROS", "nombre": "Centro Distribución Rosario", "lat": -32.9442, "lon": -60.6505},
            {"codigo": "COR", "nombre": "Hub Logístico Córdoba", "lat": -31.4201, "lon": -64.1888},
            {"codigo": "MDZ", "nombre": "Aduana Mendoza", "lat": -32.8277, "lon": -70.0706},
            {"codigo": "SCL", "nombre": "Puerto San Antonio Chile", "lat": -33.5933, "lon": -71.6153}
        ]

    coleccion_lecturas = mongo_db["lecturas_sensores"]
    lecturas_previas = coleccion_lecturas.count_documents({"envio_id": id_envio})
    indice = min(lecturas_previas, len(puntos_gps) - 1)
    nodo_actual = puntos_gps[indice]

    # Pequeña deriva GPS realista si está en tránsito entre nodos
    lat_real = round(nodo_actual["lat"] + random.uniform(-0.015, 0.015), 6)
    lon_real = round(nodo_actual["lon"] + random.uniform(-0.015, 0.015), 6)

    # Batería descendente
    ultima = coleccion_lecturas.find_one({"envio_id": id_envio}, sort=[("timestamp", -1)])
    bateria_ant = ultima["metricas"].get("bateria_pct", 100) if (ultima and "metricas" in ultima) else 100
    bateria = max(5, bateria_ant - random.randint(1, 4))

    # Consultar regla de temperatura activa en MongoDB
    regla_temp = mongo_db["reglas_iot"].find_one({"parametro": "TEMPERATURA"})
    umbral_temp = regla_temp["umbral_maximo"] if regla_temp else 8.0

    es_anomalia = random.random() < 0.20
    temperatura = round(random.uniform(umbral_temp + 2.0, 22.0) if es_anomalia else random.uniform(-18.0, umbral_temp - 1.0), 2)
    humedad = round(random.uniform(45.0, 75.0), 2)
    vibracion = round(random.uniform(0.02, 0.45), 2)

    alerta_disparada = temperatura > umbral_temp or bateria < 15

    # 1. Guardar en MongoDB (Histórico)
    documento = {
        "envio_id": id_envio,
        "contenedor_id": id_contenedor,
        "sensor_id": id_sensor,
        "timestamp": datetime.utcnow(),
        "ubicacion_actual": nodo_actual["nombre"],
        "coordenadas_gps": {
            "lat": lat_real,
            "lon": lon_real
        },
        "metricas": {
            "temperatura_c": temperatura,
            "humedad_pct": humedad,
            "bateria_pct": bateria,
            "vibracion_g": vibracion
        },
        "alerta_anomalia": alerta_disparada
    }
    coleccion_lecturas.insert_one(documento)

    # 2. Actualizar Redis (Caché de última posición GPS real)
    actualizar_ultima_posicion(
        id_sensor=id_sensor,
        id_contenedor=id_contenedor,
        id_envio=id_envio,
        lat=lat_real,
        lon=lon_real,
        hub_nombre=nodo_actual["nombre"],
        temp=temperatura,
        humedad=humedad,
        bateria=bateria
    )

    # 3. Si viola umbral, generar alerta automática e incidente
    if temperatura > umbral_temp:
        registrar_alerta(id_sensor, f"EXCESO_TEMPERATURA ({temperatura}°C > {umbral_temp}°C)")
    if bateria < 15:
        registrar_alerta(id_sensor, f"BATERIA_CRITICA ({bateria}%)")

    return documento



# --- MÓDULO LOGÍSTICO Y OPERATIVO ---
def registrar_evento_logistico(id_envio, tipo_evento, ubicacion, descripcion):
    """Registra un evento en la bitácora del viaje (Ej: 'Carga iniciada', 'Aduana')."""
    coleccion = mongo_db["eventos_logisticos"]
    documento = {
        "id_envio": id_envio,
        "fecha_y_hora": datetime.utcnow(),
        "tipo_evento": tipo_evento,
        "ubicacion": ubicacion,
        "descripcion": descripcion
    }
    coleccion.insert_one(documento)
    print(f"✅ Evento Logístico ('{tipo_evento}') registrado para el Envío #{id_envio}.")

def obtener_historial_eventos(id_envio):
    """Devuelve todos los eventos de un envío ordenados por el más reciente."""
    coleccion = mongo_db["eventos_logisticos"]
    return list(coleccion.find({"id_envio": id_envio}).sort("fecha_y_hora", -1))

def registrar_incidente(id_envio, tipo_incidente, severidad, descripcion):
    """Registra un problema o incidente grave (Ej: 'Falla mecánica', 'Climático')."""
    coleccion = mongo_db["incidentes"]
    documento = {
        "id_envio": id_envio,
        "tipo": tipo_incidente,
        "fecha": datetime.utcnow(),
        "severidad": severidad.upper(), # ALTA, MEDIA, BAJA
        "estado": "ABIERTO",            # Por defecto arranca abierto
        "descripcion": descripcion
    }
    coleccion.insert_one(documento)
    print(f"🚨 Incidente de severidad {severidad.upper()} registrado para el Envío #{id_envio}.")

def obtener_incidentes_por_envio(id_envio):
    """Devuelve los incidentes vinculados a un viaje específico."""
    coleccion = mongo_db["incidentes"]
    return list(coleccion.find({"id_envio": id_envio}).sort("fecha", -1))

def registrar_alerta(id_sensor, tipo_alerta, estado="ACTIVA", id_evento=None):
    """Guarda una alerta automática disparada por un sensor IoT."""
    coleccion = mongo_db["alertas"]
    documento = {
        "id_sensor": id_sensor,
        "id_evento": id_evento, # Puede ser nulo si no está atado a un evento manual
        "tipo": tipo_alerta,
        "fecha": datetime.utcnow(),
        "estado": estado
    }
    coleccion.insert_one(documento)
    print(f"⚠️ Alerta ('{tipo_alerta}') registrada para el Sensor #{id_sensor}.")

def registrar_prediccion_riesgo(id_envio, probabilidad_demora, riesgo_climatico, riesgo_operativo):
    """Registra el análisis predictivo de un trayecto (Analítica avanzada)."""
    coleccion = mongo_db["predicciones_riesgos"]
    documento = {
        "id_envio": id_envio,
        "probabilidad_demora": probabilidad_demora,
        "riesgo_climatico": riesgo_climatico,
        "riesgo_operativo": riesgo_operativo,
        "fecha_calculo": datetime.utcnow()
    }
    coleccion.insert_one(documento)
    print(f"📈 Predicción de riesgo calculada para el Envío #{id_envio} (Demora: {probabilidad_demora}%).")

def obtener_predicciones_envio(id_envio):
    coleccion = mongo_db["predicciones_riesgos"]
    return list(coleccion.find({"id_envio": id_envio}).sort("fecha_calculo", -1))


# --- MÓDULO DE COMUNICACIÓN (Mensajes) ---
def enviar_mensaje(remitente, destinatario, contenido, tipo="TEXTO"):
    """Guarda un mensaje en el historial del chat."""
    coleccion = mongo_db["mensajes"]
    documento = {
        "fecha_y_hora": datetime.utcnow(),
        "remitente": remitente,
        "destinatario": destinatario,
        "contenido": contenido,
        "tipo": tipo
    }
    coleccion.insert_one(documento)
    print(f"💬 Mensaje enviado de {remitente} a {destinatario}.")

def obtener_mensajes(usuario_nombre, usuario_email_o_cuit=None):
    """
    Recupera los mensajes donde el usuario actual es remitente o destinatario.
    Busca coincidencias parciales por el nombre, o exactas por email/cuit si se proporciona.
    """
    coleccion = mongo_db["mensajes"]
    
    import re
    regex_usuario = re.compile(f".*{usuario_nombre}.*", re.IGNORECASE)

    condiciones_or = [
        {"remitente": {"$regex": regex_usuario}}, 
        {"destinatario": {"$regex": regex_usuario}}
    ]

    # Si se pasa un email o CUIT, lo agregamos a las condiciones de búsqueda
    if usuario_email_o_cuit:
        condiciones_or.extend([
            {"remitente": usuario_email_o_cuit},
            {"destinatario": usuario_email_o_cuit}
        ])

    mensajes = list(coleccion.find({
        "$or": condiciones_or
    }).sort("fecha_y_hora", 1))
    
    return mensajes


# --- MÓDULO DE REPORTES ---
def guardar_reporte(usuario_generador, tipo_reporte, contenido, formato="JSON"):
    """Almacena un reporte analítico u operativo generado por un usuario."""
    coleccion = mongo_db["reportes"]
    documento = {
        "usuario": usuario_generador,
        "tipo": tipo_reporte,
        "fecha_generacion": datetime.utcnow(),
        "contenido": contenido,
        "formato": formato,
        "estado": "GENERADO"
    }
    resultado = coleccion.insert_one(documento)
    print(f"📊 Reporte de '{tipo_reporte}' guardado correctamente.")
    return resultado.inserted_id

def listar_reportes_usuario(usuario_generador):
    """Lista los reportes generados por un usuario."""
    coleccion = mongo_db["reportes"]
    return list(coleccion.find({"usuario": usuario_generador}).sort("fecha_generacion", -1))


# --- REPORTES OPERATIVOS Y ANALÍTICOS ---
def reporte_incidentes_abiertos():
    """Devuelve todos los incidentes que aún no han sido resueltos."""
    coleccion = mongo_db["incidentes"]
    return list(coleccion.find({"estado": "ABIERTO"}).sort("fecha", -1))

def reporte_analisis_predictivos():
    """Devuelve las predicciones de riesgo más críticas (probabilidad > 50%)."""
    coleccion = mongo_db["predicciones_riesgos"]
    return list(coleccion.find({"probabilidad_demora": {"$gt": 50}}).sort("probabilidad_demora", -1))

def reporte_promedio_incidentes_por_estado():
    """
    Usa el Aggregation Framework para agrupar incidentes por su severidad/estado 
    y sacar estadísticas analíticas.
    """
    coleccion = mongo_db["incidentes"]
    pipeline = [
        {"$group": {"_id": "$severidad", "total_incidentes": {"$sum": 1}}},
        {"$sort": {"total_incidentes": -1}}
    ]
    return list(coleccion.aggregate(pipeline))

def deteccion_anomalias_temperatura():
    """Reporte Operador: Trae las últimas lecturas IoT donde se disparó una alerta de anomalía."""
    coleccion = mongo_db["lecturas_sensores"]
    # Filtramos donde alerta_anomalia es True, ordenado por el más reciente
    return list(coleccion.find({"alerta_anomalia": True}).sort("timestamp", -1).limit(10))

def ranking_rutas_incidentes():
    """Reporte Operador: Agrupa los incidentes por Envío (Ruta) para ver cuáles son los más problemáticos."""
    coleccion = mongo_db["incidentes"]
    pipeline = [
        {"$group": {"_id": "$id_envio", "total_incidentes": {"$sum": 1}}},
        {"$sort": {"total_incidentes": -1}},
        {"$limit": 5}
    ]
    return list(coleccion.aggregate(pipeline))

def abm_reglas_y_alertas_menu():
    """Permite crear reglas de umbrales IoT, listar alertas de sensores y resolverlas."""
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
                {"$set": {"umbral_maximo": umbral, "estado": "ACTIVA", "actualizado": datetime.utcnow()}},
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
            for a in alertas: print(f"   - ID Sensor #{a.get('id_sensor')} | Tipo: {a.get('tipo')} | Estado: {a.get('estado')} | Fecha: {a.get('fecha')}")
        elif op == "4":
            id_s = int(input_seguro("Ingresá el ID del Sensor cuya alerta querés marcar como RESUELTA: "))
            mongo_db["alertas"].update_many({"id_sensor": id_s, "estado": "ACTIVA"}, {"$set": {"estado": "RESUELTA"}})
            print(f"✅ Alertas del Sensor #{id_s} marcadas como RESUELTAS.")

def reporte_promedio_incidentes_multicriterio():
    """Cruza incidentes de MongoDB con datos de Envío y Cliente de PostgreSQL para calcular promedios por País, Estado y Cliente."""
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










