from tkinter import Tk, Label
import webbrowser
import time
import threading
import socket

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

def open_browser():
    # Espera un momento para dar tiempo a la ventana de Tkinter de aparecer
    time.sleep(2)
    # Abre el navegador con la dirección IP local
    webbrowser.open(f"http://{get_local_ip()}:5000")
    # Cierra la ventana de carga después de abrir el navegador
    loading_window.destroy()

def show_loading_window():
    global loading_window
    # Crear una ventana de Tkinter
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

# Ejecuta la ventana de carga en un hilo separado
threading.Thread(target=show_loading_window).start()

# Ejecuta la función para abrir el navegador en el hilo principal
open_browser()
