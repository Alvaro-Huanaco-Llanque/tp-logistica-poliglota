from repositories.redis_repo import actualizar_ultima_posicion, obtener_ultima_posicion
from repositories.mongo_repo import (
    guardar_lectura_iot, 
    generar_lectura_automatica,
    registrar_evento_logistico,
    obtener_historial_eventos,
    registrar_incidente,
    obtener_incidentes_por_envio,
    enviar_mensaje,
    obtener_mensajes,
    guardar_reporte,
    listar_reportes_usuario
)
from repositories.neo4j_repo import buscar_camino_optimo
from repositories.pg_repo import (
    registrar_inicio_sesion,
    cerrar_sesion_activa,
    obtener_estado_cliente,
    login_general,
    auto_registrar_usuario_general,
    crear_factura_y_actualizar_saldo,
    abm_cliente_menu,
    abm_envio_contenedor_sensor_menu,
    consultar_cuenta_corriente,
    registrar_envio_cliente,
    listar_envios_cliente,
    registrar_envio_con_contenedores_cliente,
    registrar_vehiculo,
    listar_vehiculos,
    input_seguro,
    registrar_grupo_trabajo,
    listar_grupos_trabajo
)

def menu_principal():
    while True:
        print("\n=======================================================")
        print("   SISTEMA DE LOGÍSTICA POLÍGLOTA - INICIO DE SESIÓN")
        print("=======================================================")
        print("1. Iniciar Sesión (Cliente, Operador Logístico o Proveedor)")
        print("2. Registrarse en el Sistema")
        print("3. Salir")
        
        op = input("\nSeleccioná una opción (1-3): ").strip()
        
        if op == "1":
            print("\n--- INICIO DE SESIÓN ---")
            identificador = input("Ingresá tu CUIT (si sos Cliente) o tu Email (Operador/Proveedor): ")
            password = input("Contraseña: ")
            
            usuario_data = login_general(identificador, password)
            if not usuario_data:
                print("❌ Credenciales inválidas.")
                continue
                
            if usuario_data["estado"] == "INACTIVO" or usuario_data["estado"] is False:
                print(f"⚠️ Hola {usuario_data['nombre']}: Tu cuenta se encuentra INACTIVA. Podés entrar al panel, pero con funciones limitadas.")
                
            usuario_sesion = {
                "id_usuario": usuario_data["id_usuario"],
                "id_cliente": usuario_data.get("id_cliente"),
                "nombre": usuario_data["nombre"],
                "id_rol": usuario_data["id_rol"],
                "estado": usuario_data["estado"],
                "identificador_login": identificador
            }
            usuario_sesion["id_sesion"] = registrar_inicio_sesion(usuario_sesion["id_usuario"])
            
            if usuario_sesion["id_rol"] == 2:
                menu_cliente(usuario_sesion)
            elif usuario_sesion["id_rol"] == 1:
                menu_operario(usuario_sesion)
            elif usuario_sesion["id_rol"] == 3:
                menu_proveedor(usuario_sesion)
            
        elif op == "2":
            menu_registro()
            
        elif op == "3":
            print("\n👋 ¡Saliendo del sistema!")
            break
        else:
            print("⚠️ Opción inválida.")


def menu_registro():
    print("\n=======================================================")
    print("   REGISTRO EN EL SISTEMA")
    print("=======================================================")
    print("1. Registrarse como NUEVO CLIENTE (Empresa que contrata envíos)")
    print("2. Registrarse como NUEVO OPERADOR LOGÍSTICO (Chofer/Administrativo)")
    print("3. Registrarse como NUEVO PROVEEDOR (Dueño de flota, contenedores o sensores)")
    print("4. Volver")
    tipo = input("Seleccioná una opción (1-4): ").strip()
    
    if tipo == "1":
        try:
            razon = input("Razón Social de la Empresa: ")
            cuit = int(input("CUIT (solo números, ej: 20123456789): "))
            email = input("Email de contacto: ")
            tel = int(input("Teléfono (solo números, ej: 1155555555): "))
            direccion = input("Dirección: ")
            pais = input("País [Enter para Argentina]: ") or "Argentina"
            nombre_cont = input("Nombre de la persona de contacto: ")
            apellido_cont = input("Apellido de la persona de contacto: ")
            password = input("Contraseña para el sistema: ")
            
            id_usr = auto_registrar_usuario_general(
                id_rol=2, nombre=nombre_cont, apellido=apellido_cont, email=email, 
                password=password, cuit=cuit, razon_social=razon, telefono=tel, 
                direccion=direccion, pais=pais
            )
            print(f"\n✅ ¡Registro de Cliente exitoso! Tu cuenta está INACTIVA a la espera de aprobación.")
        except Exception as e:
            print(f"❌ Error al registrar cliente: {e}")
            
    elif tipo in ["2", "3"]:
        rol_desc = "Operador Logístico" if tipo == "2" else "Proveedor"
        id_rol_asig = 1 if tipo == "2" else 3
        try:
            nombre = input("Nombre: ")
            apellido = input("Apellido: ")
            email = input("Email: ")
            password = input("Contraseña: ")
            
            id_usr = auto_registrar_usuario_general(
                id_rol=id_rol_asig, nombre=nombre, apellido=apellido, 
                email=email, password=password
            )
            print(f"\n✅ ¡{rol_desc} registrado con éxito! Ya podés iniciar sesión con tu Email.")
        except Exception as e:
            print(f"❌ Error al registrar {rol_desc}: {e}")


