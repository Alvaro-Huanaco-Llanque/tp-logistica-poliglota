from config.database import get_pg_connection, mongo_db
from repositories.pg_repo import (
    obtener_usuario_por_rol,
    registrar_inicio_sesion,
    cerrar_sesion_activa,
    abm_cliente_menu,
    abm_usuarios_y_sesiones_menu,
    abm_proveedores_menu,
    abm_operadores_logisticos_menu,
    abm_envio_contenedor_sensor_menu,
    registrar_envio_con_contenedores_cliente,
    consultar_cuenta_corriente,
    listar_clientes_deudores,
    ejecutar_cierre_mensual_cuentas,
    gestionar_pagos_proveedores_y_operadores_menu,
    reporte_envios_por_pais,
    reporte_envios_por_estado,
    reporte_envios_por_cliente,
    reporte_envios_demorados,
    reporte_tiempos_envio_por_cliente,
    reporte_tiempos_promedio_general,
    reporte_costos_por_tipo_transporte,
    ranking_clientes_por_volumen,
    analisis_historico_desempeno,
    listar_clientes_formateados,
    HUBS_PAIS,
    input_seguro
)
from repositories.mongo_repo import (
    generar_lectura_iot_coordenadas,
    registrar_evento_logistico,
    obtener_historial_eventos,
    registrar_incidente,
    obtener_incidentes_por_envio,
    abm_reglas_y_alertas_menu,
    deteccion_anomalias_temperatura,
    ranking_rutas_incidentes,
    reporte_incidentes_abiertos,
    reporte_analisis_predictivos,
    reporte_promedio_incidentes_multicriterio,
    registrar_prediccion_riesgo,
    enviar_mensaje,
    obtener_mensajes
)
from repositories.neo4j_repo import obtener_red_relaciones_grafo
from repositories.redis_repo import obtener_ultima_posicion_envio

ROLES_ERP = {
    1: "GERENTE_OPERACIONES (Gestión de Maestros, Usuarios y Comunicaciones)",
    2: "GESTOR_TRAFICO_IOT (Envíos, Contenedores, Rutas, Monitoreo GPS e Incidentes)",
    3: "ANALISTA_FINANZAS (Cuentas Corrientes, Facturación, Cobros y Pagos)",
    4: "ANALISTA_REPORTES (Reportes Operativos, Analíticos, Grafo y Predicciones)"
}

# Permisos estrictos por Rol: Cada rol solo ve y ejecuta sus módulos asignados
MODULOS_POR_ROL = {
    1: ["1", "5"],          # Gerente Operaciones: Maestros/Usuarios/Sesiones y Comunicaciones
    2: ["2", "3", "4", "5"],# Gestor Tráfico IoT: Envíos, Monitoreo GPS/Eventos, Alertas/Incidentes y Comunicaciones
    3: ["7", "5"],          # Analista Finanzas: Cuentas Corrientes/Facturación/Pagos y Comunicaciones
    4: ["6", "5"]           # Analista Reportes: Inteligencia Analítica/Predictiva/Grafo y Comunicaciones
}

def menu_principal():
    while True:
        print("\n==================================================================")
        print("   ERP INTERNO DE GESTIÓN LOGÍSTICA POLÍGLOTA (SELECCIÓN DE ROL)")
        print("==================================================================")
        print("Seleccioná el Rol Interno con el que deseás operar en la terminal:")
        print("  1. GERENTE_OPERACIONES (ABM Clientes, Proveedores, Operadores, Usuarios y Sesiones)")
        print("  2. GESTOR_TRAFICO_IOT  (Registro de Envíos, Sensores IoT, Eventos, Rutas y Alertas)")
        print("  3. ANALISTA_FINANZAS   (Cuentas Corrientes, Facturación, Cobros, Pagos y Cierre)")
        print("  4. ANALISTA_REPORTES   (Reportes Analíticos, Costos, Grafo Neo4j y Predicciones)")
        print("  5. Salir del Sistema")

        op = input("\nIngresá una opción (1-5): ").strip()

        if op in ["1", "2", "3", "4"]:
            rol_id = int(op)
            usuario = obtener_usuario_por_rol(rol_id)
            if not usuario:
                print("❌ No hay un empleado activo asignado a este rol. Ejecutá primero 'python seed_datos_prueba.py'.")
                continue
            usuario["id_sesion"] = registrar_inicio_sesion(usuario["id_usuario"])
            panel_central_erp(usuario)
        elif op == "5":
            print("👋 Cerrando ERP Logístico.")
            break
        else:
            print("⚠️ Opción inválida.")

