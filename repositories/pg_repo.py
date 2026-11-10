from config.database import get_pg_connection
from repositories.neo4j_repo import buscar_camino_optimo, registrar_relaciones_envio_grafo

def input_seguro(mensaje):
    """Permite capturar input de consola y maneja Ctrl+C de forma elegante."""
    try:
        return input(mensaje).strip()
    except KeyboardInterrupt:
        print("\n\n↩️ Operación cancelada por el usuario. Volviendo al menú...")
        raise KeyboardInterrupt

def formatear_cuit(cuit_num):
    if not cuit_num:
        return ""
    s = str(cuit_num).zfill(11)
    return f"{s[:2]}-{s[2:10]}-{s[10:]}"

def formatear_telefono(tel_num):
    if not tel_num:
        return ""
    s = str(tel_num)
    if len(s) >= 10:
        return f"{s[:-8]} {s[-8:-4]}-{s[-4:]}"
    return s

# --- SESIONES Y ACCESO POR ROL ---
def registrar_inicio_sesion(id_usuario):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO sesion (id_usuario, estado) VALUES (%s, 'ACTIVA') RETURNING id_sesion;",
            (id_usuario,)
        )
        id_sesion = cursor.fetchone()[0]
        conn.commit()
        return id_sesion
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def cerrar_sesion_activa(id_sesion):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE sesion SET estado = 'CERRADA', fecha_fin = CURRENT_TIMESTAMP WHERE id_sesion = %s;",
            (id_sesion,)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def obtener_usuario_por_rol(id_rol):
    """Permite ingresar directamente seleccionando el rol sin perder el registro de sesión."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id_usuario, id_rol, nombre, apellido, email, estado_usuario
            FROM usuario
            WHERE id_rol = %s AND estado_usuario = TRUE
            ORDER BY id_usuario ASC LIMIT 1;
        """, (id_rol,))
        res = cursor.fetchone()
        if res:
            return {
                "id_usuario": res[0],
                "id_rol": res[1],
                "nombre": f"{res[2]} {res[3]}".strip(),
                "email": res[4],
                "estado": res[5]
            }
        return None
    finally:
        cursor.close()
        conn.close()

# --- MÓDULO 1: ABM MAESTROS (CLIENTES, PROVEEDORES, OPERADORES, USUARIOS Y SESIONES) ---
def listar_clientes_formateados():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id_cliente, razon_social, cuit, email, telefono, direccion, pais, estado_cliente 
            FROM cliente ORDER BY id_cliente ASC;
        """)
        filas = cursor.fetchall()
        if not filas:
            print("   ⚠️ No hay clientes registrados.")
            return
        for c in filas:
            cuit_fmt = formatear_cuit(c[2])
            tel_fmt = formatear_telefono(c[4])
            print(f"   ID: {c[0]} | Razón Social: {c[1]} | CUIT: {cuit_fmt} | Email: {c[3]} | Tel: {tel_fmt} | Dirección: {c[5]} ({c[6]}) | Estado: {c[7]}")
    finally:
        cursor.close()
        conn.close()

def abm_cliente_menu():
    while True:
        print("\n--- [ABM Clientes (Empresas que contratan fletes)] ---")
        print("1. Dar de Alta Nuevo Cliente (y abrir su Cuenta Corriente)")
        print("2. Listar Clientes (incluye Dirección, CUIT y Teléfono)")
        print("3. Modificar Datos de Cliente (Razón Social, Teléfono, Dirección)")
        print("4. Cambiar Estado (ACTIVO / SUSPENDIDO / INACTIVO)")
        print("5. Eliminar Cliente Físicamente")
        print("6. Volver")
        op = input_seguro("Elegí una opción (1-6): ")

        if op == "6":
            break

        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            if op == "1":
                razon = input_seguro("Razón Social del Cliente: ")
                cuit = int(input_seguro("CUIT (11 dígitos sin guiones): "))
                email = input_seguro("Email de contacto: ")
                tel = int(input_seguro("Teléfono (solo números): ") or 1155554444)
                dir_cli = input_seguro("Dirección fiscal: ")
                pais = input_seguro("País [Enter para Argentina]: ") or "Argentina"

                cursor.execute("""
                    INSERT INTO cliente (cuit, razon_social, email, telefono, direccion, pais, estado_cliente)
                    VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVO') RETURNING id_cliente;
                """, (cuit, razon, email, tel, dir_cli, pais))
                id_cli = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO cuenta_corriente (id_cliente, saldo, fecha_de_actualizacion, tipo_entidad)
                    VALUES (%s, 0.00, CURRENT_TIMESTAMP, 'CLIENTE');
                """, (id_cli,))
                conn.commit()
                print(f"✅ Cliente #{id_cli} ('{razon}') dado de alta con Cuenta Corriente abierta.")

            elif op == "2":
                listar_clientes_formateados()

            elif op == "3":
                listar_clientes_formateados()
                id_cli = int(input_seguro("ID del Cliente a modificar: "))
                razon = input_seguro("Nueva Razón Social: ")
                tel = int(input_seguro("Nuevo Teléfono (solo números): "))
                dir_cli = input_seguro("Nueva Dirección: ")
                cursor.execute("""
                    UPDATE cliente SET razon_social = %s, telefono = %s, direccion = %s 
                    WHERE id_cliente = %s;
                """, (razon, tel, dir_cli, id_cli))
                conn.commit()
                print(f"✅ Cliente #{id_cli} actualizado correctamente.")

            elif op == "4":
                id_cli = int(input_seguro("ID del Cliente: "))
                print("Estados: 1. ACTIVO | 2. SUSPENDIDO | 3. INACTIVO")
                est_op = input_seguro("Seleccioná el estado (1-3): ")
                nuevo_estado = {"1": "ACTIVO", "2": "SUSPENDIDO", "3": "INACTIVO"}.get(est_op, "ACTIVO")
                cursor.execute("UPDATE cliente SET estado_cliente = %s WHERE id_cliente = %s;", (nuevo_estado, id_cli))
                conn.commit()
                print(f"✅ Estado del Cliente #{id_cli} cambiado a '{nuevo_estado}'.")

            elif op == "5":
                id_cli = int(input_seguro("ID del Cliente a eliminar: "))
                cursor.execute("DELETE FROM cuenta_corriente WHERE id_cliente = %s;", (id_cli,))
                cursor.execute("DELETE FROM cliente WHERE id_cliente = %s;", (id_cli,))
                conn.commit()
                print(f"🗑️ Cliente #{id_cli} eliminado.")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error en ABM Clientes: {e}")
        finally:
            cursor.close()
            conn.close()