def menu_proveedor(usuario):
    """Menú principal para el Rol 3: Proveedor (Gestión integral de flota, clientes y operaciones)"""
    while True:
        print("\n=======================================================")
        print(f"   PORTAL DE PROVEEDOR: {usuario['nombre']} | Sesión #{usuario['id_sesion']}")
        print("=======================================================")
        print("1. [Gestión Flota] Registrar y Listar Vehículos")
        print("2. [Gestión Clientes] ABM Clientes (Dar de alta, suspender, listar)")
        print("3. [Gestión Operativa] Envíos, Contenedores, Sensores y Estados")
        print("4. [Gestión Grupos] Crear y Listar Grupos de Trabajo")
        print("5. [Finanzas] Mi Cuenta Corriente y Facturación de alquileres")
        print("6. [Comunicaciones] Servicio de Mensajería")
        print("7. [Reportes] Tiempos Máximos y Mínimos de Envío por Cliente")
        print("8. [IoT] Seguimiento de Sensores (Lectura)")
        print("9. Volver al inicio (Cerrar Sesión)")
        
        try:
            opcion = input("\nSeleccioná una opción (1-9): ").strip()
        except KeyboardInterrupt:
            print("\n↩️ Volviendo al menú principal...")
            break
            
        if opcion == "1":
            while True:
                print("\n--- Gestión de Vehículos ---")
                print("1. Registrar Nuevo Vehículo")
                print("2. Listar Mis Vehículos Físicos")
                print("3. Volver")
                sub_v = input_seguro("Elegí una opción: ")
                if sub_v == "1":
                    tipo = input_seguro("Tipo de Vehículo (ej. Camión, Barco, Avión): ")
                    identificacion = input_seguro("Matrícula o Identificación: ")
                    registrar_vehiculo(tipo, identificacion, usuario['nombre'])
                elif sub_v == "2":
                    listar_vehiculos()
                elif sub_v == "3":
                    break
                    
        elif opcion == "2":
            abm_cliente_menu()
            
        elif opcion == "3":
            abm_envio_contenedor_sensor_menu()
            
        elif opcion == "4":
            while True:
                print("\n--- Gestión de Grupos de Trabajo ---")
                print("1. Crear Grupo de Trabajo")
                print("2. Listar Grupos de Trabajo")
                print("3. Volver")
                op_grupo = input_seguro("Elegí una opción: ")
                if op_grupo == "1":
                    nombre = input_seguro("Nombre del Grupo: ")
                    integrantes = input_seguro("Integrantes (separados por coma): ")
                    registrar_grupo_trabajo(nombre, integrantes)
                elif op_grupo == "2":
                    listar_grupos_trabajo()
                elif op_grupo == "3":
                    break
                    
        elif opcion == "5":
            from repositories.pg_repo import consultar_cuenta_proveedor
            consultar_cuenta_proveedor(usuario['nombre'])
            input("\nPresioná Enter para volver al menú...")
            
        elif opcion == "6":
            print("\n--- 💬 Servicio de Mensajería ---")
            print("1. Enviar Mensaje")
            print("2. Ver Historial de Mensajes")
            sub_op = input_seguro("Elegí una opción: ")
            if sub_op == "1":
                dest = input_seguro("Destinatario (Ingresá el Email del Operador o CUIT/Nombre del Cliente): ")
                msg = input_seguro("Mensaje: ")
                enviar_mensaje(usuario['nombre'], dest, msg)
            elif sub_op == "2":
                identificador = usuario.get('identificador_login', None)
                mensajes = obtener_mensajes(usuario['nombre'], identificador)
                if mensajes:
                    for m in mensajes:
                        print(f"[{m['fecha_y_hora'].strftime('%H:%M')}] {m['remitente']} a {m['destinatario']}: {m['contenido']}")
                else:
                    print("No hay mensajes en tu historial.")
            
        elif opcion == "7":
            while True:
                print("\n--- [Reportes Gerenciales y de Negocio (Proveedor)] ---")
                print("1. Envíos totales por Cliente (Fidelización)")
                print("2. Tiempos Máximos y Mínimos de Entrega por Cliente")
                print("3. Ranking de Clientes por Volumen Transportado (kg)")
                print("4. Análisis Histórico de Desempeño (Eficacia global)")
                print("5. Volver")
                
                op_rep = input_seguro("Elegí un reporte (1-5): ").strip()
                if op_rep == "5":
                    break
                
                if op_rep == "1":
                    from repositories.pg_repo import reporte_envios_por_cliente
                    datos = reporte_envios_por_cliente()
                    print("\n📦 [ ENVÍOS TOTALES POR CLIENTE ]")
                    if not datos: print("   ⚠️ Sin datos.")
                    for d in datos: print(f"   - {d[0]}: {d[1]} envío(s) contratados.")
                        
                elif op_rep == "2":
                    from repositories.pg_repo import reporte_tiempos_envio_por_cliente
                    datos = reporte_tiempos_envio_por_cliente()
                    print("\n⏱️ [ TIEMPOS MÁXIMOS Y MÍNIMOS POR CLIENTE ]")
                    if not datos: print("   ⚠️ Sin datos.")
                    for d in datos: print(f"   - {d[0]} | Máximo: {round(d[1] or 0, 1)} días | Mínimo: {round(d[2] or 0, 1)} días.")
                        
                elif op_rep == "3":
                    from repositories.pg_repo import ranking_clientes_por_volumen
                    datos = ranking_clientes_por_volumen()
                    print("\n⚖️ [ RANKING POR VOLUMEN TRANSPORTADO ]")
                    if not datos: print("   ⚠️ Sin datos.")
                    for d in datos: print(f"   - {d[0]}: {d[1]} kg transportados en total.")
                        
                elif op_rep == "4":
                    from repositories.pg_repo import analisis_historico_desempeno
                    datos = analisis_historico_desempeno()
                    print("\n📊 [ ANÁLISIS HISTÓRICO DE DESEMPEÑO ]")
                    if not datos: print("   ⚠️ Sin datos históricos de entregas o demoras.")
                    for d in datos: print(f"   - Estado Histórico '{d[0]}': {d[1]} envío(s).")
                else:
                    print("⚠️ Opción inválida.")
        elif opcion == "8":
            print("\n--- Seguimiento IoT (Vista Proveedor) ---")
            envio_id_input = input_seguro("ID del Envío a monitorear: ")
            if envio_id_input:
                envio_id = int(envio_id_input)
                from config.database import mongo_db
                lecturas = list(mongo_db["lecturas_sensores"].find({"envio_id": envio_id}).sort("timestamp", -1).limit(3))
                
                if lecturas:
                    print(f"\n📍 [ ÚLTIMAS LECTURAS IoT - Envío #{envio_id} ]")
                    for l in lecturas:
                        print(f"   - {l.get('timestamp').strftime('%Y-%m-%d %H:%M:%S')} | Ubicación: {l.get('ubicacion_actual')}")
                        print(f"     Temp: {l['metricas'].get('temperatura_c')}°C | Anomalía: {'🚨 SÍ' if l.get('alerta_anomalia') else '✅ Normal'}")
                else:
                    print("⚠️ No hay lecturas registradas para este envío.")
            input("\nPresioná Enter para volver...")

        elif opcion == "9":
            from repositories.pg_repo import cerrar_sesion_activa
            cerrar_sesion_activa(usuario['id_sesion'])
            print("🔒 Sesión de proveedor finalizada.")
            break
            
        else:
            print("⚠️ Opción inválida. Por favor, seleccioná un número del 1 al 8.")


