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
    listar_clientes_resumido,
    validar_cliente_activo,
    normalizar_nombre_ubicacion,
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

MODULOS_POR_ROL = {
    1: ["1", "5"],
    2: ["2", "3", "4", "5"],
    3: ["7", "5"],
    4: ["6", "5"]
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
                # Mostrar solo ID, Razón Social y Estado
                listar_clientes_resumido(mostrar_estado=True)
                id_cli = int(input_seguro("\nIngresá el ID del Cliente que solicita el envío: "))

                # Validar inmediatamente antes de pedir cualquier otro dato
                es_valido, msg = validar_cliente_activo(id_cli)
                if not es_valido:
                    print(f"❌ Operación cancelada: {msg}")
                    continue

                print("\nDestinos y Orígenes disponibles:")
                print("  Nacionales     : Buenos Aires | Rosario | Córdoba | Mendoza")
                print("  Internacionales: Santiago de Chile | Madrid (España)")
                origen_in = input_seguro("Origen del envío [Ej: Buenos Aires]: ") or "Buenos Aires"
                destino_in = input_seguro("Destino del envío [Ej: Santiago de Chile]: ") or "Santiago de Chile"
                origen_formal = normalizar_nombre_ubicacion(origen_in)
                destino_formal = normalizar_nombre_ubicacion(destino_in)

                prioridad = input_seguro("Prioridad [ALTA / MEDIA / BAJA]: ").upper() or "MEDIA"

                pais_o = HUBS_PAIS.get(origen_formal, "Argentina")
                pais_d = HUBS_PAIS.get(destino_formal, "Exterior")
                es_internacional = (pais_o != pais_d)

                id_operador = None
                if es_internacional:
                    print(f"\n🌐 Envío INTERNACIONAL detectado ({origen_formal} -> {destino_formal}).")
                    print("Seleccioná el Operador Logístico asignado:")
                    cursor.execute("SELECT id_operador, nombre_completo FROM operador_logistico WHERE estado = 'ACTIVO' ORDER BY id_operador;")
                    ops = cursor.fetchall()
                    for o in ops:
                        print(f"   - ID #{o[0]}: {o[1]}")
                    id_operador = int(input_seguro("ID del Operador Logístico: ") or (ops[0][0] if ops else 1))
                else:
                    print(f"\n🚛 Envío NACIONAL TERRESTRE detectado ({origen_formal} -> {destino_formal}). No requiere Operador Logístico externo.")

                # Mostrar proveedores de forma limpia (solo ID y Razón Social) para elegir libremente
                cursor.execute("SELECT id_proveedor, razon_social FROM proveedor WHERE estado = 'ACTIVO' ORDER BY id_proveedor;")
                provs = cursor.fetchall()
                print("\n🏢 Proveedores disponibles:")
                for p in provs:
                    print(f"   - ID #{p[0]}: {p[1]}")

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
                    id_prov_sens = int(input_seguro("ID del Proveedor del Sensor IoT: ") or (provs[0][0] if provs else 1))

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

                registrar_envio_con_contenedores_cliente(id_cli, origen_formal, destino_formal, prioridad, contenedores, id_operador)
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
        print("1. Emitir Lectura IoT Continua (Detecta automáticamente los sensores del Contenedor)")
        print("2. Consultar Última Posición GPS en Tiempo Real (Caché Redis)")
        print("3. Reconstrucción del Recorrido de un Contenedor (Secuencia de Pasos y GPS)")
        print("4. Registrar Evento Logístico en Bitácora")
        print("5. Ver Historial Completo de Eventos de un Envío")
        print("6. Volver")
        sub = input_seguro("Opción (1-6): ")
        if sub == "1":
            try:
                id_env = int(input_seguro("ID del Envío: "))
                id_cont = int(input_seguro("ID del Contenedor: ") or 1)
                doc = generar_lectura_iot_coordenadas(id_env, id_cont)
                gps = doc["coordenadas_gps"]
                sensores_str = ", ".join(f"#{s}" for s in doc.get("sensores_procesados", [doc["sensor_id"]]))
                print(f"✅ Lectura registrada (Sensor/es {sensores_str}) -> Ubicación: {doc['ubicacion_actual']} | GPS: ({gps['lat']}, {gps['lon']}) | Temp: {doc['metricas']['temperatura_c']}°C | Bat: {doc['metricas']['bateria_pct']}%")
            except Exception as e:
                print(f"❌ Error: {e}")
        elif sub == "2":
            id_env = int(input_seguro("ID del Envío a consultar en Redis: "))
            datos_redis = obtener_ultima_posicion_envio(id_env)
            if datos_redis:
                print(f"\n⚡ [ CACHÉ TIEMPO REAL REDIS - Envío #{id_env} ]")
                print(f"   - Punto Logístico: {datos_redis.get('punto_logistico')}")
                print(f"   - Coordenadas GPS: Latitud {datos_redis.get('latitud')}, Longitud {datos_redis.get('longitud')}")
                print(f"   - Temperatura: {datos_redis.get('temperatura_c')}°C | Humedad: {datos_redis.get('humedad_pct')}% | Batería: {datos_redis.get('bateria_pct')}%")
                print(f"   - Hora Local de Lectura: {datos_redis.get('ultima_actualizacion')}")
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
                print(f"   Paso {idx}: {l.get('ubicacion_actual')} -> Coordenadas GPS ({gps.get('lat')}, {gps.get('lon')})")
        elif sub == "4":
            id_env = int(input_seguro("ID del Envío: "))
            print("Tipos de Eventos Oficiales:")
            print("  1. Carga iniciada | 2. En tránsito | 3. Aduana | 4. Retraso | 5. Descarga | 6. Entregado")
            t_op = input_seguro("Seleccioná el tipo de evento (1-6): ")
            tipo = {
                "1": "Carga iniciada", "2": "En tránsito", "3": "Aduana",
                "4": "Retraso", "5": "Descarga", "6": "Entregado"
            }.get(t_op, "En tránsito")
            ubic = input_seguro("Ubicación: ")
            desc = input_seguro("Descripción: ")
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
                    print(f"   [{fecha_str}] Evento: {e['tipo_evento']}")
                    print(f"     Ubicacion: {e['ubicacion']}")
                    print(f"     Descripcion: {e['descripcion']}\n")
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
                print(f"   - Envío #{d['envio_id']} (Sensor #{d.get('sensor_id', 1)}) | Temp: {d['metricas']['temperatura_c']}°C | Ubicación: {d['ubicacion_actual']} ({gps.get('lat')}, {gps.get('lon')})")
        elif sub == "5":
            for r in ranking_rutas_incidentes():
                print(f"   - Envío/Ruta #{r['_id']}: {r['total_incidentes']} incidente(s) registrados.")
        elif sub == "6":
            break

def modulo_5_comunicaciones(usuario):
    while True:
        print("\n--- [MÓDULO 5: COMUNICACIÓN CON CLIENTES, PROVEEDORES Y OPERADORES] ---")
        print("1. Registrar / Enviar Comunicación (Seleccionando Destinatario por ID)")
        print("2. Ver Historial de Comunicaciones")
        print("3. Volver al panel principal")
        sub = input_seguro("Opción (1-3): ")
        if sub == "1":
            print("\n¿A qué tipo de actor deseás enviarle una comunicación?")
            print("  1. Cliente")
            print("  2. Proveedor")
            print("  3. Operador Logístico")
            tipo_dest = input_seguro("Seleccioná una opción (1-3): ")
            
            conn = get_pg_connection()
            cursor = conn.cursor()
            destinatario_nombre = None
            try:
                if tipo_dest == "1":
                    cursor.execute("SELECT id_cliente, razon_social FROM cliente ORDER BY id_cliente;")
                    filas = cursor.fetchall()
                    print("\n🏢 Clientes disponibles:")
                    for f in filas: print(f"   - ID #{f[0]}: {f[1]}")
                    id_sel = int(input_seguro("Ingresá el ID del Cliente destinatario: "))
                    cursor.execute("SELECT razon_social FROM cliente WHERE id_cliente = %s;", (id_sel,))
                    r = cursor.fetchone()
                    if r: destinatario_nombre = f"Cliente: {r[0]}"
                elif tipo_dest == "2":
                    cursor.execute("SELECT id_proveedor, razon_social FROM proveedor ORDER BY id_proveedor;")
                    filas = cursor.fetchall()
                    print("\n🏢 Proveedores disponibles:")
                    for f in filas: print(f"   - ID #{f[0]}: {f[1]}")
                    id_sel = int(input_seguro("Ingresá el ID del Proveedor destinatario: "))
                    cursor.execute("SELECT razon_social FROM proveedor WHERE id_proveedor = %s;", (id_sel,))
                    r = cursor.fetchone()
                    if r: destinatario_nombre = f"Proveedor: {r[0]}"
                elif tipo_dest == "3":
                    cursor.execute("SELECT id_operador, nombre_completo FROM operador_logistico ORDER BY id_operador;")
                    filas = cursor.fetchall()
                    print("\n👷 Operadores Logísticos disponibles:")
                    for f in filas: print(f"   - ID #{f[0]}: {f[1]}")
                    id_sel = int(input_seguro("Ingresá el ID del Operador Logístico destinatario: "))
                    cursor.execute("SELECT nombre_completo FROM operador_logistico WHERE id_operador = %s;", (id_sel,))
                    r = cursor.fetchone()
                    if r: destinatario_nombre = f"Operador: {r[0]}"
                else:
                    print("⚠️ Opción inválida.")
                    continue
            finally:
                cursor.close()
                conn.close()

            if not destinatario_nombre:
                print("❌ Error: El ID ingresado no existe.")
                continue

            msg = input_seguro(f"Escribí el mensaje para [{destinatario_nombre}]: ")
            if msg:
                enviar_mensaje(usuario["nombre"], destinatario_nombre, msg)
        elif sub == "2":
            mensajes = obtener_mensajes()
            if not mensajes:
                print("   ⚠️ No hay comunicaciones registradas.")
            for m in mensajes:
                print(f"   [{m['fecha_y_hora'].strftime('%Y-%m-%d %H:%M')}] De: {m['remitente']} -> Para: {m['destinatario']} | Mensaje: {m['contenido']}")
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
        print("8. Generar / Consultar Predicciones de Atrasos y Riesgos")
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
                print(f"   - Cliente '{r['cliente']}' -> Envío #{r['id_envio']} ({r['origen']} -> {r['destino']}) | Operador: '{r['operador']}' | Proveedor Insumos: '{r['proveedor']}'")
        elif sub == "8":
            op_p = input_seguro("1. Registrar Nueva Predicción de Riesgo | 2. Ver Todas las Predicciones de Atraso y Fecha Estimada: ")
            if op_p == "1":
                id_env = int(input_seguro("ID del Envío: "))
                prob = int(input_seguro("Probabilidad de demora (0-100%): "))
                clim = input_seguro("Riesgo Climático [BAJO / MEDIO / ALTO]: ").upper() or "MEDIO"
                oper = input_seguro("Riesgo Operativo [BAJO / MEDIO / ALTO]: ").upper() or "BAJO"
                registrar_prediccion_riesgo(id_env, prob, clim, oper)
            else:
                predicciones = reporte_analisis_predictivos()
                print("\n📅 [ REPORTE DE PREDICCIONES DE ATRASOS Y RIESGOS (TODOS LOS ENVÍOS) ]")
                if not predicciones:
                    print("   ⚠️ No hay predicciones registradas.")
                for p in predicciones:
                    f_calc = p.get("fecha_calculo").strftime("%Y-%m-%d %H:%M") if p.get("fecha_calculo") else "N/A"
                    f_proy = p.get("fecha_llegada_proyectada").strftime("%Y-%m-%d") if p.get("fecha_llegada_proyectada") else "N/A"
                    dias_atr = p.get("dias_atraso_estimados", 0)
                    print(f"   - Envío #{p['id_envio']} | Prob. Demora: {p['probabilidad_demora']}% | Clima: {p['riesgo_climatico']} | Operativo: {p['riesgo_operativo']}")
                    print(f"     Fecha de Cálculo: {f_calc} | Atraso Estimado: +{dias_atr} días -> Nueva Fecha Estimada de Entrega: {f_proy}")
        elif sub == "9":
            break

def modulo_7_finanzas():
    while True:
        print("\n--- [MÓDULO 7: FINANZAS ACID, CUENTAS CORRIENTES, FACTURACIÓN Y PAGOS] ---")
        print("1. Cuenta Corriente de Clientes (Facturas Emitidas y Registro de Cobros)")
        print("2. Cuenta Corriente de Proveedores y Operadores Logísticos (Facturas y Órdenes de Pago)")
        print("3. Reporte de Clientes Deudores / Mora Vencida")
        print("4. Ejecutar Cierre Mensual Contable de Cuentas Corrientes")
        print("5. Volver")
        sub = input_seguro("Opción (1-5): ")
        if sub == "1":
            # Muestra solo ID y Razón Social como pediste
            listar_clientes_resumido(mostrar_estado=False)
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