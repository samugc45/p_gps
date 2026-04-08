import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import serial
import threading

from parseo_tramas import parsear_gga
from conversion_utm import geograficas_a_utm

# --- CONFIGURACIÓN DE LOS MAPAS ---
MAPAS = {
    "Campus Sur": {
        "archivo": "etsisi.PNG",
        "E_MIN": 446193.00, "N_MAX": 4471374.00,
        "E_MAX": 447008.00, "N_MIN": 4470787.00
    },
    "INSIA": {
        "archivo": "insia.PNG", 
        "E_MIN": 446237.00, "N_MAX": 4470980.00,
        "E_MAX": 446444.00, "N_MIN": 4470777.00
    }
}

class NavegadorGPS:
    def __init__(self, root):
        self.root = root
        self.root.title("Navegador GPS - Práctica 2")
        
        self.leyendo = False
        self.historial_puntos = [] # lista vacia donde se guardarán las coordenadas en píxeles para trazar la ruta
        
        frame_controles = tk.Frame(root, padx=10, pady=5)
        frame_controles.pack(fill=tk.X)
        
        tk.Label(frame_controles, text="Puerto Serie:").pack(side=tk.LEFT)
        self.entry_puerto = tk.Entry(frame_controles, width=15)
        self.entry_puerto.insert(0, "COM1") 
        self.entry_puerto.pack(side=tk.LEFT, padx=5)
        
        self.btn_conectar = tk.Button(frame_controles, text="Conectar", command=self.iniciar_conexion, bg="lightblue")
        self.btn_conectar.pack(side=tk.LEFT, padx=5)
        
        tk.Label(frame_controles, text="Mapa:").pack(side=tk.LEFT, padx=(20, 0))
        self.mapa_seleccionado = tk.StringVar(value="Campus Sur")
        combo_mapas = ttk.Combobox(frame_controles, textvariable=self.mapa_seleccionado, values=list(MAPAS.keys()), state="readonly", width=15)
        combo_mapas.pack(side=tk.LEFT, padx=5)
        combo_mapas.bind("<<ComboboxSelected>>", self.cambiar_mapa)
        
        self.canvas = tk.Canvas(root, bg="gray")
        self.canvas.pack()
        
        self.imagen_tk = None
        self.mapa_actual = None
        
        self.radio_coche = 6
        self.coche = self.canvas.create_oval(-20, -20, -20, -20, fill="red", outline="black", width=2)
        
        self.label_info = tk.Label(root, text="Esperando conexión...", bg="white", font=("Arial", 10), pady=5)
        self.label_info.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.cambiar_mapa()

    def cambiar_mapa(self, event=None):
        nombre_mapa = self.mapa_seleccionado.get()
        self.mapa_actual = MAPAS[nombre_mapa]
        
        try:
            imagen_pil = Image.open(self.mapa_actual["archivo"])
            self.ancho_img, self.alto_img = imagen_pil.size
            self.imagen_tk = ImageTk.PhotoImage(imagen_pil)
            
            self.canvas.config(width=self.ancho_img, height=self.alto_img)
            self.canvas.delete("fondo") 
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.imagen_tk, tags="fondo")
            
            self.canvas.tag_lower("fondo")
            
            self.canvas.delete("ruta")
            self.historial_puntos.clear()
            self.canvas.coords(self.coche, -20, -20, -20, -20) 
            
            self.label_info.config(text=f"Mapa cambiado a {nombre_mapa}. Esperando GPS...")
            
        except FileNotFoundError:
            messagebox.showerror("Error", f"No se encuentra la imagen '{self.mapa_actual['archivo']}'.")

    def utm_a_pixeles(self, easting, northing):
        E_MIN = self.mapa_actual["E_MIN"]
        E_MAX = self.mapa_actual["E_MAX"]
        N_MIN = self.mapa_actual["N_MIN"]
        N_MAX = self.mapa_actual["N_MAX"]
        
        x = ((easting - E_MIN) / (E_MAX - E_MIN)) * self.ancho_img
        y = ((N_MAX - northing) / (N_MAX - N_MIN)) * self.alto_img
        
        return int(x), int(y)

    def actualizar_interfaz(self, easting, northing, num_sats):
        x, y = self.utm_a_pixeles(easting, northing)
        
        if self.historial_puntos:
            ult_x, ult_y = self.historial_puntos[-1]
            self.canvas.create_line(ult_x, ult_y, x, y, fill="blue", width=3, tags="ruta")
            
        self.historial_puntos.append((x, y))
        
        self.canvas.coords(self.coche, 
                           x - self.radio_coche, y - self.radio_coche, 
                           x + self.radio_coche, y + self.radio_coche)
        self.canvas.tag_raise(self.coche)
        
        
        texto = f"Easting: {easting:.2f} | Northing: {northing:.2f} | Satélites: {num_sats}"
        self.label_info.config(text=texto)

    def iniciar_conexion(self):
        if self.leyendo:
            return 
            
        puerto = self.entry_puerto.get().strip()
        if not puerto:
            messagebox.showwarning("Aviso", "Por favor, introduce un puerto serie.")
            return
            
        self.leyendo = True
        self.btn_conectar.config(text="Conectado", state=tk.DISABLED)
        self.label_info.config(text=f"Conectando a {puerto}...")
        
        self.hilo_gps = threading.Thread(target=self.leer_gps_continuamente, args=(puerto,), daemon=True)
        self.hilo_gps.start()

    def leer_gps_continuamente(self, puerto):
        try:
            ser = serial.Serial(port=puerto, baudrate=4800, timeout=1)
            self.root.after(0, lambda: self.label_info.config(text="GPS Conectado. Esperando datos..."))
            
            while self.leyendo:
                linea = ser.readline().decode("ascii", errors="replace").strip()
                if "$GPGGA" in linea or "$GNGGA" in linea:
                    datos = parsear_gga(linea)
                    
                    if datos and datos.get("calidad_fix", 0) > 0:
                        utm = geograficas_a_utm(datos["latitud_decimal"], datos["longitud_decimal"])
                        self.root.after(0, self.actualizar_interfaz, utm['easting'], utm['northing'], datos['num_satelites'])
                        
        except serial.SerialException as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Problema con el puerto serie:\n{e}"))
            self.root.after(0, self.desconectar)
        except Exception as e:
            print(f"[ERROR] Inesperado: {e}")

    def desconectar(self):
        self.leyendo = False
        self.btn_conectar.config(text="Conectar", state=tk.NORMAL)
        self.label_info.config(text="Desconectado.")

    def cerrar(self):
        self.leyendo = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NavegadorGPS(root)
    root.protocol("WM_DELETE_WINDOW", app.cerrar)
    root.mainloop()