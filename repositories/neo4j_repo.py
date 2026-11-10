from config.database import neo4j_driver

def inicializar_red_hubs_neo4j():
    """Crea nodos de Hubs Logísticos reales con latitud y longitud y sus tramos conectados."""
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        query = """
        CREATE (bue:HubLogistico {codigo: 'BUE', nombre: 'Puerto Buenos Aires', tipo: 'PUERTO', pais: 'Argentina', lat: -34.5885, lon: -58.3702})
        CREATE (eze:HubLogistico {codigo: 'EZE', nombre: 'Aeropuerto Ezeiza', tipo: 'AEROPUERTO', pais: 'Argentina', lat: -34.8222, lon: -58.5358})
        CREATE (ros:HubLogistico {codigo: 'ROS', nombre: 'Centro Distribución Rosario', tipo: 'DEPOSITO', pais: 'Argentina', lat: -32.9442, lon: -60.6505})
        CREATE (cor:HubLogistico {codigo: 'COR', nombre: 'Hub Logístico Córdoba', tipo: 'DEPOSITO', pais: 'Argentina', lat: -31.4201, lon: -64.1888})
        CREATE (mdz:HubLogistico {codigo: 'MDZ', nombre: 'Aduana Cristo Redentor Mendoza', tipo: 'ADUANA', pais: 'Argentina', lat: -32.8277, lon: -70.0706})
        CREATE (scl:HubLogistico {codigo: 'SCL', nombre: 'Puerto San Antonio Chile', tipo: 'PUERTO', pais: 'Chile', lat: -33.5933, lon: -71.6153})
        CREATE (mad:HubLogistico {codigo: 'MAD', nombre: 'Hub Carga Barajas Madrid', tipo: 'AEROPUERTO', pais: 'España', lat: 40.4719, lon: -3.5626})

        CREATE (bue)-[:TRAMO_RUTA {medio: 'TERRESTRE', distancia_km: 300, tiempo_hs: 4, costo_base: 45000}]->(ros)
        CREATE (ros)-[:TRAMO_RUTA {medio: 'TERRESTRE', distancia_km: 400, tiempo_hs: 5, costo_base: 60000}]->(cor)
        CREATE (cor)-[:TRAMO_RUTA {medio: 'TERRESTRE', distancia_km: 600, tiempo_hs: 8, costo_base: 95000}]->(mdz)
        CREATE (bue)-[:TRAMO_RUTA {medio: 'TERRESTRE', distancia_km: 1050, tiempo_hs: 14, costo_base: 150000}]->(mdz)
        CREATE (mdz)-[:TRAMO_RUTA {medio: 'TERRESTRE', distancia_km: 200, tiempo_hs: 5, costo_base: 80000}]->(scl)
        CREATE (bue)-[:TRAMO_RUTA {medio: 'TERRESTRE', distancia_km: 35, tiempo_hs: 1, costo_base: 15000}]->(eze)
        CREATE (eze)-[:TRAMO_RUTA {medio: 'AEREO', distancia_km: 10050, tiempo_hs: 12, costo_base: 850000}]->(mad)
        """
        session.run(query)
        print("✅ Red geográfica de Hubs Logísticos con coordenadas GPS inicializada en Neo4j.")

def buscar_camino_optimo(origen_input, destino_input):
    """Devuelve la secuencia de Hubs con sus coordenadas GPS (lat, lon) reales."""
    with neo4j_driver.session() as session:
        query = """
        MATCH (origen:HubLogistico), (destino:HubLogistico)
        WHERE (toLower(origen.nombre) CONTAINS toLower($origen) OR toLower(origen.codigo) = toLower($origen))
        AND (toLower(destino.nombre) CONTAINS toLower($destino) OR toLower(destino.codigo) = toLower($destino))
        MATCH p = shortestPath((origen)-[:TRAMO_RUTA*]->(destino))
        RETURN [n IN nodes(p) | {
            codigo: n.codigo, 
            nombre: n.nombre, 
            tipo: n.tipo, 
            lat: n.lat, 
            lon: n.lon
        }] AS puntos_gps,
        reduce(s = 0, r IN relationships(p) | s + r.distancia_km) AS distancia_total,
        reduce(t = 0, r IN relationships(p) | t + r.tiempo_hs) AS tiempo_total
        """
        result = session.run(query, origen=origen_input.strip(), destino=destino_input.strip())
        return [record.data() for record in result]

def registrar_relaciones_envio_grafo(id_envio, razon_cliente, nombre_operador, nombre_proveedor, origen, destino):
    """Sincroniza en Neo4j la red de actores que participan de un envío para trazabilidad en grafo."""
    with neo4j_driver.session() as session:
        query = """
        MERGE (c:Cliente {nombre: $cliente})
        MERGE (op:OperadorLogistico {nombre: $operador})
        MERGE (pr:Proveedor {nombre: $proveedor})
        MERGE (e:Envio {id_envio: $id_envio, origen: $origen, destino: $destino})
        MERGE (c)-[:CONTRATO_ENVIO]->(e)
        MERGE (op)-[:OPERO_CARGA_Y_ADUANA]->(e)
        MERGE (pr)-[:PROVEYO_INSUMOS]->(e)
        """
        session.run(query, id_envio=id_envio, cliente=razon_cliente, 
                    operador=nombre_operador, proveedor=nombre_proveedor,
                    origen=origen, destino=destino)

def obtener_red_relaciones_grafo():
    """Consulta avanzada: Red de relaciones entre clientes, operadores, proveedores y envíos."""
    with neo4j_driver.session() as session:
        query = """
        MATCH (c:Cliente)-[:CONTRATO_ENVIO]->(e:Envio)<-[:OPERO_CARGA_Y_ADUANA]-(op:OperadorLogistico)
        OPTIONAL MATCH (pr:Proveedor)-[:PROVEYO_INSUMOS]->(e)
        RETURN c.nombre AS cliente, e.id_envio AS id_envio, e.origen AS origen, 
            e.destino AS destino, op.nombre AS operador, COALESCE(pr.nombre, 'Flota Propia') AS proveedor
        ORDER BY e.id_envio ASC
        """
        result = session.run(query)
        return [record.data() for record in result]