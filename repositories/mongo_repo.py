from config.database import mongo_db
from datetime import datetime
import random

# --- MÓDULO IoT Y TELEMETRÍA (Lecturas) ---


def generar_lectura_automatica(id_envio, contenedor_id):
    """Genera una lectura IoT simulada con rutas geográficas lógicas según el tipo de transporte."""
    from config.database import get_pg_connection
    
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT origen_envio, destino_envio, estado_envio, prioridad FROM envio WHERE id_envio = %s;", (id_envio,))
        envio_info = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
        
    origen = "Buenos Aires"
    destino = "Rosario"
    estado = "EN_TRANSITO"
    prioridad = "MEDIA"
    
    if envio_info:
        origen, destino, estado, prioridad = envio_info[0], envio_info[1], envio_info[2], envio_info[3]

    if estado == "ENTREGADO":
        ubicacion_actual = destino.split(",")[0].strip()
    else:
        # Detectamos el tipo de ruta según los puntos geográficos
        is_transoceanico = "España" in destino or "Madrid" in destino
        is_maritimo_patagonico = "Malvinas" in origen or "Atlántico" in origen or "Malvinas" in destino
        
        if is_transoceanico:
            escala_1 = origen.split(",")[0].strip()
            escala_2 = "Aduana de Salida Internacional"
            escala_3 = "En Vuelo Transatlántico (Aéreo - Avión)" if prioridad.upper() == "ALTA" else "En Tránsito Marítimo (Buque de Carga)"
            destino_limpio = destino.split(",")[0].strip()
            secuencia_ruta = [escala_1, escala_2, escala_3, destino_limpio]
            
        elif is_maritimo_patagonico:
            # Ruta marítima coherente desde Malvinas hacia el puerto de Buenos Aires pasando por la costa
            origen_limpio = origen.split(",")[0].strip()
            escala_1 = "Puerto de Comodoro Rivadavia (Chubut)"
            escala_2 = "Costa Atlántica / Zona de Exclusión Marítima"
            destino_limpio = destino.split(",")[0].strip()
            secuencia_ruta = [origen_limpio, escala_1, escala_2, destino_limpio]
            
        else:
            # Ruta terrestre nacional estándar (Ej: Buenos Aires -> Mendoza)
            origen_limpio = origen.split(",")[0].strip()
            destino_limpio = destino.split(",")[0].strip()
            secuencia_ruta = [origen_limpio, "Córdoba", "San Luis", destino_limpio]

        coleccion_lecturas = mongo_db["lecturas_sensores"]
        total_lecturas_previas = coleccion_lecturas.count_documents({"envio_id": id_envio})
        
        indice_ruta = min(total_lecturas_previas, len(secuencia_ruta) - 1)
        ubicacion_actual = secuencia_ruta[indice_ruta]
        
        # Actualización automática a ENTREGADO si llega al último punto
        if indice_ruta >= len(secuencia_ruta) - 1 and estado != "ENTREGADO":
            conn_pg = get_pg_connection()
            cur_pg = conn_pg.cursor()
            try:
                cur_pg.execute("UPDATE envio SET estado_envio = 'ENTREGADO' WHERE id_envio = %s;", (id_envio,))
                conn_pg.commit()
                print(f"\n🎉 [ACT AUTOMÁTICA]: El Envío #{id_envio} ha completado su ruta y ahora figura como ENTREGADO.")
            except Exception as e:
                conn_pg.rollback()
            finally:
                cur_pg.close()
                conn_pg.close()

    es_anomalia = random.random() < 0.10 
    temperatura = round(random.uniform(15.0, 25.0) if es_anomalia else random.uniform(-20.0, 4.0), 2)
    humedad = round(random.uniform(40.0, 80.0), 2)
    vibracion = round(random.uniform(0.01, 0.50), 2)
    bateria = max(20, int(100 - random.randint(1, 5))) 
    
    lectura_simulada = {
        "envio_id": id_envio,
        "contenedor_id": contenedor_id,
        "timestamp": datetime.utcnow(),
        "ubicacion_actual": ubicacion_actual, 
        "metricas": {
            "temperatura_c": temperatura,
            "humedad_pct": humedad,
            "bateria_pct": bateria,
            "vibracion_g": vibracion
        },
        "alerta_anomalia": es_anomalia 
    }
    return lectura_simulada

def guardar_lectura_iot(contenedor_id, envio_id, ubicacion_actual, metricas, alerta_anomalia=False):
    """Inserta un documento de telemetría IoT simplificado en MongoDB vinculado al grafo."""
    coleccion = mongo_db["lecturas_sensores"]
    documento = {
        "envio_id": envio_id,
        "contenedor_id": contenedor_id,
        "timestamp": datetime.utcnow(),
        "ubicacion_actual": ubicacion_actual,
        "metricas": metricas,
        "alerta_anomalia": alerta_anomalia
    }
    resultado = coleccion.insert_one(documento)
    return resultado.inserted_id


# --- MÓDULO LOGÍSTICO Y OPERATIVO (Nuevas Entidades) ---

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
        "probabilidad_demora": probabilidad_demora, # Ej: 75.5 (porcentaje)
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

    # Construimos la condición de búsqueda base (por nombre)
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


# --- MÓDULO DE REPORTES (Documental) ---

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


# --- REPORTES OPERATIVOS Y ANALÍTICOS (MONGODB) ---

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












