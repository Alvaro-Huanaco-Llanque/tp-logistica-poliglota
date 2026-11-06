from config.database import neo4j_driver

def buscar_camino_optimo(origen_input, destino_input):
    """Busca la ruta más corta en Neo4j adaptándose a los nodos :Provincia y relaciones :CONECTA_CON."""
    with neo4j_driver.session() as session:
        query = """
        MATCH (origen)
        WHERE (origen:Provincia OR origen:Ubicacion OR origen:Pais)
        AND (
            toLower(COALESCE(origen.nombre, '')) = toLower($origen) OR
            toLower(COALESCE(origen.name, '')) = toLower($origen) OR
            toLower(COALESCE(origen.codigo, '')) = toLower($origen)
        )
        MATCH (destino)
        WHERE (destino:Provincia OR destino:Ubicacion OR destino:Pais)
        AND (
            toLower(COALESCE(destino.nombre, '')) = toLower($destino) OR
            toLower(COALESCE(destino.name, '')) = toLower($destino) OR
            toLower(COALESCE(destino.codigo, '')) = toLower($destino)
        )
        MATCH p = shortestPath((origen)-[:CONECTA_CON|TRAMO_TERRESTRE|TRAMO_MARITIMO*]-(destino))
        RETURN [n IN nodes(p) | COALESCE(n.nombre, n.name, n.codigo)] AS ruta,
            reduce(s = 0, r IN relationships(p) | s + COALESCE(r.distancia_km, 0)) AS distancia_total,
            reduce(t = 0, r IN relationships(p) | t + COALESCE(r.tiempo_estimado_hs, 0)) AS tiempo_total
        """
        result = session.run(query, origen=origen_input.strip(), destino=destino_input.strip())
        return [record.data() for record in result]