def abm_proveedores_menu():
    while True:
        print("\n--- [ABM Proveedores (Contenedores, Sensores IoT, Flota)] ---")
        print("1. Dar de Alta Proveedor (y abrir su Cuenta Corriente por Pagar)")
        print("2. Listar Proveedores")
        print("3. Modificar Proveedor / Cambiar Estado")
        print("4. Eliminar Proveedor")
        print("5. Volver")
        op = input_seguro("Elegí una opción (1-5): ")
        if op == "5":
            break
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            if op == "1":
                razon = input_seguro("Razón Social del Proveedor: ")
                cuit = int(input_seguro("CUIT (11 dígitos sin guiones): "))
                print("Rubros disponibles: 1. CONTENEDORES | 2. SENSORES_IOT | 3. FLOTA_VEHICULOS")
                r_op = input_seguro("Seleccioná rubro (1-3): ")
                rubro = {"1": "CONTENEDORES", "2": "SENSORES_IOT", "3": "FLOTA_VEHICULOS"}.get(r_op, "CONTENEDORES")
                email = input_seguro("Email comercial: ")
                tel = int(input_seguro("Teléfono (solo números): ") or 1144445555)
                direc = input_seguro("Dirección fiscal: ")
                cursor.execute("""
                    INSERT INTO proveedor (cuit, razon_social, tipo_insumo, email, telefono, direccion, estado)
                    VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVO') RETURNING id_proveedor;
                """, (cuit, razon, rubro, email, tel, direc))
                id_prov = cursor.fetchone()[0]
                cursor.execute("""
                    INSERT INTO cuenta_corriente (id_proveedor, saldo, fecha_de_actualizacion, tipo_entidad)
                    VALUES (%s, 0.00, CURRENT_TIMESTAMP, 'PROVEEDOR');
                """, (id_prov,))
                conn.commit()
                print(f"✅ Proveedor #{id_prov} ('{razon}') dado de alta con Cuenta Corriente activa.")
            elif op == "2":
                cursor.execute("SELECT id_proveedor, razon_social, cuit, tipo_insumo, email, direccion, estado FROM proveedor ORDER BY id_proveedor;")
                print("\n🏢 [ MAESTRO DE PROVEEDORES ]")
                for p in cursor.fetchall():
                    print(f"   - ID #{p[0]} | {p[1]} | CUIT: {formatear_cuit(p[2])} | Rubro: {p[3]} | Email: {p[4]} | Dir: {p[5]} | Estado: {p[6]}")
            elif op == "3":
                idp = int(input_seguro("ID del Proveedor a modificar: "))
                print("Rubros disponibles: 1. CONTENEDORES | 2. SENSORES_IOT | 3. FLOTA_VEHICULOS")
                r_op = input_seguro("Seleccioná nuevo rubro (1-3): ")
                nuevo_rubro = {"1": "CONTENEDORES", "2": "SENSORES_IOT", "3": "FLOTA_VEHICULOS"}.get(r_op, "CONTENEDORES")
                print("Estados disponibles: 1. ACTIVO | 2. INACTIVO")
                e_op = input_seguro("Seleccioná estado (1-2): ")
                nuevo_est = "ACTIVO" if e_op != "2" else "INACTIVO"
                cursor.execute("UPDATE proveedor SET tipo_insumo = %s, estado = %s WHERE id_proveedor = %s;", (nuevo_rubro, nuevo_est, idp))
                conn.commit()
                print(f"✅ Proveedor #{idp} actualizado ({nuevo_rubro} - {nuevo_est}).")
            elif op == "4":
                idp = int(input_seguro("ID del Proveedor a eliminar: "))
                cursor.execute("DELETE FROM cuenta_corriente WHERE id_proveedor = %s;", (idp,))
                cursor.execute("DELETE FROM proveedor WHERE id_proveedor = %s;", (idp,))
                conn.commit()
                print(f"🗑️ Proveedor #{idp} eliminado.")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error en ABM Proveedores: {e}")
        finally:
            cursor.close()
            conn.close()

def abm_operadores_logisticos_menu():
    while True:
        print("\n--- [ABM Operadores Logísticos (Estiba en Puerto, Despacho de Aduana, Última Milla)] ---")
        print("1. Registrar Operador Logístico (y abrir Cuenta Corriente para liquidación)")
        print("2. Listar Operadores Logísticos")
        print("3. Modificar Especialidad / Estado")
        print("4. Eliminar Operador Logístico")
        print("5. Volver")
        op = input_seguro("Elegí una opción (1-5): ")
        if op == "5":
            break
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            mapeo_esp = {
                "1": "CARGA_DESCARGA_PUERTO",
                "2": "DESPACHANTE_ADUANA",
                "3": "TRANSPORTE_ULTIMA_MILLA"
            }
            if op == "1":
                nombre = input_seguro("Nombre / Razón Social del Operador Logístico: ")
                cuit = int(input_seguro("CUIT / DNI (solo números): "))
                print("Especialidades disponibles:")
                print("   1. CARGA_DESCARGA_PUERTO (Estiba y consolidación de contenedores)")
                print("   2. DESPACHANTE_ADUANA (Licencias, papeleo e intervención aduanera)")
                print("   3. TRANSPORTE_ULTIMA_MILLA (Distribución local desde puerto/hangar a domicilio)")
                esp_op = input_seguro("Seleccioná especialidad (1-3): ")
                esp = mapeo_esp.get(esp_op, "DESPACHANTE_ADUANA")
                email = input_seguro("Email de contacto: ")
                tel = int(input_seguro("Teléfono: ") or 1155556666)
                cursor.execute("""
                    INSERT INTO operador_logistico (cuit_dni, nombre_completo, especialidad, email, telefono, estado)
                    VALUES (%s, %s, %s, %s, %s, 'ACTIVO') RETURNING id_operador;
                """, (cuit, nombre, esp, email, tel))
                id_op = cursor.fetchone()[0]
                cursor.execute("""
                    INSERT INTO cuenta_corriente (id_operador, saldo, fecha_de_actualizacion, tipo_entidad)
                    VALUES (%s, 0.00, CURRENT_TIMESTAMP, 'OPERADOR');
                """, (id_op,))
                conn.commit()
                print(f"✅ Operador Logístico #{id_op} ('{nombre}') registrado con especialidad {esp}.")
            elif op == "2":
                cursor.execute("SELECT id_operador, nombre_completo, cuit_dni, especialidad, email, estado FROM operador_logistico ORDER BY id_operador;")
                print("\n👷 [ MAESTRO DE OPERADORES LOGÍSTICOS ]")
                for o in cursor.fetchall():
                    print(f"   - ID #{o[0]} | {o[1]} | CUIT: {formatear_cuit(o[2])} | Especialidad: {o[3]} | Email: {o[4]} | Estado: {o[5]}")
            elif op == "3":
                ido = int(input_seguro("ID del Operador a modificar: "))
                print("Especialidades disponibles:")
                print("   1. CARGA_DESCARGA_PUERTO")
                print("   2. DESPACHANTE_ADUANA")
                print("   3. TRANSPORTE_ULTIMA_MILLA")
                esp_op = input_seguro("Seleccioná la nueva especialidad (1-3): ")
                nueva_esp = mapeo_esp.get(esp_op, "DESPACHANTE_ADUANA")
                print("Estados disponibles: 1. ACTIVO | 2. INACTIVO")
                est_op = input_seguro("Seleccioná el nuevo estado (1-2): ")
                nuevo_est = "ACTIVO" if est_op != "2" else "INACTIVO"
                cursor.execute("UPDATE operador_logistico SET especialidad = %s, estado = %s WHERE id_operador = %s;", (nueva_esp, nuevo_est, ido))
                conn.commit()
                print(f"✅ Operador #{ido} actualizado a especialidad '{nueva_esp}' ({nuevo_est}).")
            elif op == "4":
                ido = int(input_seguro("ID del Operador a eliminar: "))
                cursor.execute("DELETE FROM cuenta_corriente WHERE id_operador = %s;", (ido,))
                cursor.execute("DELETE FROM operador_logistico WHERE id_operador = %s;", (ido,))
                conn.commit()
                print(f"🗑️ Operador #{ido} eliminado.")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error en ABM Operadores: {e}")
        finally:
            cursor.close()
            conn.close()