def panel_central_erp(usuario):
    rol_id = usuario["id_rol"]
    rol_nombre = ROLES_ERP.get(rol_id, "OPERADOR_ERP")
    permitidos = MODULOS_POR_ROL.get(rol_id, [])

    catalogo_modulos = {
        "1": "[Módulo 1] Gestión de Maestros: Clientes, Proveedores, Operadores, Usuarios y Sesiones",
        "2": "[Módulo 2] Registro de Envíos, Contenedores, Sensores y Tramos",
        "3": "[Módulo 3 y 8] Monitoreo IoT (Coordenadas GPS en Redis/Mongo), Recorridos y Trazabilidad",
        "4": "[Módulo 4] Reglas IoT, Detección de Incidentes, Anomalías y Alertas Automáticas",
        "5": "[Módulo 5] Centro de Comunicaciones con Clientes, Proveedores y Operadores",
        "6": "[Módulo 6 y 9] Reportes Operativos, Analíticos, Grafo de Relaciones y Predicciones",
        "7": "[Módulo 7] Finanzas ACID: Cuentas Corrientes, Facturación y Pagos (Clientes/Proveedores/Operadores)"
    }

    while True:
        print("\n==================================================================")
        print(f"   EMPLEADO ACTIVO: {usuario['nombre']} | Sesión #{usuario['id_sesion']}")
        print(f"   ROL: {rol_nombre}")
        print("==================================================================")
        print("Módulos habilitados para tu Rol:")
        for cod in permitidos:
            print(f"  {cod}. {catalogo_modulos[cod]}")
        print("  8. Cerrar Sesión (Cambiar de Rol)")

        op = input_seguro("\nSeleccioná el número de módulo a operar: ")

        if op == "8":
            cerrar_sesion_activa(usuario["id_sesion"])
            print(f"🔒 Sesión #{usuario['id_sesion']} cerrada y registrada en el historial.")
            break

        if op not in permitidos:
            print(f"⛔ Acceso denegado: Tu rol ({rol_nombre.split()[0]}) no tiene permisos para operar ese módulo.")
            continue

        if op == "1": modulo_1_maestros()
        elif op == "2": modulo_2_envios_contenedores()
        elif op == "3": modulo_3_monitoreo_iot_y_trazabilidad()
        elif op == "4": modulo_4_incidentes_y_alertas()
        elif op == "5": modulo_5_comunicaciones(usuario)
        elif op == "6": modulo_6_y_9_reportes_y_predicciones(usuario)
        elif op == "7": modulo_7_finanzas()

def modulo_1_maestros():
    while True:
        print("\n--- [MÓDULO 1: ABM MAESTROS Y SEGURIDAD] ---")
        print("1. ABM Clientes (Empresas que contratan fletes)")
        print("2. ABM Proveedores (Proveedores de Contenedores, Sensores y Flota)")
        print("3. ABM Operadores Logísticos (Personal de Puerto, Aduana, Última Milla)")
        print("4. ABM Usuarios Internos, Roles y Auditoría de Sesiones")
        print("5. Volver")
        sub = input_seguro("Opción (1-5): ")
        if sub == "1": abm_cliente_menu()
        elif sub == "2": abm_proveedores_menu()
        elif sub == "3": abm_operadores_logisticos_menu()
        elif sub == "4": abm_usuarios_y_sesiones_menu()
        elif sub == "5": break

