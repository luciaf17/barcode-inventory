from waitress import serve
from app import app  # Asegúrate de que 'app' es el nombre de tu instancia de Flask
import logging
import socket
import time
import threading
import webbrowser
from tkinter import Tk, Label

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

def open_browser(ip_address):
    """Espera un momento y abre el navegador con la URL de la aplicación."""
    time.sleep(2)
    webbrowser.open(f"http://{ip_address}:5000")
    # Cierra la ventana de carga después de abrir el navegador
    loading_window.destroy()

def show_loading_window():
    """Muestra una ventana de carga mientras se abre la aplicación."""
    global loading_window
    loading_window = Tk()
    loading_window.title("Cargando")
    loading_window.geometry("200x100")
    loading_window.eval('tk::PlaceWindow . center')
    loading_window.resizable(False, False)

    # Etiqueta con el mensaje
    Label(loading_window, text="Abriendo aplicación...").pack(expand=True)

    # Hacer que la ventana aparezca en primer plano
    loading_window.attributes('-topmost', True)
    # Iniciar el ciclo de eventos de la ventana
    loading_window.mainloop()

if __name__ == '__main__':
    # Configura el logging para información de servidor
    logging.basicConfig(level=logging.INFO)
    
    ip_address = get_local_ip()
    print(f"Starting server on http://{ip_address}:5000")

    # Ejecuta la ventana de carga en un hilo separado
    threading.Thread(target=show_loading_window).start()

    # Ejecuta la función para abrir el navegador en el hilo principal
    threading.Thread(target=open_browser, args=(ip_address,)).start()

    # Inicia el servidor Waitress en el puerto 5000
    serve(app, host='0.0.0.0', port=5000)
