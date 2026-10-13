import os
from dotenv import load_dotenv
import psycopg2
from pymongo import MongoClient
from neo4j import GraphDatabase
import redis

# Carga las variables del archivo .env
load_dotenv()

# 1. Conexión a PostgreSQL (Relacional - Transaccional y Facturación)
def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        port=os.getenv("PG_PORT")
    )

# 2. Conexión a MongoDB (NoSQL Documental - Telemetría IoT / Eventos)
mongo_client = MongoClient(os.getenv("MONGO_URI"))
mongo_db = mongo_client[os.getenv("MONGO_DB")]

# 3. Conexión a Neo4j (Grafos - Red Logística y Rutas)
neo4j_driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

# 4. Conexión a Redis (Clave-Valor / Caché en tiempo real)
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    decode_responses=True
)