def modulo_2_envios_contenedores():
    while True:
        print("\n--- [MÓDULO 2: REGISTRO DE ENVÍOS, CONTENEDORES Y SENSORES] ---")
        print("1. Registrar Nuevo Envío solicitado por un Cliente")
        print("2. ABM de Contenedores, Sensores IoT y Cambio de Estados (Entrega y Facturación)")
        print("3. Volver")
        sub = input_seguro("Opción (1-3): ")
        if sub == "1":
            conn = get_pg_connection()
            cursor = conn.cursor()
            try:
                listar_clientes_formateados()
                id_cli = int(input_seguro("\nIngresá únicamente el ID del Cliente que solicita el envío: "))

                print("\nPuntos Logísticos (Hubs) de la red:")
                print("  Argentina: BUE (Puerto BsAs) | EZE (Ezeiza) | ROS (Rosario) | COR (Córdoba) | MDZ (Aduana Mendoza)")
                print("  Exterior : SCL (Puerto San Antonio, Chile) | MAD (Aeropuerto Barajas, España)")
                origen = input_seguro("Código Hub de Origen [Ej: BUE]: ").upper() or "BUE"
                destino = input_seguro("Código Hub de Destino [Ej: SCL]: ").upper() or "SCL"
                prioridad = input_seguro("Prioridad [ALTA / MEDIA / BAJA]: ").upper() or "MEDIA"

                pais_o = HUBS_PAIS.get(origen, "Argentina")
                pais_d = HUBS_PAIS.get(destino, "Exterior")
                es_internacional = (pais_o != pais_d) or destino in ["SCL", "MAD"]

                id_operador = None
                if es_internacional:
                    print(f"\n🌐 Trayecto INTERNACIONAL detectado ({origen} [{pais_o}] -> {destino} [{pais_d}]).")
                    print("Se requiere asignar un Operador Logístico para trámites aduaneros y portuarios:")
                    cursor.execute("SELECT id_operador, nombre_completo, especialidad FROM operador_logistico WHERE estado = 'ACTIVO';")
                    ops = cursor.fetchall()
                    for o in ops:
                        print(f"   - ID #{o[0]}: {o[1]} | Especialidad: {o[2]}")
                    id_operador = int(input_seguro("Seleccioná el ID del Operador Logístico: ") or (ops[0][0] if ops else 1))
                else:
                    print(f"\n🚛 Trayecto NACIONAL TERRESTRE detectado ({origen} -> {destino}). No requiere Operador Aduanero/Portuario.")

                # Listado de proveedores para asociar a los contenedores y sensores
                cursor.execute("SELECT id_proveedor, razon_social, tipo_insumo FROM proveedor WHERE estado = 'ACTIVO' ORDER BY id_proveedor;")
                provs = cursor.fetchall()
                print("\nProveedores de Insumos registrados:")
                for p in provs:
                    print(f"   - ID #{p[0]}: {p[1]} (Rubro: {p[2]})")

                contenedores = []
                while True:
                    print(f"\n--- Configurando Contenedor #{len(contenedores) + 1} ---")
                    cod = input_seguro("Código Internacional Contenedor [Ej: MSKU-9012]: ") or f"MSKU-{1000 + len(contenedores)}"
                    tipo_c = input_seguro("Tipo de Contenedor [REFRIGERADO / ESTANDAR]: ").upper() or "REFRIGERADO"
                    cap = float(input_seguro("Capacidad máxima en kg [Enter para 25000]: ") or 25000)
                    id_prov_cont = int(input_seguro("ID del Proveedor del Contenedor: ") or (provs[0][0] if provs else 1))

                    print("Tipos de Sensor IoT a instalar en este contenedor:")
                    print("   1. TEMPERATURA_GPS")
                    print("   2. HUMEDAD_GPS")
                    print("   3. MULTIPARAMETRICO_GPS (Temperatura + Humedad + Vibración)")
                    op_s = input_seguro("Elegí el tipo de sensor (1-3): ")
                    tipo_sensor = {"1": "TEMPERATURA_GPS", "2": "HUMEDAD_GPS", "3": "MULTIPARAMETRICO_GPS"}.get(op_s, "TEMPERATURA_GPS")
                    id_prov_sens = int(input_seguro("ID del Proveedor del Sensor IoT: ") or (provs[-1][0] if provs else 1))

                    contenedores.append({
                        "codigo": cod,
                        "tipo": tipo_c,
                        "capacidad": cap,
                        "id_proveedor_contenedor": id_prov_cont,
                        "tipo_sensor": tipo_sensor,
                        "id_proveedor_sensor": id_prov_sens
                    })
                    if input_seguro("¿Agregar otro contenedor a este envío? (s/n): ").lower() != "s":
                        break

                registrar_envio_con_contenedores_cliente(id_cli, origen, destino, prioridad, contenedores, id_operador)
            except Exception as e:
                print(f"❌ Error al registrar envío: {e}")
            finally:
                cursor.close()
                conn.close()
        elif sub == "2":
            abm_envio_contenedor_sensor_menu()
        elif sub == "3":
            break

