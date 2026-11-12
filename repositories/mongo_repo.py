from config.database import mongo_db
from repositories.redis_repo import actualizar_ultima_posicion
from datetime import datetime, timedelta
import random

# --- MÓDULO IoT Y TELEMETRÍA ---
def evaluar_regla_parametro(parametro, valor_actual, default_max=None, default_min=None):
    """Evalúa si un valor viola la regla activa en MongoDB según sea MAXIMO o MINIMO."""
    regla = mongo_db["reglas_iot"].find_one({"parametro": parametro, "estado": "ACTIVA"})
    if regla:
        condicion = regla.get("condicion", "MAXIMO")
        umbral = regla.get("umbral", 0.0)
        if condicion == "MAXIMO" and valor_actual > umbral:
            return True, f"EXCESO_{parametro} ({valor_actual} > {umbral})"
        elif condicion == "MINIMO" and valor_actual < umbral:
            return True, f"BAJO_{parametro} ({valor_actual} < {umbral})"
        return False, None
    else:
        if default_max is not None and valor_actual > default_max:
            return True, f"EXCESO_{parametro} ({valor_actual} > {default_max})"
        if default_min is not None and valor_actual < default_min:
            return True, f"BAJA_{parametro} ({valor_actual} < {default_min})"
        return False, None