def abm_usuarios_y_sesiones_menu():
    """ABM de Empleados Internos del ERP, Roles y Auditoría de Sesiones (sin cierre forzoso)."""
    while True:
        print("\n--- [ABM Usuarios Internos del ERP, Roles y Sesiones] ---")
        print("1. Dar de Alta Nuevo Empleado / Usuario Interno")
        print("2. Listar Usuarios Internos y sus Roles")
        print("3. Activar / Desactivar un Usuario")
        print("4. Cambiar Rol de Permisos de un Usuario")
        print("5. Ver Historial de Sesiones Activas y Cerradas")
        print("6. Volver")
        op = input_seguro("Elegí una opción (1-6): ")
        if op == "6":
            break
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            mapeo_rol = {
                1: "GERENTE_OPERACIONES",
                2: "GESTOR_TRAFICO_IOT",
                3: "ANALISTA_FINANZAS",
                4: "ANALISTA_REPORTES"
            }
            if op == "1":
                nombre = input_seguro("Nombre del empleado: ")
                apellido = input_seguro("Apellido: ")
                email = input_seguro("Email corporativo: ")
                pwd = input_seguro("Contraseña: ") or "1234"
                print("Roles: 1: GERENTE_OPERACIONES | 2: GESTOR_TRAFICO_IOT | 3: ANALISTA_FINANZAS | 4: ANALISTA_REPORTES")
                rol = int(input_seguro("Seleccioná Rol (1-4): ") or 1)
                cursor.execute("""
                    INSERT INTO usuario (id_rol, nombre, apellido, email, contrasena_encriptada, estado_usuario)
                    VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id_usuario;
                """, (rol, nombre, apellido, email, pwd))
                uid = cursor.fetchone()[0]
                conn.commit()
                print(f"✅ Usuario interno #{uid} creado con rol {mapeo_rol.get(rol)}.")
            elif op == "2":
                cursor.execute("SELECT id_usuario, nombre, apellido, email, id_rol, estado_usuario FROM usuario ORDER BY id_usuario ASC;")
                print("\n👤 [ PLANTILLA DE USUARIOS DEL ERP ]")
                for u in cursor.fetchall():
                    est = "ACTIVO" if u[5] else "INACTIVO"
                    print(f"   - ID #{u[0]} | {u[1]} {u[2]} ({u[3]}) | Rol: {mapeo_rol.get(u[4], u[4])} | Estado: {est}")
            elif op == "3":
                uid = int(input_seguro("ID del Usuario a activar/desactivar: "))
                est_op = input_seguro("Nuevo estado (1. ACTIVO / 2. INACTIVO): ")
                nuevo_est = True if est_op == "1" else False
                cursor.execute("UPDATE usuario SET estado_usuario = %s WHERE id_usuario = %s;", (nuevo_est, uid))
                conn.commit()
                print(f"✅ Estado del Usuario #{uid} actualizado.")
            elif op == "4":
                uid = int(input_seguro("ID del Usuario: "))
                print("Roles: 1: GERENTE_OPERACIONES | 2: GESTOR_TRAFICO_IOT | 3: ANALISTA_FINANZAS | 4: ANALISTA_REPORTES")
                nuevo_rol = int(input_seguro("Nuevo Rol (1-4): "))
                cursor.execute("UPDATE usuario SET id_rol = %s WHERE id_usuario = %s;", (nuevo_rol, uid))
                conn.commit()
                print(f"✅ Rol del Usuario #{uid} actualizado a {mapeo_rol.get(nuevo_rol)}.")
            elif op == "5":
                cursor.execute("""
                    SELECT s.id_sesion, u.nombre, u.apellido, r.descripcion, s.estado, s.fecha_inicio, s.fecha_fin
                    FROM sesion s 
                    JOIN usuario u ON s.id_usuario = u.id_usuario
                    JOIN rol r ON u.id_rol = r.id_rol
                    ORDER BY s.id_sesion DESC LIMIT 15;
                """)
                print("\n🔐 [ AUDITORÍA DE SESIONES DEL ERP ]")
                for s in cursor.fetchall():
                    fin_str = s[6].strftime('%Y-%m-%d %H:%M') if s[6] else "En curso"
                    print(f"   - Sesión #{s[0]} | {s[1]} {s[2]} ({s[3]}) | Estado: {s[4]} | Inicio: {s[5].strftime('%Y-%m-%d %H:%M')} | Fin: {fin_str}")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error: {e}")
        finally:
            cursor.close()
            conn.close()


# --- MÓDULO 2: ENVÍOS, CONTENEDORES, SENSORES Y FACTURACIÓN DIFERIDA AL ENTREGAR ---
HUBS_PAIS = {
    "BUE": "Argentina",
    "EZE": "Argentina",
    "ROS": "Argentina",
    "COR": "Argentina",
    "MDZ": "Argentina",
    "SCL": "Chile",
    "MAD": "España"
}

def emitir_factura_por_entrega(cursor, id_envio):
    """
    Se ejecuta ÚNICAMENTE cuando un envío pasa a estado ENTREGADO.
    Verifica que no haya sido facturado antes, suma el costo de sus tramos y carga la factura en la cuenta corriente del cliente.
    """
    cursor.execute("SELECT id_cliente, origen_envio, destino_envio FROM envio WHERE id_envio = %s;", (id_envio,))
    env = cursor.fetchone()
    if not env:
        return None
    id_cliente, origen, destino = env

    concepto_busqueda = f"%Envío #{id_envio}%"
    cursor.execute("SELECT id_factura FROM factura WHERE id_cliente = %s AND concepto LIKE %s;", (id_cliente, concepto_busqueda))
    if cursor.fetchone():
        return None  # Ya fue facturado previamente

    cursor.execute("SELECT COALESCE(SUM(costo_tramo), 45000.00) FROM tramo WHERE id_envio = %s;", (id_envio,))
    importe_total = cursor.fetchone()[0] or 45000.00

    concepto = f"Facturación por Entrega Completada - Envío #{id_envio} ({origen} -> {destino})"
    cursor.execute("""
        INSERT INTO factura (id_cliente, importe_total, fecha_emision, estado_factura, tipo_comprobante, concepto)
        VALUES (%s, %s, CURRENT_DATE, 'a_pagar', 'COBRO_CLIENTE', %s) RETURNING id_factura;
    """, (id_cliente, importe_total, concepto))
    id_factura = cursor.fetchone()[0]

    cursor.execute("""
        UPDATE cuenta_corriente 
        SET saldo = saldo + %s, fecha_de_actualizacion = CURRENT_TIMESTAMP 
        WHERE id_cliente = %s;
    """, (importe_total, id_cliente))
    return id_factura, importe_total