def modulo_3_monitoreo_iot_y_trazabilidad():
    while True:
        print("\n--- [MÓDULO 3 Y 8: MONITOREO IoT (GPS REAL), RECORRIDOS Y EVENTOS] ---")
        print("1. Emitir Lectura IoT Continua (Simular Sensor con Lat/Lon real -> Redis + MongoDB)")
        print("2. Consultar Última Posición GPS en Tiempo Real (Caché Redis)")
        print("3. Reconstrucción del Recorrido de un Contenedor (Coordenadas Históricas MongoDB)")
        print("4. Registrar Evento Logístico en Bitácora")
        print("5. Ver Historial Completo de Eventos de un Envío")
        print("6. Volver")
        sub = input_seguro("Opción (1-6): ")
        if sub == "1":
            id_env = int(input_seguro("ID del Envío: "))
            id_cont = int(input_seguro("ID del Contenedor: ") or 1)
            id_sens = int(input_seguro("ID del Sensor: ") or 1)
            doc = generar_lectura_iot_coordenadas(id_env, id_cont, id_sens)
            gps = doc["coordenadas_gps"]
            print(f"✅ Lectura registrada -> Punto: {doc['ubicacion_actual']} | GPS: ({gps['lat']}, {gps['lon']}) | Temp: {doc['metricas']['temperatura_c']}°C | Bat: {doc['metricas']['bateria_pct']}%")
        elif sub == "2":
            id_env = int(input_seguro("ID del Envío a consultar en Redis: "))
            datos_redis = obtener_ultima_posicion_envio(id_env)
            if datos_redis:
                print(f"\n⚡ [ CACHÉ TIEMPO REAL REDIS - Envío #{id_env} ]")
                print(f"   - Punto Logístico: {datos_redis.get('punto_logistico')}")
                print(f"   - Coordenadas GPS: Latitud {datos_redis.get('latitud')}, Longitud {datos_redis.get('longitud')}")
                print(f"   - Temperatura: {datos_redis.get('temperatura_c')}°C | Humedad: {datos_redis.get('humedad_pct')}% | Batería: {datos_redis.get('bateria_pct')}%")
                print(f"   - Timestamp: {datos_redis.get('ultima_actualizacion')}")
            else:
                print("⚠️ Sin datos en caché de Redis para ese envío.")
        elif sub == "3":
            id_env = int(input_seguro("ID del Envío para reconstruir recorrido: "))
            lecturas = list(mongo_db["lecturas_sensores"].find({"envio_id": id_env}).sort("timestamp", 1))
            print(f"\n🗺️ [ RECONSTRUCCIÓN GEOGRÁFICA DEL RECORRIDO - Envío #{id_env} ]")
            if not lecturas:
                print("   ⚠️ No hay lecturas registradas para este envío.")
            for idx, l in enumerate(lecturas, 1):
                gps = l.get("coordenadas_gps", {"lat": 0.0, "lon": 0.0})
                print(f"   Paso {idx}: {l.get('ubicacion_actual')} -> GPS ({gps.get('lat')}, {gps.get('lon')}) | Temp: {l['metricas'].get('temperatura_c')}°C | {l.get('timestamp').strftime('%Y-%m-%d %H:%M:%S')}")
        elif sub == "4":
            id_env = int(input_seguro("ID del Envío: "))
            print("Tipos de Eventos Oficiales:")
            print("  1. Carga iniciada | 2. En tránsito | 3. Aduana | 4. Retraso | 5. Descarga | 6. Entregado")
            t_op = input_seguro("Seleccioná el tipo de evento (1-6): ")
            tipo = {
                "1": "Carga iniciada", "2": "En tránsito", "3": "Aduana",
                "4": "Retraso", "5": "Descarga", "6": "Entregado"
            }.get(t_op, "En tránsito")
            ubic = input_seguro("Ubicación / Punto Logístico: ")
            desc = input_seguro("Descripción operativa: ")
            registrar_evento_logistico(id_env, tipo, ubic, desc)
        elif sub == "5":
            id_env = int(input_seguro("ID del Envío: "))
            eventos = obtener_historial_eventos(id_env)
            if not eventos:
                print("   ⚠️ No hay eventos registrados para este envío.")
            else:
                print(f"\n📋 [ HISTORIAL DE EVENTOS LOGÍSTICOS - Envío #{id_env} ]")
                for e in eventos:
                    fecha_str = e["fecha_y_hora"].strftime("%Y-%m-%d %H:%M")
                    print(f"   - [{fecha_str}] envio id{e['id_envio']} tuvo un evento: {e['tipo_evento']}")
                    print(f"     en la ubicacion: {e['ubicacion']}")
                    print(f"     descripcion: {e['descripcion']}\n")
        elif sub == "6":
            break

