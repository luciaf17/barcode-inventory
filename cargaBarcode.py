from waitress import serve
from app import app  # Asegúrate de que 'app' es el nombre de tu instancia de Flask
import logging
import socket

def get_local_ip():
    """Obtiene la dirección IP local de la máquina."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Intenta obtener la IP local mediante una conexión simulada
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"  # En caso de error, usa la IP de localhost
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    # Configura el logging para información de servidor
    logging.basicConfig(level=logging.INFO)
    
    ip_address = get_local_ip()
    print(f"Starting server on http://{ip_address}:5000")
    # Inicia el servidor Waitress en el puerto 5000
    serve(app, host='0.0.0.0', port=5000)