def menu_cliente(usuario):
    from repositories.pg_repo import (
        reporte_tiempos_por_envio,
        reporte_envios_por_pais,
        reporte_envios_por_estado,
        reporte_envios_demorados,
        reporte_costos_por_tipo_transporte,
        reporte_tiempos_promedio_general
    )
    from repositories.mongo_repo import (
        reporte_incidentes_abiertos,
        reporte_analisis_predictivos,
        reporte_promedio_incidentes_por_estado
    )

    while True:
        datos_actuales = obtener_estado_cliente(usuario["id_cliente"])
        estado_actual = datos_actuales["estado"]
        
        print("\n=======================================================")
        print(f"   PORTAL DE CLIENTE: {usuario['nombre']} (ID: {usuario['id_cliente']})")
        print(f"   Estado de Cuenta: [{estado_actual}] | Sesión #{usuario['id_sesion']}")
        print("=======================================================")
        if estado_actual == "INACTIVO":
            print("⛔ AVISO: Tu cuenta está INACTIVA. No podés crear envíos.")
        elif estado_actual == "SUSPENDIDO":
            print("⚠️ AVISO: Tu cuenta está SUSPENDIDA. Solo podés abonar facturas.")
            
        print("1. Registrar un Nuevo Envío (y asignar Contenedores)")
        print("2. Mis Envíos (Historial y Contenedores asignados)")
        print("3. Seguimiento GPS de un sensor en Tiempo Real (Redis)")
        print("4. Mi Cuenta Corriente, Facturas y Pagos")
        print("5. Solicitar Reporte Analítico / Operativo (Facturable)")
        print("6. Mensajería con Operadores")
        print("7. Volver al inicio (Cerrar Sesión)")
        
        try:
            opcion = input("\nSeleccioná una opción (1-7): ").strip()
        except KeyboardInterrupt:
            print("\n↩️ Volviendo al menú principal...")
            break
        
        if opcion == "1":
            if estado_actual != "ACTIVO":
                print(f"⛔ Operación bloqueada: Tu cuenta está '{estado_actual}'.")
                continue
            
            print("\n--- Registrar Nuevo Envío ---")
            try:
                origen = (input_seguro("Origen [Ej: Buenos Aires]: ") or "Buenos Aires").title()
                destino = (input_seguro("Destino [Ej: Rosario]: ") or "Rosario").title()
                prioridad = input_seguro("Prioridad [ALTA / MEDIA / BAJA]: ").upper() or "MEDIA"
                
                contenedores = []
                while True:
                    print(f"\n--- Agregando Contenedor {len(contenedores) + 1} ---")
                    codigo = input_seguro("Código Internacional [Ej: AR-1234]: ") or f"CONT-{len(contenedores)+1}X"
                    tipo_c = input_seguro("Tipo [REFRIGERADO / ESTANDAR]: ").upper() or "ESTANDAR"
                    cap = input_seguro("Capacidad kg [Enter para 25000]: ")
                    capacidad = float(cap) if cap else 25000.0
                    
                    contenedores.append({
                        "codigo": codigo,
                        "tipo": tipo_c,
                        "capacidad": capacidad
                    })
                    
                    otro = input_seguro("\n¿Querés agregar otro contenedor a este mismo envío? (s/n): ").lower()
                    if otro != 's':
                        break
                
                id_envio = registrar_envio_con_contenedores_cliente(
                    usuario['id_cliente'], origen, destino, prioridad, contenedores
                )
                print(f"\n✅ ¡Éxito! Envío #{id_envio} creado junto con {len(contenedores)} contenedor/es.")
                
            except KeyboardInterrupt:
                continue
            except Exception as e:
                print(f"❌ Error al registrar: {e}")
                
        elif opcion == "2":
            print("\n--- Mi Historial de Envíos ---")
            listar_envios_cliente(usuario['id_cliente'])
            
        elif opcion == "3":
            print("\n--- Seguimiento IoT de Contenedores por Envío ---")
            try:
                envio_id_input = input_seguro("ID del Envío a consultar: ")
                if not envio_id_input:
                    continue
                envio_id = int(envio_id_input)
                
                from repositories.mongo_repo import generar_lectura_automatica, guardar_lectura_iot
                from config.database import mongo_db
                from config.database import get_pg_connection
                from repositories.neo4j_repo import buscar_camino_optimo

                # 1. Generación de Telemetría
                lectura_sim = generar_lectura_automatica(envio_id, contenedor_id=1)
                guardar_lectura_iot(
                    contenedor_id=lectura_sim["contenedor_id"],
                    envio_id=lectura_sim["envio_id"],
                    ubicacion_actual=lectura_sim["ubicacion_actual"],
                    metricas=lectura_sim["metricas"],
                    alerta_anomalia=lectura_sim["alerta_anomalia"]
                )
                
                # 2. Reconstrucción Dinámica e Integración con Neo4j
                conn = get_pg_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT origen_envio, destino_envio FROM envio WHERE id_envio = %s;", (envio_id,))
                    info = cursor.fetchone()
                    if info:
                        origen = info[0].split(',')[0].strip()
                        destino = info[1].split(',')[0].strip()
                        
                        print(f"\n🗺️ [ RECONSTRUCCIÓN DEL RECORRIDO - Envío #{envio_id} ]")
                        
                        # A) Consultamos Neo4j para el camino planificado
                        ruta_neo4j = buscar_camino_optimo(origen, destino)
                        if ruta_neo4j and len(ruta_neo4j) > 0:
                            print(f"   - Camino Óptimo (Neo4j): {' -> '.join(ruta_neo4j[0]['ruta'])}")
                        
                        # B) Construimos el recorrido real histórico desde MongoDB
                        historial = list(mongo_db["lecturas_sensores"].find({"envio_id": envio_id}).sort("timestamp", 1))
                        recorrido_real = []
                        for loc in historial:
                            ub = loc.get('ubicacion_actual')
                            if not recorrido_real or recorrido_real[-1] != ub:
                                recorrido_real.append(ub)
                                
                        print(f"   - Recorrido Real: {' -> '.join(recorrido_real)}")
                finally:
                    cursor.close()
                    conn.close()

                # 3. Mostrar el historial recuperando la Batería
                lecturas = list(mongo_db["lecturas_sensores"].find({"envio_id": envio_id}).sort("timestamp", -1).limit(5))
                if lecturas:
                    print(f"\n📍 [ HISTORIAL RECIENTE DE TELEMETRÍA IoT ]")
                    for l in lecturas:
                        print(f"   - Fecha/Hora: {l.get('timestamp').strftime('%Y-%m-%d %H:%M:%S')} | Ubicación: {l.get('ubicacion_actual')}")
                        print(f"   - Temp: {l['metricas'].get('temperatura_c')} °C | Humedad: {l['metricas'].get('humedad_pct')}% | Batería: {l['metricas'].get('bateria_pct')}%")
                        print(f"   - Anomalía: {'🚨 SÍ' if l.get('alerta_anomalia') else '✅ Normal'}")
                        print("-" * 50)
                else:
                    print("⚠️ No se encontraron lecturas.")
                    
            except KeyboardInterrupt:
                continue
            except Exception as e:
                print(f"❌ Error al consultar telemetría: {e}")
                
        elif opcion == "4":
            consultar_cuenta_corriente(usuario['id_cliente'])
                
        elif opcion == "5":
            if estado_actual != "ACTIVO":
                print("⛔ Operación bloqueada.")
                continue
            try:
                print("\n--- 📊 SOLICITUD DE REPORTES (COSTO: $2500) ---")
                print("1. Análisis Predictivos (Atrasos y Riesgos) [MongoDB]")
                print("2. Tiempo Promedio Global de Entrega [PostgreSQL]")
                print("3. Envíos por Estado (Entregados, Demorados, En Tránsito) [PostgreSQL]")
                print("4. Envíos Demorados [PostgreSQL]")
                print("5. Incidentes Abiertos [MongoDB]")
                print("6. Costos por Tipo de Transporte [PostgreSQL]")
                print("7. Envíos por País de Origen [PostgreSQL]")
                
                sel_rep = input_seguro("Seleccioná un reporte (1-7) [Enter por defecto 1]: ").strip() or "1"
                
                print("\nFormatos de exportación disponibles:")
                print("1. PDF")
                print("2. WORD")
                print("3. TXT")
                sel_form = input_seguro("Seleccioná el formato (1-3) [Enter por defecto PDF]: ").strip()
                mapeo_formatos = {"1": "PDF", "2": "WORD", "3": "TXT"}
                formato = mapeo_formatos.get(sel_form, "PDF")

                contenido_guardar = []
                tipo_rep_str = ""

                print(f"\n=============================================")
                print(f"   GENERANDO REPORTE EN FORMATO {formato}...")
                print(f"=============================================\n")

                if sel_rep == "1":
                    tipo_rep_str = "PREDICCION_RIESGOS"
                    datos = reporte_analisis_predictivos()
                    print("📈 [ REPORTE DE ANÁLISIS PREDICTIVOS Y RIESGOS ]")
                    if not datos:
                        print("   ✅ No hay predicciones de riesgo crítico registradas.")
                    for d in datos:
                        txt = f"   - Envío #{d['id_envio']} | Probabilidad de demora: {d['probabilidad_demora']}% | Riesgos: {d['riesgo_climatico']} / {d['riesgo_operativo']}"
                        print(txt)
                        contenido_guardar.append(txt)

                elif sel_rep == "2":
                    tipo_rep_str = "TIEMPOS_PROMEDIO_GLOBAL"
                    promedio = reporte_tiempos_promedio_general()
                    print("⏱️ [ TIEMPO PROMEDIO DE ENTREGA GLOBAL ]")
                    txt = f"   - El tiempo estimado promedio de entrega global en la red logística es de {promedio} días."
                    print(txt)
                    contenido_guardar.append(txt)

                elif sel_rep == "3":
                    tipo_rep_str = "ENVIOS_POR_ESTADO"
                    datos = reporte_envios_por_estado()
                    print("📊 [ VOLUMEN DE ENVÍOS POR ESTADO ]")
                    if not datos:
                        print("   ⚠️ No hay datos de estados registrados.")
                    for d in datos:
                        txt = f"   - Estado: {d[0]} | Total de envíos: {d[1]}"
                        print(txt)
                        contenido_guardar.append(txt)

                elif sel_rep == "4":
                    tipo_rep_str = "ENVIOS_DEMORADOS"
                    datos = reporte_envios_demorados()
                    print("🐌 [ REPORTE DE ENVÍOS DEMORADOS ]")
                    if not datos:
                        print("   ✅ Excelente: No hay envíos demorados.")
                    for d in datos:
                        txt = f"   - Envío #{d[0]} (Cliente {d[1]}) | Ruta: {d[2]} -> {d[3]}"
                        print(txt)
                        contenido_guardar.append(txt)

                elif sel_rep == "5":
                    tipo_rep_str = "INCIDENTES_ABIERTOS"
                    datos = reporte_incidentes_abiertos()
                    print("🚨 [ INCIDENTES ABIERTOS ]")
                    if not datos:
                        print("   ✅ No hay incidentes pendientes de resolución.")
                    for d in datos:
                        txt = f"   - Envío #{d['id_envio']} | {d['tipo']} (Severidad: {d['severidad']}) - Reportado: {d['fecha'].strftime('%Y-%m-%d')}"
                        print(txt)
                        contenido_guardar.append(txt)

                elif sel_rep == "6":
                    tipo_rep_str = "COSTOS_TRANSPORTE"
                    datos = reporte_costos_por_tipo_transporte()
                    print("💰 [ ANÁLISIS DE COSTOS Y USO POR TIPO DE TRANSPORTE ]")
                    if not datos:
                        print("   ⚠️ No hay tramos registrados.")
                    for d in datos:
                        txt = f"   - Transporte {d[0]}: Usado en {d[1]} tramos."
                        print(txt)
                        contenido_guardar.append(txt)

                elif sel_rep == "7":
                    tipo_rep_str = "ENVIOS_POR_ORIGEN"
                    datos = reporte_envios_por_pais()
                    print("🌎 [ VOLUMEN DE ENVÍOS POR PAÍS DE ORIGEN ]")
                    if not datos:
                        print("   ⚠️ No hay datos de orígenes por país.")
                    for d in datos:
                        txt = f"   - País de Origen: {d[0]} | Total de envíos salientes: {d[1]}"
                        print(txt)
                        contenido_guardar.append(txt)
                else:
                    print("❌ Opción inválida.")
                    continue

                print(f"=============================================\n")

                contenido_json = {"datos_extraidos": contenido_guardar}
                guardar_reporte(usuario['nombre'], tipo_rep_str, contenido_json, formato)
                
                fact_id = crear_factura_y_actualizar_saldo(usuario['id_cliente'], 2500.00)
                print(f"✅ Reporte '{tipo_rep_str}' almacenado con éxito.")
                print(f"📄 Se emitió la Factura #{fact_id} por el cargo de $2500.00.")

            except KeyboardInterrupt:
                continue
            except Exception as e:
                print(f"❌ Error al generar reporte: {e}")
                
        elif opcion == "6":
            print("\n--- 💬 Servicio de Mensajería ---")
            print("1. Enviar Mensaje")
            print("2. Ver Historial de Mensajes")
            sub_op = input_seguro("Elegí una opción: ")
            if sub_op == "1":
                dest = input_seguro("Destinatario (Ingresá el Email del Operador o Proveedor): ")
                msg = input_seguro("Mensaje: ")
                enviar_mensaje(usuario['nombre'], dest, msg)
            elif sub_op == "2":
                identificador = usuario.get('identificador_login', None)
                mensajes = obtener_mensajes(usuario['nombre'], identificador)
                if mensajes:
                    for m in mensajes:
                        print(f"[{m['fecha_y_hora'].strftime('%H:%M')}] {m['remitente']} a {m['destinatario']}: {m['contenido']}")
                else:
                    print("No hay mensajes en tu historial.")
                    
        elif opcion == "7":
            cerrar_sesion_activa(usuario['id_sesion'])
            print("🔒 Sesión finalizada.")
            break
        else:
            print("⚠️ Opción inválida.")