def modulo_4_incidentes_y_alertas():
    while True:
        print("\n--- [MÓDULO 4: REGLAS IoT, INCIDENTES Y ALERTAS AUTOMÁTICAS] ---")
        print("1. ABM de Reglas de Umbrales IoT y Gestión de Alertas de Sensores")
        print("2. Registrar Incidente en Ruta Manualmente")
        print("3. Consultar Incidentes por Envío")
        print("4. Detección de Anomalías de Temperatura")
        print("5. Ranking de Rutas/Envíos con Mayor Cantidad de Incidentes")
        print("6. Volver")
        sub = input_seguro("Opción (1-6): ")
        if sub == "1": abm_reglas_y_alertas_menu()
        elif sub == "2":
            id_env = int(input_seguro("ID del Envío: "))
            tipo = input_seguro("Tipo (Climático / Aduanero / Falla Mecánica / Corte Cadena Frío): ")
            sev = input_seguro("Severidad [ALTA / MEDIA / BAJA]: ").upper() or "ALTA"
            desc = input_seguro("Descripción: ")
            registrar_incidente(id_env, tipo, sev, desc)
        elif sub == "3":
            id_env = int(input_seguro("ID del Envío: "))
            incidentes = obtener_incidentes_por_envio(id_env)
            if not incidentes:
                print("   ✅ Sin incidentes para este envío.")
            for i in incidentes:
                print(f"   - [{i['severidad']}] {i['tipo']} ({i['estado']}): {i['descripcion']}")
        elif sub == "4":
            anomalias = deteccion_anomalias_temperatura()
            if not anomalias:
                print("   ✅ No se registran anomalías térmicas.")
            for d in anomalias:
                gps = d.get("coordenadas_gps", {})
                print(f"   - Envío #{d['envio_id']} (Sensor #{d.get('sensor_id', 1)}) | Temp: {d['metricas']['temperatura_c']}°C | Hub: {d['ubicacion_actual']} ({gps.get('lat')}, {gps.get('lon')})")
        elif sub == "5":
            for r in ranking_rutas_incidentes():
                print(f"   - Envío/Ruta #{r['_id']}: {r['total_incidentes']} incidente(s) registrados.")
        elif sub == "6":
            break