def generar_lectura_iot_coordenadas(id_envio, id_contenedor, id_sensor=None):
    """
    Busca automáticamente los sensores asociados al contenedor en PostgreSQL,
    calcula las coordenadas GPS reales en base a la ruta de Neo4j y actualiza Redis y MongoDB.
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
    umbral_temp = regla_temp.get("umbral", 8.0) if regla_temp else 8.0

    ultimo_doc = None
    for s_id in sensores_db:
        ultima = coleccion_lecturas.find_one({"envio_id": id_envio, "sensor_id": s_id}, sort=[("timestamp", -1)])
        bateria_ant = ultima["metricas"].get("bateria_pct", 100) if (ultima and "metricas" in ultima) else 100
        bateria = max(5, bateria_ant - random.randint(1, 4))

        es_anomalia = random.random() < 0.20
        temperatura = round(random.uniform(umbral_temp + 2.0, 22.0) if es_anomalia else random.uniform(-18.0, umbral_temp - 1.0), 2)
        humedad = round(random.uniform(45.0, 75.0), 2)
        vibracion = round(random.uniform(0.02, 0.45), 2)

        viola_temp, msg_temp = evaluar_regla_parametro("TEMPERATURA", temperatura, default_max=8.0)
        viola_bat, msg_bat = evaluar_regla_parametro("BATERIA", bateria, default_min=15.0)
        viola_hum, msg_hum = evaluar_regla_parametro("HUMEDAD", humedad)

        alerta_disparada = viola_temp or viola_bat or viola_hum

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

        if viola_temp:
            registrar_alerta(s_id, msg_temp)
        if viola_bat:
            registrar_alerta(s_id, msg_bat)
        if viola_hum:
            registrar_alerta(s_id, msg_hum)

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
    print(f"⚠️ Alerta ('{tipo_alerta}') registrada como ACTIVA para el Sensor #{id_sensor}.")


# --- MÓDULO PREDICTIVO DE ATRASOS Y RIESGOS ---
def registrar_prediccion_riesgo(id_envio, probabilidad_demora, riesgo_climatico, riesgo_operativo):
    """
    Obtiene la fecha de entrega original del tramo en PostgreSQL y calcula la nueva fecha
    de entrega estimada (con fecha y hora) en base al riesgo climático, operativo y probabilidad.
    """
    from config.database import get_pg_connection
    conn = get_pg_connection()
    cursor = conn.cursor()
    fecha_entrega_original = datetime.now() + timedelta(days=3)
    try:
        cursor.execute("SELECT fecha_de_llegada_estimada FROM tramo WHERE id_envio = %s LIMIT 1;", (id_envio,))
        row = cursor.fetchone()
        if row and row[0]:
            fecha_entrega_original = row[0]
    finally:
        cursor.close()
        conn.close()

    horas_atraso = round((probabilidad_demora / 100.0) * 72)  # Hasta 72hs base según probabilidad
    if "ALTO" in riesgo_climatico.upper():
        horas_atraso += 48
    elif "MEDIO" in riesgo_climatico.upper():
        horas_atraso += 24

    if "ALTO" in riesgo_operativo.upper():
        horas_atraso += 36
    elif "MEDIO" in riesgo_operativo.upper():
        horas_atraso += 12

    nueva_fecha_entrega = fecha_entrega_original + timedelta(hours=horas_atraso)

    coleccion = mongo_db["predicciones_riesgos"]
    documento = {
        "id_envio": id_envio,
        "probabilidad_demora": probabilidad_demora,
        "riesgo_climatico": riesgo_climatico,
        "riesgo_operativo": riesgo_operativo,
        "fecha_entrega_original": fecha_entrega_original,
        "fecha_llegada_proyectada": nueva_fecha_entrega,
        "fecha_calculo": datetime.now()
    }
    coleccion.insert_one(documento)
    orig_str = fecha_entrega_original.strftime("%Y-%m-%d %H:%M")
    nueva_str = nueva_fecha_entrega.strftime("%Y-%m-%d %H:%M")
    print(f"📈 Predicción registrada para Envío #{id_envio}:")
    print(f"   fecha de entrega original: ({orig_str}) -> nueva fecha de entrega estimada: ({nueva_str})")

def reporte_analisis_predictivos():
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
    coleccion = mongo_db["mensajes"]
    return list(coleccion.find().sort("fecha_y_hora", 1))


# --- MÓDULO DE REPORTES, REGLAS IoT Y ALERTAS ---
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
    """Permite crear reglas, modificar reglas existentes, registrar alertas manuales contextuales y resolverlas."""
    from repositories.pg_repo import input_seguro, normalizar_nombre_ubicacion
    from config.database import get_pg_connection

    while True:
        print("\n--- [ABM Reglas IoT y Alertas de Sensores (MongoDB)] ---")
        print("1. Crear Nueva Regla de Umbral IoT (Definir Umbral Mínimo o Máximo)")
        print("2. Modificar una Regla Existente")
        print("3. Listar Reglas Configuradas")
        print("4. Registrar Alerta de Sensor Manualmente (Contextual según tipo de sensor)")
        print("5. Listar Alertas Disparadas por Sensores")
        print("6. Cambiar Estado de una Alerta (ACTIVA -> RESUELTA)")
        print("7. Volver")
        op = input_seguro("Elegí una opción (1-7): ")
        if op == "7":
            break

        if op == "1":
            print("\nParámetros disponibles: 1. TEMPERATURA | 2. HUMEDAD | 3. BATERIA")
            p_op = input_seguro("Seleccioná el parámetro (1-3): ")
            param = {"1": "TEMPERATURA", "2": "HUMEDAD", "3": "BATERIA"}.get(p_op, "TEMPERATURA")

            print("¿Qué condición dispara la alerta?")
            print("  1. MAXIMO (Dispara alerta si la lectura SUPERA el umbral, ej. Exceso Temperatura)")
            print("  2. MINIMO (Dispara alerta si la lectura CAE POR DEBAJO del umbral, ej. Batería Baja)")
            c_op = input_seguro("Seleccioná condición (1-2): ")
            condicion = "MINIMO" if c_op == "2" else "MAXIMO"

            umbral = float(input_seguro(f"Valor del umbral ({condicion}) para {param}: ") or 10.0)
            mongo_db["reglas_iot"].update_one(
                {"parametro": param, "condicion": condicion},
                {"$set": {
                    "parametro": param,
                    "condicion": condicion,
                    "umbral": umbral,
                    "estado": "ACTIVA",
                    "actualizado": datetime.now()
                }},
                upsert=True
            )
            simbolo = ">" if condicion == "MAXIMO" else "<"
            print(f"✅ Regla creada: Alerta si {param} {simbolo} {umbral} (Condición: {condicion}).")

        elif op == "2":
            reglas = list(mongo_db["reglas_iot"].find())
            if not reglas:
                print("   ⚠️ No hay reglas creadas para modificar.")
                continue
            print("\n⚙️ [ SELECCIONÁ LA REGLA A MODIFICAR ]")
            for idx, r in enumerate(reglas, 1):
                cond = r.get("condicion", "MAXIMO")
                val = r.get("umbral", r.get("umbral_maximo", 0))
                print(f"   {idx}. Parámetro: {r.get('parametro')} | Condición: {cond} | Umbral actual: {val} | Estado: {r.get('estado')}")
            
            sel = input_seguro(f"Ingresá el número de regla a modificar (1-{len(reglas)}): ")
            if not sel.isdigit() or not (1 <= int(sel) <= len(reglas)):
                print("❌ Selección inválida.")
                continue
            regla_elegida = reglas[int(sel) - 1]
            cond_actual = regla_elegida.get("condicion", "MAXIMO")
            val_actual = regla_elegida.get("umbral", regla_elegida.get("umbral_maximo", 0))

            print(f"Condición actual: [{cond_actual}] (1. MAXIMO | 2. MINIMO | Enter para mantener)")
            c_in = input_seguro("Nueva condición: ")
            nueva_cond = "MAXIMO" if c_in == "1" else ("MINIMO" if c_in == "2" else cond_actual)

            u_in = input_seguro(f"Nuevo valor de umbral [{val_actual}] (Enter para mantener): ")
            nuevo_umbral = float(u_in) if u_in else val_actual

            print(f"Estado actual: [{regla_elegida.get('estado', 'ACTIVA')}] (1. ACTIVA | 2. INACTIVA | Enter para mantener)")
            e_in = input_seguro("Nuevo estado: ")
            nuevo_est = "ACTIVA" if e_in == "1" else ("INACTIVA" if e_in == "2" else regla_elegida.get("estado", "ACTIVA"))

            mongo_db["reglas_iot"].update_one(
                {"_id": regla_elegida["_id"]},
                {"$set": {
                    "condicion": nueva_cond,
                    "umbral": nuevo_umbral,
                    "estado": nuevo_est,
                    "actualizado": datetime.now()
                }}
            )
            print(f"✅ Regla de '{regla_elegida.get('parametro')}' actualizada correctamente.")

        elif op == "3":
            reglas = list(mongo_db["reglas_iot"].find())
            print("\n⚙️ [ REGLAS Y UMBRALES CONFIGURADOS ]")
            if not reglas:
                print("   ⚠️ No hay reglas cargadas.")
            for r in reglas:
                cond = r.get("condicion", "MAXIMO")
                val = r.get("umbral", r.get("umbral_maximo", 0))
                simbolo = "Máx (>)" if cond == "MAXIMO" else "Mín (<)"
                print(f"   - Parámetro: {r.get('parametro')} | Condición: {cond} | Umbral {simbolo}: {val} | Estado: {r.get('estado')}")

        elif op == "4":
            conn = get_pg_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT s.id_sensor, s.tipo_sensor, s.estado_sensor,
                           c.id_contenedor, c.codigo_internacional,
                           e.id_envio, e.origen_envio, e.destino_envio
                    FROM sensor_iot s
                    JOIN contenedor c ON s.id_contenedor = c.id_contenedor
                    JOIN envio e ON c.id_envio = e.id_envio
                    ORDER BY s.id_sensor ASC;
                """)
                sensores = cursor.fetchall()
                if not sensores:
                    print("   ⚠️ No hay sensores registrados.")
                    continue
                print("\n📡 [ LISTADO DE ENVÍOS, CONTENEDORES Y SENSORES ]")
                mapa_sensores = {}
                for s in sensores:
                    est_s = "ACTIVO" if s[2] else "INACTIVO"
                    orig = normalizar_nombre_ubicacion(s[6])
                    dest = normalizar_nombre_ubicacion(s[7])
                    print(f"   - Sensor ID #{s[0]} ({s[1]} - {est_s}) | Contenedor #{s[3]} ({s[4]}) | Envío #{s[5]} ({orig} -> {dest})")
                    mapa_sensores[s[0]] = s[1]

                id_s = int(input_seguro("\nIngresá el ID del Sensor para registrar la alerta: "))
                if id_s not in mapa_sensores:
                    print(f"❌ Error: No existe el Sensor con ID #{id_s}.")
                    continue

                tipo_sensor_db = mapa_sensores[id_s].upper()
                if "TEMPERATURA" in tipo_sensor_db:
                    opciones_alerta = [
                        "EXCESO_TEMPERATURA",
                        "BAJA_TEMPERATURA",
                        "NO_REGISTRA_TEMPERATURA",
                        "BATERIA_BAJA_O_SIN_SENAL_GPS"
                    ]
                elif "HUMEDAD" in tipo_sensor_db:
                    opciones_alerta = [
                        "EXCESO_HUMEDAD",
                        "BAJA_HUMEDAD",
                        "NO_REGISTRA_HUMEDAD",
                        "BATERIA_BAJA_O_SIN_SENAL_GPS"
                    ]
                else:
                    opciones_alerta = [
                        "EXCESO_TEMPERATURA_O_HUMEDAD",
                        "VIBRACION_EXCESIVA_GOLPE",
                        "PERDIDA_SENAL_GPS",
                        "BATERIA_CRITICA"
                    ]

                print(f"\nTipos de Alerta disponibles para el Sensor #{id_s} ({tipo_sensor_db}):")
                for idx, nombre_al in enumerate(opciones_alerta, 1):
                    print(f"   {idx}. {nombre_al}")
                
                op_al = input_seguro(f"Seleccioná el tipo de alerta (1-{len(opciones_alerta)}): ")
                idx_al = int(op_al) - 1 if (op_al.isdigit() and 1 <= int(op_al) <= len(opciones_alerta)) else 0
                alerta_elegida = opciones_alerta[idx_al]

                registrar_alerta(id_s, alerta_elegida, estado="ACTIVA")
            finally:
                cursor.close()
                conn.close()

        elif op == "5":
            alertas = list(mongo_db["alertas"].find().sort("fecha", -1))
            print("\n🔔 [ ALERTAS DE SENSORES IoT ]")
            if not alertas:
                print("   ✅ No hay alertas registradas.")
            for a in alertas:
                f_str = a.get("fecha").strftime("%Y-%m-%d %H:%M:%S") if a.get("fecha") else "N/A"
                print(f"   - ID Sensor #{a.get('id_sensor')} | Tipo: {a.get('tipo')} | Estado: {a.get('estado')} | Fecha: {f_str}")

        elif op == "6":
            alertas_activas = list(mongo_db["alertas"].find({"estado": "ACTIVA"}).sort("fecha", -1))
            if not alertas_activas:
                print("   ✅ No hay alertas ACTIVAS pendientes de resolver.")
                continue
            print("\n🔔 [ ALERTAS ACTIVAS ]")
            for a in alertas_activas:
                print(f"   - Sensor ID #{a.get('id_sensor')} | Tipo: {a.get('tipo')} | Fecha: {a.get('fecha').strftime('%Y-%m-%d %H:%M')}")
            id_s = int(input_seguro("Ingresá el ID del Sensor cuya alerta querés marcar como RESUELTA: "))
            res = mongo_db["alertas"].update_many({"id_sensor": id_s, "estado": "ACTIVA"}, {"$set": {"estado": "RESUELTA"}})
            if res.modified_count > 0:
                print(f"✅ {res.modified_count} alerta(s) del Sensor #{id_s} marcadas como RESUELTAS.")
            else:
                print(f"⚠️ El Sensor #{id_s} no tenía alertas activas.")

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