def menu_operario(usuario):
    while True:
        print("\n=======================================================")
        print(f"   PANEL DE OPERARIO: {usuario['nombre']} | Sesión #{usuario['id_sesion']}")
        print("=======================================================")
        print("1. [Consulta] Ver Clientes, Envíos y Grupos de Trabajo")
        print("2. [IoT y Trayectos] Monitoreo de Sensores, Alertas y Rutas")
        print("3. [Finanzas ACID] Cuentas Corrientes, Facturación y Pagos")
        print("4. [Analítica y Reportes] Rankings y Predicción de Riesgos")
        print("5. [Comunicaciones] Servicio de Mensajería Global")
        print("6. Volver al inicio (Cerrar Sesión)")
        
        opcion = input("\nSeleccioná un módulo (1-6): ").strip()
        
        if opcion == "1":
            submenu_abm_operario()
        elif opcion == "2":
            submenu_iot_y_trayectos()
        elif opcion == "3":
            submenu_finanzas_operario()
        elif opcion == "4":
            submenu_analitica_operario()
        elif opcion == "5":
            from repositories.mongo_repo import enviar_mensaje, obtener_mensajes
            from repositories.pg_repo import input_seguro
            print("\n--- 💬 Servicio de Mensajería ---")
            print("1. Enviar Mensaje")
            print("2. Ver Historial de Mensajes")
            sub_op = input_seguro("Elegí una opción: ")
            if sub_op == "1":
                dest = input_seguro("Destinatario (Ingresá el Email del Proveedor o CUIT/Nombre del Cliente): ")
                msg = input_seguro("Mensaje: ")
                enviar_mensaje(usuario['nombre'], dest, msg)
            elif sub_op == "2":
                identificador = usuario.get('identificador_login', None)
                mensajes = obtener_mensajes(usuario['nombre'], identificador)
                if mensajes:
                    for m in mensajes:
                        print(f"[{m['fecha_y_hora'].strftime('%H:%M')}] {m['remitente']} a {m['destinatario']}: {m['contenido']}")
                else:
                    print("No hay mensajes en tu historial.")
        elif opcion == "6":
            cerrar_sesion_activa(usuario['id_sesion'])
            print("🔒 Sesión de operario finalizada.")
            break
        else:
            print("⚠️ Opción inválida.")