def registrar_envio_con_contenedores_cliente(id_cliente, origen, destino, prioridad, lista_contenedores, id_operador=None):
    """
    Registra el envío en estado EN_PREPARACION, vincula contenedores y sensores con sus respectivos proveedores
    y crea el tramo con su operador logístico (si es internacional). NO factura hasta que se entregue.
    """
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT estado_cliente, razon_social FROM cliente WHERE id_cliente = %s;", (id_cliente,))
        cli = cursor.fetchone()
        if not cli or cli[0] != "ACTIVO":
            raise Exception(f"El Cliente #{id_cliente} no existe o no está ACTIVO.")
        razon_social_cliente = cli[1]

        ruta_info = buscar_camino_optimo(origen, destino)
        if ruta_info and len(ruta_info) > 0:
            distancia_base = ruta_info[0]["distancia_total"] or 600
            horas_estimadas = ruta_info[0]["tiempo_total"] or 24
        else:
            distancia_base = 800
            horas_estimadas = 48

        pais_orig = HUBS_PAIS.get(origen.upper(), "Argentina")
        pais_dest = HUBS_PAIS.get(destino.upper(), "Exterior")
        es_internacional = (pais_orig != pais_dest)

        if "MAD" in destino.upper() or prioridad == "ALTA":
            medio_transporte = "AÉREO"
        elif "SCL" in destino.upper() and prioridad == "BAJA":
            medio_transporte = "MARÍTIMO"
        else:
            medio_transporte = "TERRESTRE"

        tarifa_km = {"TERRESTRE": 60, "MARÍTIMO": 90, "AÉREO": 160}
        costo_unitario = tarifa_km.get(medio_transporte, 60)
        costo_estimado_tramo = round(len(lista_contenedores) * (distancia_base * costo_unitario / 10), 2)

        # 1. Crear el Envío (Sin facturar todavía)
        cursor.execute("""
            INSERT INTO envio (id_cliente, origen_envio, destino_envio, fecha_creacion, estado_envio, prioridad)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 'EN_PREPARACION', %s) RETURNING id_envio;
        """, (id_cliente, origen, destino, prioridad))
        id_env = cursor.fetchone()[0]

        # 2. Crear el Tramo (con costo_tramo e id_operador si es internacional)
        dias_estimados = max(1, round(horas_estimadas / 8))
        cursor.execute("""
            INSERT INTO tramo (id_envio, medio_de_transporte, origen, destino, fecha_de_salida, fecha_de_llegada_estimada, id_operador, costo_tramo)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + (%s || ' days')::INTERVAL, %s, %s);
        """, (id_env, medio_transporte, origen, destino, str(dias_estimados), id_operador, costo_estimado_tramo))

        # 3. Crear Contenedores y Sensores guardando el id_proveedor correspondiente
        nombre_prov_grafo = "Flota Propia"
        for c in lista_contenedores:
            id_prov_cont = c.get("id_proveedor_contenedor")
            id_prov_sens = c.get("id_proveedor_sensor")
            tipo_sensor = c.get("tipo_sensor", "TEMPERATURA_GPS")

            cursor.execute("""
                INSERT INTO contenedor (id_envio, codigo_internacional, tipo_contenedor, capacidad, estado_contenedor, id_proveedor)
                VALUES (%s, %s, %s, %s, 'EN_PREPARACION', %s) RETURNING id_contenedor;
            """, (id_env, c["codigo"], c["tipo"], c["capacidad"], id_prov_cont))
            id_cont = cursor.fetchone()[0]

            fab = "Sensitech"
            if id_prov_sens:
                cursor.execute("SELECT razon_social FROM proveedor WHERE id_proveedor = %s;", (id_prov_sens,))
                pr_row = cursor.fetchone()
                if pr_row:
                    fab = pr_row[0]
                    nombre_prov_grafo = pr_row[0]

            cursor.execute("""
                INSERT INTO sensor_iot (id_contenedor, tipo_sensor, fabricante, fecha_instalacion, estado_sensor, id_proveedor)
                VALUES (%s, %s, %s, CURRENT_DATE, TRUE, %s);
            """, (id_cont, tipo_sensor, fab, id_prov_sens))

        # 4. Obtener nombre del operador para sincronizar con Neo4j
        nombre_op_grafo = "Tránsito Terrestre Nacional (Sin Operador Externo)"
        if id_operador:
            cursor.execute("SELECT nombre_completo FROM operador_logistico WHERE id_operador = %s;", (id_operador,))
            op_row = cursor.fetchone()
            if op_row:
                nombre_op_grafo = op_row[0]

        conn.commit()
        registrar_relaciones_envio_grafo(id_env, razon_social_cliente, nombre_op_grafo, nombre_prov_grafo, origen, destino)

        alcance_str = "INTERNACIONAL" if es_internacional else "NACIONAL"
        print(f"\n✅ Envío #{id_env} ({alcance_str}) registrado en estado 'EN_PREPARACION' para '{razon_social_cliente}'.")
        print(f"   - Tramo planificado: {origen} -> {destino} vía {medio_transporte} ({distancia_base} km | Costo operativo: ${costo_estimado_tramo}).")
        print(f"   - Nota comercial: La factura se emitirá automáticamente cuando el envío pase a estado 'ENTREGADO'.")
        return id_env
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def abm_envio_contenedor_sensor_menu():
    while True:
        print("\n--- [Gestión de Envíos, Contenedores y Sensores] ---")
        print("1. Listar Envíos, Contenedores y Sensores (con sus Proveedores)")
        print("2. Asociar Nuevo Sensor IoT a un Contenedor")
        print("3. Cambiar Estado de un Envío (Si pasa a ENTREGADO se factura automáticamente)")
        print("4. Cambiar Estado de un Contenedor (Físico)")
        print("5. Cambiar Estado de un Sensor IoT (Activar/Desactivar)")
        print("6. Volver")
        
        op = input_seguro("Elegí una opción (1-6): ")
        if op == "6":
            break
            
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            if op == "1":
                cliente_filtrar = input_seguro("Ingresá el ID del Cliente (Dejá vacío para ver todos): ")
                query_envios = """
                    SELECT e.id_envio, e.id_cliente, c.razon_social, e.origen_envio, e.destino_envio, e.estado_envio 
                    FROM envio e JOIN cliente c ON e.id_cliente = c.id_cliente
                """
                query_cont = """
                    SELECT co.id_contenedor, co.id_envio, co.codigo_internacional, co.tipo_contenedor, 
                           co.capacidad, co.estado_contenedor, co.id_proveedor, COALESCE(p.razon_social, 'Sin Proveedor')
                    FROM contenedor co LEFT JOIN proveedor p ON co.id_proveedor = p.id_proveedor
                """
                params = ()
                if cliente_filtrar:
                    query_envios += " WHERE e.id_cliente = %s"
                    query_cont += " WHERE co.id_envio IN (SELECT id_envio FROM envio WHERE id_cliente = %s)"
                    params = (int(cliente_filtrar),)
                
                query_envios += " ORDER BY e.id_envio ASC;"
                query_cont += " ORDER BY co.id_contenedor ASC;"

                cursor.execute(query_envios, params)
                print("\n📦 Envíos Registrados:")
                for e in cursor.fetchall():
                    print(f"   Envío #{e[0]} | Cliente #{e[1]} ({e[2]}) | Ruta: {e[3]} -> {e[4]} | Estado: {e[5]}")
                    
                cursor.execute(query_cont, params)
                print("\n🚛 Contenedores Físicos:")
                for c in cursor.fetchall():
                    print(f"   Contenedor #{c[0]} | Envío #{c[1]} | Cód: {c[2]} | Tipo: {c[3]} | Cap: {c[4]}kg | Estado: {c[5]} | Proveedor ID #{c[6]} ({c[7]})")
                    
                cursor.execute("""
                    SELECT s.id_sensor, s.id_contenedor, s.tipo_sensor, s.fabricante, s.estado_sensor, s.id_proveedor
                    FROM sensor_iot s ORDER BY s.id_sensor ASC;
                """)
                print("\n📡 Sensores IoT:")
                for s in cursor.fetchall():
                    estado_txt = "ACTIVO" if s[4] else "INACTIVO"
                    print(f"   Sensor #{s[0]} | Contenedor #{s[1]} | Tipo: {s[2]} | Proveedor ID #{s[5]} ({s[3]}) | Estado: {estado_txt}")
                    
            elif op == "2":
                print("\n--- Asociar Sensor IoT a un Contenedor ---")
                id_cont = int(input_seguro("ID del Contenedor donde se instala: ") or 1)
                print("Tipos de Sensor: 1. TEMPERATURA_GPS | 2. HUMEDAD_GPS | 3. MULTIPARAMETRICO_GPS")
                t_op = input_seguro("Seleccioná tipo (1-3): ")
                tipo_s = {"1": "TEMPERATURA_GPS", "2": "HUMEDAD_GPS", "3": "MULTIPARAMETRICO_GPS"}.get(t_op, "TEMPERATURA_GPS")
                
                cursor.execute("SELECT id_proveedor, razon_social FROM proveedor WHERE tipo_insumo = 'SENSORES_IOT';")
                provs = cursor.fetchall()
                for p in provs:
                    print(f"   - Proveedor ID #{p[0]}: {p[1]}")
                id_prov = int(input_seguro("ID del Proveedor del Sensor: ") or (provs[0][0] if provs else 1))
                cursor.execute("SELECT razon_social FROM proveedor WHERE id_proveedor = %s;", (id_prov,))
                pr_row = cursor.fetchone()
                fab = pr_row[0] if pr_row else "Sensitech"
                
                cursor.execute("""
                    INSERT INTO sensor_iot (id_contenedor, tipo_sensor, fabricante, fecha_instalacion, estado_sensor, id_proveedor)
                    VALUES (%s, %s, %s, CURRENT_DATE, TRUE, %s) RETURNING id_sensor;
                """, (id_cont, tipo_s, fab, id_prov))
                id_sens = cursor.fetchone()[0]
                conn.commit()
                print(f"✅ Sensor IoT #{id_sens} ({tipo_s}) del proveedor '{fab}' asociado al Contenedor #{id_cont}.")
                
            elif op == "3":
                print("\n--- Cambiar Estado de un Envío (Administrativo) ---")
                id_env = int(input_seguro("ID del Envío: "))
                print("Estados: 1. EN_PREPARACION | 2. EN_TRANSITO | 3. DEMORADO | 4. ENTREGADO | 5. CANCELADO")
                est_op = input_seguro("Seleccioná (1-5): ").strip()
                mapeo_estados = {"1": "EN_PREPARACION", "2": "EN_TRANSITO", "3": "DEMORADO", "4": "ENTREGADO", "5": "CANCELADO"}
                nuevo_est = mapeo_estados.get(est_op, "EN_TRANSITO")
                
                cursor.execute("UPDATE envio SET estado_envio = %s WHERE id_envio = %s;", (nuevo_est, id_env))
                if nuevo_est == "ENTREGADO":
                    cursor.execute("UPDATE contenedor SET estado_contenedor = 'DESCARGADO' WHERE id_envio = %s;", (id_env,))
                    res_fac = emitir_factura_por_entrega(cursor, id_env)
                    if res_fac:
                        print(f"✨ [FACTURACIÓN AUTOMÁTICA POR ENTREGA]: Se emitió la Factura #{res_fac[0]} por ${res_fac[1]} al cliente.")
                conn.commit()
                print(f"✅ Envío #{id_env} actualizado a '{nuevo_est}'.")

            elif op == "4":
                id_cont = int(input_seguro("ID del Contenedor: "))
                print("Estados: 1. EN_PREPARACION | 2. EN_TRANSITO | 3. DEMORADO | 4. DESCARGADO")
                est_op = input_seguro("Seleccioná (1-4): ").strip()
                mapeo_estados = {"1": "EN_PREPARACION", "2": "EN_TRANSITO", "3": "DEMORADO", "4": "DESCARGADO"}
                nuevo_est = mapeo_estados.get(est_op, "EN_TRANSITO")
                cursor.execute("UPDATE contenedor SET estado_contenedor = %s WHERE id_contenedor = %s;", (nuevo_est, id_cont))
                conn.commit()
                print(f"✅ Contenedor #{id_cont} actualizado a '{nuevo_est}'.")

            elif op == "5":
                id_sens = int(input_seguro("ID del Sensor: "))
                print("Estados: 1. ACTIVO | 2. INACTIVO")
                est_op = input_seguro("Seleccioná (1-2): ").strip()
                nuevo_est_bool = True if est_op == "1" else False
                cursor.execute("UPDATE sensor_iot SET estado_sensor = %s WHERE id_sensor = %s;", (nuevo_est_bool, id_sens))
                conn.commit()
                print(f"✅ Sensor #{id_sens} actualizado a '{'ACTIVO' if nuevo_est_bool else 'INACTIVO'}'.")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error: {e}")
        finally:
            cursor.close()
            conn.close()


