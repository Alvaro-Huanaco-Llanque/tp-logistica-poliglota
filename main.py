from repositories.redis_repo import actualizar_ultima_posicion, obtener_ultima_posicion
from repositories.mongo_repo import guardar_lectura_iot
from repositories.neo4j_repo import buscar_camino_optimo
from repositories.pg_repo import (
    registrar_inicio_sesion,
    cerrar_sesion_activa,
    obtener_estado_cliente,
    login_cliente,
    login_operario,
    auto_registrar_cliente,
    auto_registrar_operario,
    crear_factura_y_actualizar_saldo,
    abm_cliente_menu,
    abm_envio_contenedor_sensor_menu,
    registrar_pago_cliente,
    consultar_cuenta_corriente,
    registrar_envio_cliente,
    listar_envios_cliente,                     # <-- Agregado aquí
    registrar_envio_con_contenedores_cliente,
    input_seguro
)

def menu_principal():
    while True:
        print("\n=======================================================")
        print("   SISTEMA DE LOGÍSTICA POLÍGLOTA - INICIO DE SESIÓN")
        print("=======================================================")
        print("1. Iniciar Sesión como CLIENTE (Ingresar CUIT y Contraseña)")
        print("2. Iniciar Sesión como OPERARIO (Ingresar Nombre, Apellido y Contraseña)")
        print("3. Registrarse en el Sistema (Nuevo Cliente o Nuevo Operario)")
        print("4. Salir")
        
        op = input("\nSeleccioná una opción (1-4): ").strip()
        
        if op == "1":
            print("\n--- LOGIN CLIENTE ---")
            cuit_input = int(input("Ingresá tu CUIT (solo números): ") or 0)
            password = input("Contraseña: ")
            
            cliente_data = login_cliente(cuit_input, password)
            if not cliente_data:
                print("❌ Credenciales inválidas o CUIT no registrado.")
                continue
                
            if cliente_data["estado_cliente"] == "INACTIVO":
                print(f"⚠️ Hola {cliente_data['razon_social']}: Tu cuenta se encuentra INACTIVA. Un operario debe darla de alta para que puedas operar.")
                # De todas formas permitimos entrar al menú, pero las operaciones con envíos estarán bloqueadas.
                
            usuario_cliente = {
                "id_usuario": cliente_data["id_usuario"],
                "id_cliente": cliente_data["id_cliente"],
                "nombre": cliente_data["razon_social"],
                "estado_cliente": cliente_data["estado_cliente"],
                "rol": "CLIENTE"
            }
            usuario_cliente["id_sesion"] = registrar_inicio_sesion(usuario_cliente["id_usuario"])
            menu_cliente(usuario_cliente)
            
        elif op == "2":
            print("\n--- LOGIN OPERARIO ---")
            nombre = input("Nombre: ")
            apellido = input("Apellido: ")
            password = input("Contraseña: ")
            
            operario_data = login_operario(nombre, apellido, password)
            if not operario_data:
                print("❌ Credenciales incorrectas o usuario sin permisos de operario.")
                continue
                
            usuario_operario = {
                "id_usuario": operario_data["id_usuario"],
                "id_cliente": None,
                "nombre": operario_data["nombre"],
                "rol": "OPERARIO"
            }
            usuario_operario["id_sesion"] = registrar_inicio_sesion(usuario_operario["id_usuario"])
            menu_operario(usuario_operario)
            
        elif op == "3":
            menu_registro()
            
        elif op == "4":
            print("\n👋 ¡Saliendo del sistema!")
            break
        else:
            print("⚠️ Opción inválida.")


def menu_registro():
    print("\n=======================================================")
    print("   REGISTRO EN EL SISTEMA")
    print("=======================================================")
    print("1. Registrarse como NUEVO CLIENTE (Quedará INACTIVO hasta aprobación)")
    print("2. Registrarse como NUEVO OPERARIO")
    print("3. Volver")
    tipo = input("Seleccioná una opción (1-3): ").strip()
    
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
            
            id_cli = auto_registrar_cliente(cuit, razon, email, tel, direccion, pais, nombre_cont, apellido_cont, password)
            print(f"\n✅ ¡Registro exitoso! Tu ID de Cliente es #{id_cli}.")
            print("⚠️ Tu cuenta se encuentra en estado INACTIVO. Un operario deberá activarla para que puedas crear envíos.")
        except Exception as e:
            print(f"❌ Error al registrar cliente: {e}")
            
    elif tipo == "2":
        try:
            nombre = input("Nombre: ")
            apellido = input("Apellido: ")
            email = input("Email: ")
            password = input("Contraseña: ")
            
            id_usr = auto_registrar_operario(nombre, apellido, email, password)
            print(f"\n✅ ¡Operario registrado con éxito! ID de Usuario: #{id_usr}. Ya podés iniciar sesión.")
        except Exception as e:
            print(f"❌ Error al registrar operario: {e}")