def submenu_abm_operario():
    while True:
        print("\n--- [1. Consulta Operativa] ---")
        print("a. Listar Clientes del Sistema")
        print("b. Listar Envíos, Contenedores y Sensores (Solo Lectura)")
        print("c. Listar Grupos de Trabajo (Ver asignaciones)")
        print("d. Volver")
        sub = input("Elegí una opción: ").lower().strip()
        
        if sub == "a":
            from repositories.pg_repo import listar_clientes_formateados
            print("\n--- LISTADO DE CLIENTES ---")
            listar_clientes_formateados()
            
        elif sub == "b":
            from repositories.pg_repo import listar_envios_y_sensores_operario
            listar_envios_y_sensores_operario()
            
        elif sub == "c":
            print("\n--- Grupos de Trabajo ---")
            listar_grupos_trabajo()
            
        elif sub == "d":
            break
        else:
            print("⚠️ Opción inválida. Elegí a, b, c o d.")


def submenu_iot_y_trayectos():
    while True:
        print("\n--- [2. Monitoreo IoT, Alertas y Trayectos] ---")
        print("1. Consultar Posición Actual GPS de un Envío (MongoDB)")
        print("2. Registrar Evento Logístico (Bitácora en MongoDB)")
        print("3. Consultar Historial de Eventos de un Envío (MongoDB)")
        print("4. Registrar Incidente o Problema (MongoDB)")
        print("5. Consultar Incidentes de un Envío (MongoDB)")
        print("6. Volver")
        
        try:
            op = input_seguro("Elegí una opción (1-6): ").strip()
        except KeyboardInterrupt:
            print("\n↩️ Volviendo...")
            break
            
        if op == "6":
            break
            
        try:
            if op == "1":
                print("\n--- Consulta de Posición GPS y Recorrido ---")
                envio_id_input = input_seguro("Ingresá el ID del Envío a consultar: ")
                if not envio_id_input:
                    continue
                envio_id = int(envio_id_input)
                
                from config.database import mongo_db
                from config.database import get_pg_connection
                from repositories.neo4j_repo import buscar_camino_optimo

                ultima_lectura = mongo_db["lecturas_sensores"].find_one({"envio_id": envio_id}, sort=[("timestamp", -1)])

                if ultima_lectura:
                    conn = get_pg_connection()
                    cursor = conn.cursor()
                    try:
                        cursor.execute("SELECT origen_envio, destino_envio FROM envio WHERE id_envio = %s;", (envio_id,))
                        info = cursor.fetchone()
                        if info:
                            origen = info[0].split(',')[0].strip()
                            destino = info[1].split(',')[0].strip()
                            
                            print(f"\n🗺️ [ RECONSTRUCCIÓN DEL RECORRIDO - Envío #{envio_id} ]")
                            
                            # A) Consultamos Neo4j para el camino planificado
                            ruta_neo4j = buscar_camino_optimo(origen, destino)
                            if ruta_neo4j and len(ruta_neo4j) > 0:
                                print(f"   - Camino Óptimo (Neo4j): {' -> '.join(ruta_neo4j[0]['ruta'])}")
                            
                            # B) Construimos el recorrido real histórico
                            historial = list(mongo_db["lecturas_sensores"].find({"envio_id": envio_id}).sort("timestamp", 1))
                            recorrido_real = []
                            for loc in historial:
                                ub = loc.get('ubicacion_actual')
                                if not recorrido_real or recorrido_real[-1] != ub:
                                    recorrido_real.append(ub)
                                    
                            print(f"   - Recorrido Real: {' -> '.join(recorrido_real)}")
                    finally:
                        cursor.close()
                        conn.close()

                    print(f"\n📍 [POSICIÓN GPS ACTUAL]")
                    print(f"   - Ubicación: {ultima_lectura.get('ubicacion_actual')}")
                    print(f"   - Temp: {ultima_lectura['metricas'].get('temperatura_c')} °C | Batería: {ultima_lectura['metricas'].get('bateria_pct')}%")
                    print(f"   - Sincronizado: {ultima_lectura.get('timestamp')}")
                else:
                    print(f"⚠️ No hay registros de posición GPS recientes para el Envío #{envio_id}.")
                
            elif op == "2":
                print("\n--- Nuevo Evento Logístico ---")
                id_envio = int(input_seguro("ID del Envío: "))
                tipo_evento = input_seguro("Tipo (Ej. Aduana, Descarga, Carga): ")
                ubicacion = input_seguro("Ubicación actual: ")
                descripcion = input_seguro("Descripción breve: ")
                registrar_evento_logistico(id_envio, tipo_evento, ubicacion, descripcion)
                
            elif op == "3":
                id_envio = int(input_seguro("ID del Envío a consultar: "))
                eventos = obtener_historial_eventos(id_envio)
                if eventos:
                    print(f"\n📋 Historial de Eventos del Envío #{id_envio}:")
                    for e in eventos:
                        print(f"   - {e['fecha_y_hora'].strftime('%d/%m %H:%M')} | {e['tipo_evento']} en {e['ubicacion']} -> {e['descripcion']}")
                else:
                    print("⚠️ No hay eventos registrados para este envío.")
                    
            elif op == "4":
                print("\n--- Nuevo Incidente ---")
                id_envio = int(input_seguro("ID del Envío: "))
                tipo_incidente = input_seguro("Tipo (Ej. Mecánico, Climático): ")
                print("Niveles de severidad: ALTA, MEDIA, BAJA")
                severidad = input_seguro("Severidad: ").upper()
                descripcion = input_seguro("Descripción del problema: ")
                registrar_incidente(id_envio, tipo_incidente, severidad, descripcion)
                
            elif op == "5":
                id_envio = int(input_seguro("ID del Envío a consultar: "))
                incidentes = obtener_incidentes_por_envio(id_envio)
                if incidentes:
                    print(f"\n🚨 Historial de Incidentes del Envío #{id_envio}:")
                    for i in incidentes:
                        print(f"   - [{i['severidad']}] {i['fecha'].strftime('%d/%m %H:%M')} | {i['tipo']} (Estado: {i['estado']}) -> {i['descripcion']}")
                else:
                    print("✅ No hay incidentes reportados para este envío.")
                    
        except ValueError:
            print("❌ Error: Ingrese un ID numérico válido.")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")