# --- MÓDULO 6: REPORTES OPERATIVOS Y ANALÍTICOS ---
def reporte_envios_por_pais():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN origen_envio IN ('BUE', 'EZE', 'ROS', 'COR', 'MDZ') OR origen_envio LIKE '%Argentina%' THEN 'Argentina'
                    WHEN origen_envio = 'SCL' OR origen_envio LIKE '%Chile%' THEN 'Chile'
                    WHEN origen_envio = 'MAD' OR origen_envio LIKE '%España%' THEN 'España'
                    ELSE 'Otros'
                END as pais_origen,
                COUNT(id_envio) as total_envios
            FROM envio
            GROUP BY pais_origen 
            ORDER BY total_envios DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_envios_por_estado():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT estado_envio, COUNT(id_envio) as total FROM envio GROUP BY estado_envio ORDER BY total DESC;")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_envios_por_cliente():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.razon_social, COUNT(e.id_envio)
            FROM envio e JOIN cliente c ON e.id_cliente = c.id_cliente
            GROUP BY c.razon_social ORDER BY COUNT(e.id_envio) DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_envios_demorados():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_envio, id_cliente, origen_envio, destino_envio FROM envio WHERE estado_envio = 'DEMORADO';")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_tiempos_envio_por_cliente():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.razon_social, 
                MAX(EXTRACT(EPOCH FROM (t.fecha_de_llegada_estimada - t.fecha_de_salida))/86400) as max_dias,
                MIN(EXTRACT(EPOCH FROM (t.fecha_de_llegada_estimada - t.fecha_de_salida))/86400) as min_dias
            FROM envio e
            JOIN cliente c ON e.id_cliente = c.id_cliente
            JOIN tramo t ON e.id_envio = t.id_envio
            GROUP BY c.razon_social;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_tiempos_promedio_general():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (fecha_de_llegada_estimada - fecha_de_salida))/86400), 0)
            FROM tramo;
        """)
        return round(cursor.fetchone()[0], 1)
    finally:
        cursor.close()
        conn.close()

def reporte_costos_por_tipo_transporte():
    """Devuelve: medio_de_transporte, cantidad_tramos, costo_total ($), costo_promedio ($)."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT medio_de_transporte, 
                   COUNT(*) as cantidad_tramos,
                   COALESCE(SUM(costo_tramo), 0) as costo_total,
                   COALESCE(ROUND(AVG(costo_tramo), 2), 0) as costo_promedio
            FROM tramo
            GROUP BY medio_de_transporte 
            ORDER BY costo_total DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def ranking_clientes_por_volumen():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.razon_social, SUM(co.capacidad) as volumen_total_kg, COUNT(co.id_contenedor) as total_contenedores
            FROM cliente c
            JOIN envio e ON c.id_cliente = e.id_cliente
            JOIN contenedor co ON e.id_envio = co.id_envio
            GROUP BY c.razon_social
            ORDER BY volumen_total_kg DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def analisis_historico_desempeno():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT estado_envio, COUNT(id_envio) 
            FROM envio 
            GROUP BY estado_envio;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


