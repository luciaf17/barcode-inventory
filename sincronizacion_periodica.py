import logging
from sincronizacion_inicial import sincronizar_inicial  # Importa las funciones de sincronización inicial
from sincronizacion_clientes import sincronizar_clientes  # Importa la función para sincronizar clientes
from sincronizacion_productos import sincronizar_productos  # Importa la función para sincronizar productos

def sincronizar_periodica():
    """Función que sincroniza productos y clientes periódicamente cada 30 segundos."""
    try:
        logging.info("Iniciando sincronización periódica...")
        
        # Llama a las funciones de sincronización
        sincronizar_productos()  # Sincroniza los productos
        sincronizar_clientes()  # Sincroniza los clientes
        
        logging.info("Sincronización periódica completada.")
    except Exception as e:
        logging.error(f"Error en la sincronización periódica: {e}")
