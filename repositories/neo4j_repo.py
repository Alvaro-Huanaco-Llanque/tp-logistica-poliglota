from config.database import neo4j_driver

def buscar_camino_optimo(origen_codigo, destino_codigo):
    """Busca la ruta más corta entre dos ubicaciones utilizando el grafo logístico de Neo4j."""
    with neo4j_driver.session() as session:
        query = """
        MATCH (origen:Ubicacion {codigo: $origen}), (destino:Ubicacion {codigo: $destino})
        MATCH p = shortestPath((origen)-[:TRAMO_MARITIMO|TRAMO_TERRESTRE*]-(destino))
        RETURN [n IN nodes(p) | n.codigo] AS ruta,
               reduce(s = 0, r IN relationships(p) | s + r.distancia_km) AS distancia_total,
               reduce(t = 0, r IN relationships(p) | t + r.tiempo_estimado_hs) AS tiempo_total
        """
        result = session.run(query, origen=origen_codigo, destino=destino_codigo)
        return [record.data() for record in result]