# --- MÓDULO 7: FINANZAS ACID (CUENTAS POR COBRAR DE CLIENTES Y CUENTAS POR PAGAR A PROVEEDORES/OPERADORES) ---
def registrar_cobro_factura_cliente(cliente_id, id_factura):
    """Registra el cobro cuando un cliente abona una factura a la empresa logística (Transacción ACID)."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT importe_total, estado_factura 
            FROM factura 
            WHERE id_factura = %s AND id_cliente = %s FOR UPDATE;
        """, (id_factura, cliente_id))
        factura = cursor.fetchone()
        if not factura:
            print("❌ La factura indicada no existe o no pertenece a este cliente.")
            return
            
        importe, estado_fac = factura[0], factura[1]
        if estado_fac == "PAGADA":
            print("⚠️ Esta factura ya figura como PAGADA.")
            return

        print("\n--- Medio de Cobro Recibido del Cliente ---")
        print("1. TRANSFERENCIA BANCARIA CBU")
        print("2. CHEQUE ELECTRÓNICO (ECHEQ)")
        print("3. DEPÓSITO BANCARIO")
        op_med = input_seguro("Seleccioná medio (1-3) [Enter para Transferencia]: ") or "1"
        medio_pago = {"1": "TRANSFERENCIA", "2": "ECHEQ", "3": "DEPOSITO"}.get(op_med, "TRANSFERENCIA")

        cursor.execute("""
            INSERT INTO pago (id_factura, monto, fecha, medio_de_pago) 
            VALUES (%s, %s, CURRENT_TIMESTAMP, %s) RETURNING id_pago;
        """, (id_factura, importe, medio_pago))
        id_pago = cursor.fetchone()[0]

        cursor.execute("UPDATE factura SET estado_factura = 'PAGADA' WHERE id_factura = %s;", (id_factura,))

        cursor.execute("""
            UPDATE cuenta_corriente 
            SET saldo = GREATEST(0, saldo - %s), fecha_de_actualizacion = CURRENT_TIMESTAMP 
            WHERE id_cliente = %s;
        """, (importe, cliente_id))

        conn.commit()
        print(f"\n✅ Cobro registrado con éxito (Recibo #{id_pago} por ${importe} vía {medio_pago}).")
        print(f"📉 Se descontaron ${importe} de la deuda en Cuenta Corriente del Cliente #{cliente_id}.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al registrar el cobro: {e}")
    finally:
        cursor.close()
        conn.close()

