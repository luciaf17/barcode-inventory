import sqlite3
import pandas as pd
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SincronizacionInicial")

# Configuración de la base de datos SQLite
DB_FILE = "ferreteria.db"
BATCH_SIZE = 200  # Cantidad de filas que se procesarán por batch

def crear_tabla_local():
    """Crea las tablas SQLite si no existen."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Crear tabla productos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            Codigo_interno TEXT PRIMARY KEY,
            Codigo TEXT,
            Desc_Concatenada TEXT,
            cantidad INTEGER,
            deposito TEXT,
            pasillo TEXT,
            columna TEXT,
            estante TEXT,
            precio_cpa REAL DEFAULT 0.0,
            precio_vta REAL DEFAULT 0.0
        )
    """)

    # Crear tabla interdeposito
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interdeposito (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            codigo_interno TEXT NOT NULL,
            codigo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            deposito_origen TEXT NOT NULL,
            deposito_destino TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'Remito Interno',
            numero_remito TEXT NOT NULL
        )
    """)

    # Crear tabla clientes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id_cliente INTEGER PRIMARY KEY,
            nombre_cliente TEXT
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Tablas locales creadas o ya existen.")


def insertar_productos_csv(csv_file_path):
    """Inserta los datos desde el CSV de productos a la base de datos SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Cargar los datos desde el CSV
    productos_df = pd.read_csv(csv_file_path)

    for _, row in productos_df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO productos (Codigo_interno, Codigo, Desc_Concatenada, cantidad, deposito, pasillo, columna, estante, precio_cpa, precio_vta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(Codigo_interno) DO NOTHING
            """, (
                row["Codigo_interno"],
                row["Codigo"],
                row["Desc Concatenada"],
                row["cantidad"],
                row["deposito"],
                row["pasillo"],
                row["columna"],
                row["estante"],
                row["precio_cpa"],
                row["precio_vta"]
            ))
        except Exception as e:
            logger.error(f"Error al insertar producto {row['Codigo_interno']}: {e}")

    conn.commit()
    conn.close()
    logger.info("Sincronización de productos desde CSV completada.")


def insertar_clientes_csv(csv_file_path):
    """Inserta los datos desde el CSV de clientes a la base de datos SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Cargar los datos desde el CSV
    clientes_df = pd.read_csv(csv_file_path)

    for _, row in clientes_df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO clientes (id_cliente, nombre_cliente)
                VALUES (?, ?)
                ON CONFLICT(id_cliente) DO UPDATE SET
                nombre_cliente = excluded.nombre_cliente
            """, (
                row["ID_Cliente"],
                row["Nombre Cliente"]
            ))
        except Exception as e:
            logger.error(f"Error al insertar cliente {row['ID_Cliente']}: {e}")

    conn.commit()
    conn.close()
    logger.info("Sincronización de clientes desde CSV completada.")


def sincronizar_inicial(productos_csv_path, clientes_csv_path):
    """Sincroniza los productos desde CSV y clientes desde CSV."""
    logger.info("Iniciando sincronización inicial...")
    
    # Primero sincronizamos los productos desde el archivo CSV
    crear_tabla_local()  # Asegurarse de que las tablas se creen antes de insertar los datos
    insertar_productos_csv(productos_csv_path)
    
    # Luego sincronizamos los clientes desde el archivo CSV
    insertar_clientes_csv(clientes_csv_path)
    
    logger.info("Sincronización inicial completada.")


if __name__ == "__main__":
    try:
        # Especifica la ubicación de los archivos CSV de productos y clientes
        productos_csv_path = 'Productos.csv'  # Ruta del archivo CSV de productos
        clientes_csv_path = 'Clientes.csv'    # Ruta del archivo CSV de clientes
        sincronizar_inicial(productos_csv_path, clientes_csv_path)
    except Exception as e:
        logger.error(f"Error crítico durante la sincronización inicial: {e}")