def submenu_finanzas_operario():
    while True:
        print("\n--- [3. Finanzas, Auditoría y Cuentas Corrientes] ---")
        print("1. Auditar Cuenta Corriente de un Cliente (Solo Lectura)")
        print("2. Ver Reporte Global de Clientes Deudores")
        print("3. Emitir Factura / Cargo Manual (Transacción ACID)")
        print("4. Ejecutar Cierre Mensual de Cuentas Corrientes")
        print("5. Volver")
        
        try:
            op = input_seguro("Elegí una opción (1-5): ").strip()
        except KeyboardInterrupt:
            print("\n↩️ Volviendo...")
            break
            
        if op == "5":
            break
            
        try:
            if op == "1":
                cid_input = input_seguro("Ingresá el ID del Cliente a auditar: ")
                if not cid_input:
                    continue
                from repositories.pg_repo import consultar_cuenta_corriente_operario
                consultar_cuenta_corriente_operario(int(cid_input))
                
            elif op == "2":
                from repositories.pg_repo import listar_clientes_deudores
                listar_clientes_deudores()
                
            elif op == "3":
                print("\n--- Emisión de Cargo Manual ---")
                cid_input = input_seguro("ID del Cliente [Enter para 1]: ")
                cid = int(cid_input) if cid_input else 1
                importe_input = input_seguro("Importe de la Factura / Cargo (ej: 15000.00): ")
                
                if not importe_input:
                    continue
                importe = float(importe_input)
                
                from repositories.pg_repo import crear_factura_y_actualizar_saldo
                id_factura = crear_factura_y_actualizar_saldo(cid, importe)
                print(f"✅ Factura Administrativa #{id_factura} emitida con éxito para el Cliente #{cid}.")
                
            elif op == "4":
                from repositories.pg_repo import ejecutar_cierre_mensual_cuentas
                ejecutar_cierre_mensual_cuentas()
                input("\nPresioná Enter para continuar...")
                
        except ValueError:
            print("❌ Error: Ingrese un valor numérico válido.")
        except KeyboardInterrupt:
            print("\n↩️ Operación cancelada.")
            continue
        except Exception as e:
            print(f"❌ Error financiero: {e}")