def crear_factura_y_actualizar_saldo(cliente_id, importe_total, concepto="Cargo Operativo / Servicio Logístico"):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO factura (id_cliente, importe_total, fecha_emision, estado_factura, tipo_comprobante, concepto) 
            VALUES (%s, %s, CURRENT_DATE, 'a_pagar', 'COBRO_CLIENTE', %s) RETURNING id_factura;
        """, (cliente_id, importe_total, concepto))
        id_factura = cursor.fetchone()[0]
        cursor.execute("""
            UPDATE cuenta_corriente 
            SET saldo = saldo + %s, fecha_de_actualizacion = CURRENT_TIMESTAMP 
            WHERE id_cliente = %s;
        """, (importe_total, cliente_id))
        conn.commit()
        return id_factura
    except Exception as e:
        conn.rollback()
        raise Exception(f"Error en transacción ACID: {e}")
    finally:
        cursor.close()
        conn.close()

def consultar_cuenta_corriente(cliente_id):
    """Panel interno de Tesorería: Cuentas por Cobrar de un Cliente."""
    while True:
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT razon_social, cuit, estado_cliente FROM cliente WHERE id_cliente = %s;", (cliente_id,))
            cli = cursor.fetchone()
            if not cli:
                print(f"⚠️ No existe el Cliente #{cliente_id}.")
                return
            razon_social, cuit_cli, est_cli = cli

            cursor.execute("SELECT id_cuenta, saldo, fecha_de_actualizacion FROM cuenta_corriente WHERE id_cliente = %s;", (cliente_id,))
            cuenta = cursor.fetchone()
            if not cuenta:
                cursor.execute("""
                    INSERT INTO cuenta_corriente (id_cliente, saldo, fecha_de_actualizacion, tipo_entidad) 
                    VALUES (%s, 0.00, CURRENT_TIMESTAMP, 'CLIENTE') RETURNING id_cuenta, saldo, fecha_de_actualizacion;
                """, (cliente_id,))
                conn.commit()
                cuenta = cursor.fetchone()

            id_cuenta, saldo_deudor, fecha_act = cuenta

            cursor.execute("""
                SELECT COALESCE(SUM(importe_total), 0) 
                FROM factura 
                WHERE id_cliente = %s AND LOWER(estado_factura) IN ('a_pagar', 'vencido');
            """, (cliente_id,))
            deuda_facturada = cursor.fetchone()[0]

            print(f"\n==================================================================")
            print(f"   CUENTA CORRIENTE COMERCIAL (CUENTAS POR COBRAR - Cuenta #{id_cuenta})")
            print(f"   Cliente: {razon_social} (CUIT: {formatear_cuit(cuit_cli)}) | Estado: {est_cli}")
            print(f"   Deuda Total Pendiente de Cobro: ${deuda_facturada}")
            print(f"   Última actualización contable: {fecha_act.strftime('%Y-%m-%d %H:%M')}")
            print(f"==================================================================")

            cursor.execute("""
                SELECT id_factura, importe_total, fecha_emision, COALESCE(concepto, 'Flete Logístico')
                FROM factura 
                WHERE id_cliente = %s AND LOWER(estado_factura) = 'vencido'
                ORDER BY fecha_emision ASC;
            """, (cliente_id,))
            vencidas = cursor.fetchall()
            print("\n🔴 [ FACTURAS VENCIDAS IMPAGAS (MORA) ]")
            if vencidas:
                for f in vencidas:
                    print(f"   - Factura #{f[0]} | Emisión: {f[2]} | Concepto: {f[3]} | Importe: ${f[1]}")
            else:
                print("   Sin facturas vencidas.")

            cursor.execute("""
                SELECT id_factura, importe_total, fecha_emision, fecha_emision + INTERVAL '30 days' as vto, COALESCE(concepto, 'Flete Logístico')
                FROM factura 
                WHERE id_cliente = %s AND LOWER(estado_factura) = 'a_pagar'
                ORDER BY fecha_emision ASC;
            """, (cliente_id,))
            a_vencer = cursor.fetchall()
            print("\n🟡 [ FACTURAS EMITIDAS PENDIENTES DE COBRO ]")
            if a_vencer:
                for f in a_vencer:
                    vto_str = f[3].strftime('%d/%m/%Y') if f[3] else '30 días'
                    print(f"   - Factura #{f[0]} | Vto: {vto_str} | Concepto: {f[4]} | Importe: ${f[1]}")
            else:
                print("   Sin facturas pendientes.")

            cursor.execute("""
                SELECT p.id_pago, p.id_factura, p.monto, p.fecha, p.medio_de_pago 
                FROM pago p JOIN factura f ON p.id_factura = f.id_factura
                WHERE f.id_cliente = %s ORDER BY p.fecha DESC;
            """, (cliente_id,))
            pagos = cursor.fetchall()
            print("\n🟢 [ HISTORIAL DE COBROS RECIBIDOS DEL CLIENTE ]")
            if pagos:
                for p in pagos:
                    print(f"   - Recibo #{p[0]} | Fecha: {p[3].strftime('%d/%m/%Y')} | Canceló Factura #{p[1]} | Monto Cobrado: ${p[2]} | Vía: {p[4]}")
            else:
                print("   Sin cobros registrados.")

        except Exception as e:
            print(f"❌ Error al consultar cuenta corriente: {e}")
            break
        finally:
            cursor.close()
            conn.close()

        print("\n------------------------------------------------------------------")
        print("   OPERACIONES DE TESORERÍA SOBRE EL CLIENTE:")
        print("   1. Registrar Pago / Cobro Recibido del Cliente (Cancelar Factura por ID)")
        print("   2. Emitir Factura / Cargo Adicional Manual al Cliente")
        print("   3. Volver al módulo de Finanzas")
        
        op = input_seguro("Seleccioná una opción (1-3): ")
        if op == "1":
            fid_input = input_seguro("Ingresá el ID de la Factura abonada por el cliente: ")
            if fid_input.isdigit():
                registrar_cobro_factura_cliente(cliente_id, int(fid_input))
        elif op == "2":
            concepto = input_seguro("Concepto del cargo (Ej. Estadía en Puerto / Reporte Especial): ") or "Cargo Logístico Adicional"
            monto_input = input_seguro("Importe a facturar ($): ")
            if monto_input:
                fid = crear_factura_y_actualizar_saldo(cliente_id, float(monto_input), concepto)
                print(f"✅ Factura #{fid} emitida por ${monto_input} y cargada a la deuda del cliente.")
        elif op == "3":
            break

def gestionar_pagos_proveedores_y_operadores_menu():
    """Cuentas por Pagar: Facturación y Pagos a Proveedores de Contenedores/Sensores y Operadores Logísticos."""
    while True:
        print("\n--- [Cuentas por Pagar: Proveedores y Operadores Logísticos] ---")
        print("1. Registrar Factura de Proveedor (Alquiler Contenedor / Compra Sensor / Flota)")
        print("2. Registrar Liquidación de Operador Logístico (Aduana / Estiba Puerto / Última Milla)")
        print("3. Ver Estado de Deuda con Proveedores y Operadores Logísticos")
        print("4. Emitir Orden de Pago a Proveedor u Operador Logístico (Transacción ACID)")
        print("5. Volver")
        op = input_seguro("Elegí una opción (1-5): ")
        if op == "5":
            break
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            if op == "1":
                cursor.execute("SELECT id_proveedor, razon_social, tipo_insumo FROM proveedor ORDER BY id_proveedor;")
                for p in cursor.fetchall():
                    print(f"   - Proveedor ID #{p[0]}: {p[1]} ({p[2]})")
                idp = int(input_seguro("ID del Proveedor: "))
                concepto = input_seguro("Concepto (Ej. Alquiler Contenedores / Provisión Sensores IoT): ")
                monto = float(input_seguro("Importe de la factura ($): "))
                cursor.execute("""
                    INSERT INTO factura (id_proveedor, importe_total, fecha_emision, estado_factura, tipo_comprobante, concepto)
                    VALUES (%s, %s, CURRENT_DATE, 'a_pagar', 'PAGO_PROVEEDOR', %s) RETURNING id_factura;
                """, (idp, monto, concepto))
                fid = cursor.fetchone()[0]
                cursor.execute("""
                    UPDATE cuenta_corriente SET saldo = saldo + %s, fecha_de_actualizacion = CURRENT_TIMESTAMP
                    WHERE id_proveedor = %s;
                """, (monto, idp))
                conn.commit()
                print(f"✅ Factura de Proveedor #{fid} registrada por ${monto}.")
            elif op == "2":
                cursor.execute("SELECT id_operador, nombre_completo, especialidad FROM operador_logistico ORDER BY id_operador;")
                for o in cursor.fetchall():
                    print(f"   - Operador ID #{o[0]}: {o[1]} ({o[2]})")
                ido = int(input_seguro("ID del Operador Logístico: "))
                concepto = input_seguro("Concepto (Ej. Honorarios Despacho Aduanero / Descarga): ")
                monto = float(input_seguro("Importe a liquidar ($): "))
                cursor.execute("""
                    INSERT INTO factura (id_operador, importe_total, fecha_emision, estado_factura, tipo_comprobante, concepto)
                    VALUES (%s, %s, CURRENT_DATE, 'a_pagar', 'PAGO_OPERADOR', %s) RETURNING id_factura;
                """, (ido, monto, concepto))
                fid = cursor.fetchone()[0]
                cursor.execute("""
                    UPDATE cuenta_corriente SET saldo = saldo + %s, fecha_de_actualizacion = CURRENT_TIMESTAMP
                    WHERE id_operador = %s;
                """, (monto, ido))
                conn.commit()
                print(f"✅ Liquidación de Operador #{fid} registrada por ${monto}.")
            elif op == "3":
                cursor.execute("""
                    SELECT f.id_factura, f.tipo_comprobante, COALESCE(p.razon_social, o.nombre_completo) AS titular,
                           f.concepto, f.importe_total, f.estado_factura
                    FROM factura f
                    LEFT JOIN proveedor p ON f.id_proveedor = p.id_proveedor
                    LEFT JOIN operador_logistico o ON f.id_operador = o.id_operador
                    WHERE f.tipo_comprobante IN ('PAGO_PROVEEDOR', 'PAGO_OPERADOR')
                    ORDER BY f.id_factura DESC;
                """)
                print("\n📑 [ OBLIGACIONES A PAGAR A PROVEEDORES Y OPERADORES ]")
                filas = cursor.fetchall()
                if not filas:
                    print("   Sin comprobantes registrados.")
                for f in filas:
                    print(f"   - Comprobante #{f[0]} ({f[1]}) | Acreedor: {f[2]} | Concepto: {f[3]} | Monto: ${f[4]} | Estado: {f[5]}")
            elif op == "4":
                fid = int(input_seguro("ID del Comprobante a pagar desde Tesorería: "))
                medio = input_seguro("Medio de pago [TRANSFERENCIA / CHEQUE]: ").upper() or "TRANSFERENCIA"
                cursor.execute("""
                    SELECT importe_total, estado_factura, id_proveedor, id_operador 
                    FROM factura WHERE id_factura = %s FOR UPDATE;
                """, (fid,))
                fac = cursor.fetchone()
                if not fac or fac[1] == "PAGADA":
                    print("⚠️ Comprobante inexistente o ya pagado.")
                    continue
                monto, _, idp, ido = fac
                cursor.execute("INSERT INTO pago (id_factura, monto, fecha, medio_de_pago) VALUES (%s, %s, CURRENT_TIMESTAMP, %s);", (fid, monto, medio))
                cursor.execute("UPDATE factura SET estado_factura = 'PAGADA' WHERE id_factura = %s;", (fid,))
                if idp:
                    cursor.execute("UPDATE cuenta_corriente SET saldo = GREATEST(0, saldo - %s), fecha_de_actualizacion = CURRENT_TIMESTAMP WHERE id_proveedor = %s;", (monto, idp))
                elif ido:
                    cursor.execute("UPDATE cuenta_corriente SET saldo = GREATEST(0, saldo - %s), fecha_de_actualizacion = CURRENT_TIMESTAMP WHERE id_operador = %s;", (monto, ido))
                conn.commit()
                print(f"✅ Orden de Pago emitida por ${monto} vía {medio}. Cuenta corriente del acreedor saldada.")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error financiero: {e}")
        finally:
            cursor.close()
            conn.close()

def listar_clientes_deudores():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.id_cliente, c.razon_social, SUM(f.importe_total) as deuda_pendiente, COUNT(f.id_factura),
                   SUM(CASE WHEN LOWER(f.estado_factura) = 'vencido' THEN f.importe_total ELSE 0 END) as mora_vencida
            FROM cliente c
            JOIN factura f ON c.id_cliente = f.id_cliente
            WHERE LOWER(f.estado_factura) IN ('a_pagar', 'vencido')
            GROUP BY c.id_cliente, c.razon_social
            ORDER BY deuda_pendiente DESC;
        """)
        deudores = cursor.fetchall()
        print("\n==================================================================")
        print("   ⚠️ ESTADO DE DEUDORES POR COBRAR (CLIENTES CON FACTURAS IMPAGAS)")
        print("==================================================================")
        if not deudores:
            print("   ✅ Todos los clientes están al día.")
        else:
            for m in deudores:
                print(f"   - Cliente #{m[0]} ({m[1]}) | Deuda Total: ${m[2]} (Vencida en mora: ${m[4]}) | Facturas impagas: {m[3]}")
    finally:
        cursor.close()
        conn.close()