def modulo_5_comunicaciones(usuario):
    while True:
        print("\n--- [MÓDULO 5: COMUNICACIÓN CON CLIENTES, PROVEEDORES Y OPERADORES] ---")
        print("1. Registrar / Enviar Comunicación Externa o Interna")
        print("2. Ver Historial de Comunicaciones")
        print("3. Volver al panel principal")
        sub = input_seguro("Opción (1-3): ")
        if sub == "1":
            dest = input_seguro("Destinatario (Razón Social Cliente, Proveedor u Operador Logístico): ")
            msg = input_seguro("Mensaje / Instrucción operativa: ")
            enviar_mensaje(usuario["nombre"], dest, msg)
        elif sub == "2":
            mensajes = obtener_mensajes(usuario["nombre"])
            if not mensajes:
                print("   ⚠️ No hay comunicaciones registradas para este usuario.")
            for m in mensajes:
                print(f"   [{m['fecha_y_hora'].strftime('%Y-%m-%d %H:%M')}] {m['remitente']} -> {m['destinatario']}: {m['contenido']}")
        elif sub == "3":
            break

def modulo_6_y_9_reportes_y_predicciones(usuario):
    while True:
        print("\n--- [MÓDULO 6 Y 9: REPORTES OPERATIVOS, ANALÍTICOS, GRAFO Y PREDICCIONES] ---")
        print("1. Reportes Operativos de Envíos (Por País, Por Estado, Por Cliente, Demorados, Incidentes Abiertos)")
        print("2. Reporte Analítico: Tiempos Máximos y Mínimos de Envío por Cliente")
        print("3. Reporte Analítico: Tiempo Promedio Global de Entrega")
        print("4. Reporte Analítico: Promedio de Incidentes por País / Estado / Cliente")
        print("5. Reporte Analítico: Costos Totales y Promedio por Tipo de Transporte ($)")
        print("6. Ranking de Clientes por Volumen Transportado e Histórico de Desempeño")
        print("7. Red de Relaciones entre Clientes, Operadores, Proveedores y Envíos (Neo4j)")
        print("8. Generar / Consultar Predicción de Atrasos y Riesgos")
        print("9. Volver")
        sub = input_seguro("Opción (1-9): ")
        if sub == "1":
            print("\n🌎 Envíos por País de Origen:", reporte_envios_por_pais())
            print("📊 Envíos por Estado:", reporte_envios_por_estado())
            print("🏢 Envíos por Cliente:", reporte_envios_por_cliente())
            print("🐌 Envíos Demorados:", reporte_envios_demorados())
            print("🚨 Incidentes Abiertos en Ruta:", len(reporte_incidentes_abiertos()))
        elif sub == "2":
            for d in reporte_tiempos_envio_por_cliente():
                print(f"   - Cliente: {d[0]} | Tiempo Máx: {round(d[1] or 0, 1)} días | Tiempo Mín: {round(d[2] or 0, 1)} días")
        elif sub == "3":
            print(f"⏱️ Tiempo estimado promedio global de entrega: {reporte_tiempos_promedio_general()} días.")
        elif sub == "4":
            proms = reporte_promedio_incidentes_multicriterio()
            print("📊 Promedio de Incidentes por País:", proms.get("por_pais"))
            print("📊 Promedio de Incidentes por Estado:", proms.get("por_estado"))
            print("📊 Promedio de Incidentes por Cliente:", proms.get("por_cliente"))
        elif sub == "5":
            print("\n💰 [ REPORTE ANALÍTICO DE COSTOS POR TIPO DE TRANSPORTE ]")
            datos_costos = reporte_costos_por_tipo_transporte()
            if not datos_costos:
                print("   ⚠️ No hay tramos registrados.")
            for medio, cant_tramos, costo_total, costo_prom in datos_costos:
                print(f"   - Medio: {medio} | Tramos operados: {cant_tramos} | Costo Total Acumulado: ${costo_total} | Costo Promedio por Tramo: ${costo_prom}")
        elif sub == "6":
            print("\n⚖️ [ RANKING DE CLIENTES POR VOLUMEN DE CARGA TRANSPORTADA ]")
            for cli, kg, cant_c in ranking_clientes_por_volumen():
                print(f"   - Cliente: {cli} | Volumen Total: {kg} kg ({cant_c} contenedor/es)")
            
            print("\n📈 [ ANÁLISIS HISTÓRICO DE DESEMPEÑO Y EFECTIVIDAD LOGÍSTICA ]")
            desemp = analisis_historico_desempeno()
            total_env = sum(x[1] for x in desemp) or 1
            for estado, cant in desemp:
                pct = round((cant / total_env) * 100, 1)
                print(f"   - Estado '{estado}': {cant} envío(s) ({pct}% del total operado)")
        elif sub == "7":
            relaciones = obtener_red_relaciones_grafo()
            print("\n🕸️ [ RED DE RELACIONES EN GRAFO NEO4J ]")
            for r in relaciones:
                print(f"   - Cliente '{r['cliente']}' -> Envío #{r['id_envio']} ({r['origen']}->{r['destino']}) | Operador: '{r['operador']}' | Proveedor Insumos: '{r['proveedor']}'")
        elif sub == "8":
            op_p = input_seguro("1. Registrar Nueva Predicción de Riesgo | 2. Ver Reporte Crítico (Demora > 50%): ")
            if op_p == "1":
                id_env = int(input_seguro("ID del Envío: "))
                prob = int(input_seguro("Probabilidad de demora (0-100%): "))
                clim = input_seguro("Riesgo Climático (BAJO/MEDIO/ALTO - Detalle): ")
                oper = input_seguro("Riesgo Operativo/Aduanero: ")
                registrar_prediccion_riesgo(id_env, prob, clim, oper)
            else:
                criticos = reporte_analisis_predictivos()
                print("\n⚠️ [ REPORTE DE PREDICCIONES CRÍTICAS DE ATRASO (> 50%) ]")
                if not criticos:
                    print("   ✅ No hay predicciones con probabilidad de demora superior al 50%.")
                for p in criticos:
                    print(f"   - Envío #{p['id_envio']} | Prob. Demora: {p['probabilidad_demora']}% | Clima: {p['riesgo_climatico']} | Operativo: {p['riesgo_operativo']}")
        elif sub == "9":
            break

def modulo_7_finanzas():
    while True:
        print("\n--- [MÓDULO 7: FINANZAS ACID, CUENTAS CORRIENTES, FACTURACIÓN Y PAGOS] ---")
        print("1. Cuenta Corriente de Clientes (Facturas Emitidas y Registro de Cobros)")
        print("2. Cuenta Corriente de Proveedores y Operadores Logísticos (Facturas Recibidas y Órdenes de Pago)")
        print("3. Reporte de Clientes Deudores / Mora Vencida")
        print("4. Ejecutar Cierre Mensual Contable de Cuentas Corrientes")
        print("5. Volver")
        sub = input_seguro("Opción (1-5): ")
        if sub == "1":
            listar_clientes_formateados()
            id_cli = int(input_seguro("\nIngresá el ID del Cliente a gestionar: "))
            consultar_cuenta_corriente(id_cli)
        elif sub == "2":
            gestionar_pagos_proveedores_y_operadores_menu()
        elif sub == "3":
            listar_clientes_deudores()
        elif sub == "4":
            ejecutar_cierre_mensual_cuentas()
        elif sub == "5":
            break

if __name__ == "__main__":
    menu_principal()