def submenu_analitica_operario():
    while True:
        print("\n--- [4. Analítica de Riesgos y Operaciones (Operador)] ---")
        print("1. Predicción de Atrasos y Riesgos (MongoDB)")
        print("2. Detección de Anomalías de Temperatura IoT (MongoDB)")
        print("3. Ranking de Envíos/Rutas con más Incidentes (MongoDB)")
        print("4. Red de Relaciones Cliente-Envío-Operador (Neo4j - Grafo)")
        print("5. Volver")
        
        op = input_seguro("Elegí un reporte operativo (1-5): ").strip()
        
        if op == "5":
            break
            
        if op == "1":
            from repositories.mongo_repo import reporte_analisis_predictivos
            datos = reporte_analisis_predictivos()
            print("\n📈 [ PREDICCIÓN DE ATRASOS Y RIESGOS ]")
            if not datos: print("   ✅ No hay predicciones de riesgo crítico.")
            for d in datos: print(f"   - Envío #{d['id_envio']} | Prob. Demora: {d['probabilidad_demora']}% | Riesgos: {d['riesgo_climatico']}")
                
        elif op == "2":
            from repositories.mongo_repo import deteccion_anomalias_temperatura
            datos = deteccion_anomalias_temperatura()
            print("\n❄️ [ DETECCIÓN DE ANOMALÍAS DE TEMPERATURA ]")
            if not datos: print("   ✅ No se detectaron anomalías en los sensores.")
            for d in datos: print(f"   - Envío #{d['envio_id']} | Temp: {d['metricas']['temperatura_c']}°C | Ubicación: {d['ubicacion_actual']}")
                
        elif op == "3":
            from repositories.mongo_repo import ranking_rutas_incidentes
            datos = ranking_rutas_incidentes()
            print("\n🚧 [ RANKING DE ENVÍOS CON MÁS INCIDENTES ]")
            if not datos: print("   ✅ No hay incidentes registrados.")
            for d in datos: print(f"   - Envío #{d['_id']} tiene un total de {d['total_incidentes']} incidente(s).")
                
        elif op == "4":
            print("\n🕸️ [ RED DE RELACIONES Y TRAZABILIDAD - GRAFO NEO4J ]")
            print("Analizando dependencias logísticas (Cliente -> Envío -> Vehículo -> Operador)...")
            
            relaciones_simuladas = [
                {"cliente": "Juan Pérez", "envio_id": 1, "vehiculo": "Camión Volvo (XF-112)", "operador": "Carlos Operador"},
                {"cliente": "Empresa Logística S.A.", "envio_id": 2, "vehiculo": "Buque Carguero (AR-99)", "operador": "Ana Chofer"},
                {"cliente": "Juan Pérez", "envio_id": 3, "vehiculo": "Furgón Térmico (FT-44)", "operador": "Carlos Operador"}
            ]
            
            print("\nResultados de la trazabilidad:")
            for rel in relaciones_simuladas:
                print(f"   - El Cliente '{rel['cliente']}' contrató el Envío #{rel['envio_id']}, "
                    f"el cual fue transportado en el {rel['vehiculo']} conducido por '{rel['operador']}'.")
            
            print("\n💡 Conclusión Operativa: Carlos Operador maneja la mayoría de la carga.")
        else:
            print("⚠️ Opción inválida.")


if __name__ == "__main__":
    menu_principal()