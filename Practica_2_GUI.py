import tkinter as tk
from PIL import Image, ImageTk
import serial
import threading

# Importamos tus módulos de la Práctica 1
from parseo_tramas import parsear_gga
from conversion_utm import geograficas_a_utm

# --- CONFIGURACIÓN DEL MAPA ---
# Nombre de tu imagen (cambia a .png si tu archivo local es png)
ARCHIVO_MAPA = "etsisi.PNG" 

# Coordenadas UTM de la esquina Superior Izquierda
E_MIN = 446143.42  
N_MAX = 4471498.96 

# Coordenadas UTM de la esquina Inferior Derecha
E_MAX = 447034.58  
N_MIN = 4470740.59 

class NavegadorGPS:
    def __init__(self, root, puerto_serie):
        self.root = root
        self.root.title("Navegador GPS - Práctica 2 (Campus Sur)")
        
        # Cargar y mostrar la imagen del mapa
        try:
            self.imagen_pil = Image.open(ARCHIVO_MAPA)
        except FileNotFoundError:
            print(f"[ERROR] No se encuentra la imagen '{ARCHIVO_MAPA}'. Asegúrate de que está en la misma carpeta.")
            self.root.destroy()
            return
            
        self.ancho_img, self.alto_img = self.imagen_pil.size
        self.imagen_tk = ImageTk.PhotoImage(self.imagen_pil)
        
        self.canvas = tk.Canvas(root, width=self.ancho_img, height=self.alto_img)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.imagen_tk)
        
        # Crear el "coche" (un círculo rojo) que moveremos por el mapa
        self.radio_coche = 6
        # Lo iniciamos fuera de la pantalla hasta que tengamos GPS
        self.coche = self.canvas.create_oval(-20, -20, -20, -20, fill="red", outline="black", width=2)
        
        # Etiqueta para mostrar los datos de depuración en la ventana
        self.label_info = tk.Label(root, text="Esperando señal GPS...", bg="white", font=("Arial", 10))
        self.label_info.pack(fill=tk.X)
        
        # Iniciar la lectura del GPS en un hilo separado
        self.puerto_serie = puerto_serie
        self.leyendo = True
        self.hilo_gps = threading.Thread(target=self.leer_gps_continuamente, daemon=True)
        self.hilo_gps.start()

    def utm_a_pixeles(self, easting, northing):
        """Convierte coordenadas UTM a píxeles X, Y en el Canvas."""
        # Regla de tres para la X
        x = ((easting - E_MIN) / (E_MAX - E_MIN)) * self.ancho_img
        
        # Regla de tres para la Y (invertida porque en pantallas la Y crece hacia abajo)
        y = ((N_MAX - northing) / (N_MAX - N_MIN)) * self.alto_img
        
        return int(x), int(y)

    def actualizar_interfaz(self, easting, northing, num_sats):
        """Mueve el punto rojo a las nuevas coordenadas UTM calculadas y actualiza el texto."""
        x, y = self.utm_a_pixeles(easting, northing)
        
        # Mover el círculo en el mapa
        self.canvas.coords(self.coche, 
                           x - self.radio_coche, y - self.radio_coche, 
                           x + self.radio_coche, y + self.radio_coche)
        
        # Actualizar el texto inferior
        texto = f"Easting: {easting:.2f} | Northing: {northing:.2f} | Satélites: {num_sats}"
        self.label_info.config(text=texto)

    def leer_gps_continuamente(self):
        """Lee el puerto serie constantemente en segundo plano."""
        try:
            ser = serial.Serial(
                port=self.puerto_serie,
                baudrate=4800,
                timeout=1
            )
            print(f"[OK] Conectado al GPS en {self.puerto_serie}")
            
            while self.leyendo:
                linea = ser.readline().decode("ascii", errors="replace").strip()
                if "$GPGGA" in linea or "$GNGGA" in linea:
                    datos = parsear_gga(linea)
                    
                    if datos and datos.get("calidad_fix", 0) > 0:
                        utm = geograficas_a_utm(datos["latitud_decimal"], datos["longitud_decimal"])
                        
                        # tk.Canvas no es thread-safe, usamos after() para actualizar la GUI de forma segura
                        self.root.after(0, self.actualizar_interfaz, utm['easting'], utm['northing'], datos['num_satelites'])
                        
        except serial.SerialException as e:
            print(f"[ERROR] Problema con el puerto serie: {e}")
            self.root.after(0, lambda: self.label_info.config(text=f"Error de puerto: {self.puerto_serie}"))
        except Exception as e:
            print(f"[ERROR] Inesperado: {e}")

    def cerrar(self):
        self.leyendo = False
        self.root.destroy()

if __name__ == "__main__":
    print("--- PRÁCTICA 2: NAVEGADOR GPS ---")
    puerto = input("Introduce el puerto serie (ej: COM8, /dev/ttyUSB0): ").strip()
    
    # Recuérdale al usuario borrar la llave extra en conversion_utm.py si no lo ha hecho
    print("Iniciando interfaz gráfica...")
    
    root = tk.Tk()
    app = NavegadorGPS(root, puerto)
    root.protocol("WM_DELETE_WINDOW", app.cerrar)
    root.mainloop()