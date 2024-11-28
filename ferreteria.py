from waitress import serve
from app import app  # Importa tu aplicación Flask
import logging
import socket
import time
import threading
import webbrowser
from tkinter import Tk, Label
from sincronizacion_periodica import sincronizar_periodica  # Asegúrate de que esto esté importado correctamente

def get_local_ip():
    """Obtiene la dirección IP local de la máquina."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def open_browser(ip_address):
    """Espera un momento y abre el navegador con la URL de la aplicación."""
    time.sleep(2)
    webbrowser.open(f"http://{ip_address}:5000")
    loading_window.destroy()

def show_loading_window():
    """Muestra una ventana de carga mientras se abre la aplicación."""
    global loading_window
    loading_window = Tk()
    loading_window.title("Cargando")
    loading_window.geometry("200x100")
    loading_window.eval('tk::PlaceWindow . center')
    loading_window.resizable(False, False)

    Label(loading_window, text="Abriendo aplicación...").pack(expand=True)

    loading_window.attributes('-topmost', True)
    loading_window.mainloop()

def sincronizacion_periodica_thread():
    """Ejecuta la sincronización periódica en un bucle cada 30 segundos."""
    while True:
        try:
            sincronizar_periodica()  # Ejecuta la sincronización de productos y clientes
            time.sleep(30)  # Espera 30 segundos antes del siguiente ciclo
        except Exception as e:
            logging.error(f"Error en la sincronización periódica: {e}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    ip_address = get_local_ip()
    print(f"Starting server on http://{ip_address}:5000")

    threading.Thread(target=sincronizacion_periodica_thread, daemon=True).start()  # Sincronización en segundo plano

    threading.Thread(target=show_loading_window, daemon=True).start()

    threading.Thread(target=open_browser, args=(ip_address,), daemon=True).start()

    serve(app, host='0.0.0.0', port=5000)