def menu_cliente(usuario):
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
        print("5. Solicitar Reporte Analítico")
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
                origen = input_seguro("Origen [Ej: Buenos Aires]: ") or "Buenos Aires"
                destino = input_seguro("Destino [Ej: Rosario]: ") or "Rosario"
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
            mac = input_seguro("MAC del sensor [Enter para AA:BB:CC:11:22:33]: ") or "AA:BB:CC:11:22:33"
            posicion = obtener_ultima_posicion(mac)
            if posicion:
                print("📍 Estado actual del sensor (Redis):")
                for k, v in posicion.items():
                    print(f"   - {k}: {v}")
            else:
                print("⚠️ No hay lecturas recientes.")
                
        elif opcion == "4":
            consultar_cuenta_corriente(usuario['id_cliente'])
            try:
                pagar = input_seguro("\n¿Deseás registrar un pago ahora? (s/n): ").lower()
                if pagar == 's':
                    id_factura = int(input_seguro("ID de la Factura a pagar [Ej: 1]: ") or 1)
                    monto = float(input_seguro("Monto a abonar [Ej: 5000]: ") or 5000.0)
                    medio = input_seguro("Medio de pago [Enter TRANSFERENCIA]: ") or "TRANSFERENCIA"
                    registrar_pago_cliente(usuario['id_cliente'], id_factura, monto, medio)
            except KeyboardInterrupt:
                continue
                
        elif opcion == "5":
            if estado_actual != "ACTIVO":
                print("⛔ Operación bloqueada.")
                continue
            try:
                tipo_rep = input_seguro("Tipo de reporte [Enter para TIEMPOS_ENTREGA]: ") or "TIEMPOS_ENTREGA"
                formato = input_seguro("Formato [Enter para PDF]: ") or "PDF"
                fact_id = crear_factura_y_actualizar_saldo(usuario['id_cliente'], 2500.00)
                print(f"✅ Reporte generado. Cargo de $2500 en Factura #{fact_id}.")
            except KeyboardInterrupt:
                continue
                
        elif opcion == "6":
            try:
                dest = input_seguro("Destinatario [Enter para SOPORTE]: ") or "SOPORTE"
                msg = input_seguro("Mensaje: ")
                print(f"💬 Mensaje enviado a {dest}.")
            except KeyboardInterrupt:
                continue
                
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
        print("1. [ABM] Gestión Operativa (Clientes - Dar de alta/suspender, Envíos, Contenedores)")
        print("2. [IoT y Trayectos] Monitoreo de Sensores, Alertas y Rutas")
        print("3. [Finanzas ACID] Cuentas Corrientes, Facturación y Pagos")
        print("4. [Analítica y Reportes] Rankings y Predicción de Riesgos")
        print("5. Volver al inicio (Cerrar Sesión)")
        
        opcion = input("\nSeleccioná un módulo (1-5): ").strip()
        
        if opcion == "1":
            submenu_abm_operario()
        elif opcion == "2":
            submenu_iot_y_trayectos()
        elif opcion == "3":
            submenu_finanzas_operario()
        elif opcion == "4":
            print("📈 Módulo analítico ejecutado correctamente.")
        elif opcion == "5":
            cerrar_sesion_activa(usuario['id_sesion'])
            print("🔒 Sesión de operario finalizada.")
            break
        else:
            print("⚠️ Opción inválida.")


def submenu_abm_operario():
    while True:
        print("\n--- [1. ABM y Gestión Operativa] ---")
        print("a. ABM Clientes (Dar de alta, suspender, listar)")
        print("b. Gestión de Envíos y Sensores (Listar, Asociar Sensor, Cambiar Estado)")
        print("c. Volver")
        sub = input("Elegí una opción: ").lower().strip()
        if sub == "a":
            abm_cliente_menu()
        elif sub == "b":
            abm_envio_contenedor_sensor_menu()
        elif sub == "c":
            break


def submenu_iot_y_trayectos():
    print("\n--- [2. Monitoreo IoT, Alertas y Trayectos] ---")
    mac = input("MAC del sensor [Enter para AA:BB:CC:11:22:33]: ") or "AA:BB:CC:11:22:33"
    pos = obtener_ultima_posicion(mac)
    print("📍 Posición actual:", pos if pos else "No encontrada")


def submenu_finanzas_operario():
    print("\n--- [3. Finanzas y Cuentas Corrientes] ---")
    cid = int(input("ID del Cliente [Enter para 1]: ") or 1)
    consultar_cuenta_corriente(cid)


if __name__ == "__main__":
    menu_principal()