def ejecutar_cierre_mensual_cuentas():
    """
    Proceso periódico contable:
    1. Pasa a estado 'vencido' las facturas emitidas hace más de 30 días no abonadas.
    2. Consolida el balance de Cuentas por Cobrar (Clientes) vs Cuentas por Pagar (Proveedores y Operadores).
    """
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE factura 
            SET estado_factura = 'vencido' 
            WHERE LOWER(estado_factura) = 'a_pagar' AND fecha_emision < CURRENT_DATE - INTERVAL '30 days'
            RETURNING id_factura;
        """)
        vencidas = cursor.fetchall()
        
        cursor.execute("""
            SELECT tipo_entidad, COUNT(*), COALESCE(SUM(saldo), 0)
            FROM cuenta_corriente
            GROUP BY tipo_entidad;
        """)
        balances = cursor.fetchall()
        conn.commit()
        
        print("\n📅 [ CIERRE MENSUAL CONTABLE DE CUENTAS CORRIENTES EJECUTADO ]")
        print(f"   - Facturas que entraron en mora ('VENCIDO' > 30 días): {len(vencidas)}")
        for tipo, cant, total in balances:
            etiqueta = "Cuentas por Cobrar (CLIENTES)" if tipo == "CLIENTE" else f"Cuentas por Pagar ({tipo}ES)"
            print(f"   - {etiqueta}: {cant} cuenta(s) activas | Saldo acumulado: ${total}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en cierre mensual: {e}")
    finally:
        cursor.close()
        conn.close()