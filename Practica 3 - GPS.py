import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import serial
import threading
import math
import os

from parseo_tramas import parsear_gga
from conversion_utm import geograficas_a_utm

class MapaINSIA:
    def __init__(self, ruta_archivo):
        self.puntos = []
        self.cargar_mapa(ruta_archivo)

    def cargar_mapa(self, ruta_archivo):
        if not os.path.exists(ruta_archivo):
            print(f"[AVISO] No se encontró el archivo '{ruta_archivo}'.")
            return
            
        try:
            with open(ruta_archivo, 'r') as f:
                for linea in f:
                    if linea.strip():
                        partes = linea.replace(',', ' ').split()
                        if len(partes) >= 3:
                            norte = float(partes[0])
                            este = float(partes[1])
                            v_max = float(partes[2])
                            self.puntos.append({'N': norte, 'E': este, 'Vmax': v_max})
            
            # NUEVO: Calcular el sentido (grados) de cada tramo de la pista
            for i in range(len(self.puntos) - 1):
                p_actual = self.puntos[i]
                p_sig = self.puntos[i+1]
                delta_n = p_sig['N'] - p_actual['N']
                delta_e = p_sig['E'] - p_actual['E']
                sentido_rad = math.atan2(delta_e, delta_n)
                p_actual['Sentido'] = (math.degrees(sentido_rad) + 360) % 360
                
            # Al último punto le ponemos el mismo sentido que al anterior para que no falle
            if len(self.puntos) > 1:
                self.puntos[-1]['Sentido'] = self.puntos[-2]['Sentido']
                
            print(f"[INFO] Mapa INSIA cargado con {len(self.puntos)} puntos y sentidos calculados.")
        except Exception as e:
            print(f"[ERROR] No se pudo cargar el mapa: {e}")

    # NUEVO: Ahora recibe el sentido del coche también
    def obtener_limite_velocidad(self, utm_n, utm_e, sentido_coche):
        if not self.puntos:
            return 0

        distancia_minima = float('inf')
        limite_actual = 0

        for p in self.puntos:
            dist = math.sqrt((utm_n - p['N'])**2 + (utm_e - p['E'])**2)
            
            # Calcular la diferencia de ángulo entre el coche y la pista
            if 'Sentido' in p:
                diff_angulo = abs((sentido_coche - p['Sentido']) % 360)
                if diff_angulo > 180:
                    diff_angulo = 360 - diff_angulo
                
                # SOLO aceptamos el punto si vamos en la misma dirección (margen de +/- 90 grados)
                es_mismo_sentido = diff_angulo <= 90
            else:
                es_mismo_sentido = True # Por si hay algún fallo

            if es_mismo_sentido and dist < distancia_minima:
                distancia_minima = dist
                limite_actual = p['Vmax']

        # Si el punto válido más cercano está a menos de 15 metros, devolvemos su límite
        if distancia_minima < 15:
            return limite_actual
        return 0

    def evaluar_aviso(self, velocidad_actual, velocidad_maxima):
        if velocidad_maxima == 0:
            return "gray"
        margen = velocidad_maxima * 0.10
        if velocidad_actual < (velocidad_maxima - margen):
            return "green"
        elif velocidad_actual > (velocidad_maxima + margen):
            return "red"
        else:
            return "yellow"

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
        self.root.title("Navegador GPS - Práctica 2 y 3")
        
        self.leyendo = False
        self.historial_puntos = [] 
        self.ultimo_utm = None     
        
        self.mapa_electronico = MapaINSIA("mapa_insia.txt") 
        
        self.frame_aviso = tk.Frame(root, bg="gray", height=100)
        self.frame_aviso.pack(fill=tk.X, side=tk.TOP)
        self.frame_aviso.pack_propagate(False) 
        
        self.lbl_velocidad = tk.Label(self.frame_aviso, text="0.0 Km/h", font=("Arial", 36, "bold"), bg="gray", fg="black")
        self.lbl_velocidad.pack(expand=True, fill=tk.BOTH)
        
        self.lbl_limite = tk.Label(self.frame_aviso, text="Límite: -- Km/h | Sentido: --º", font=("Arial", 12), bg="lightgray")
        self.lbl_limite.pack(fill=tk.X, side=tk.BOTTOM)

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

        self.senales_tk = {
            5:  ImageTk.PhotoImage(Image.open("senal_5.png").resize((90, 90))),
            10: ImageTk.PhotoImage(Image.open("senal_10.png").resize((90, 90))),
            15: ImageTk.PhotoImage(Image.open("senal_15.png").resize((90, 90))),
            18: ImageTk.PhotoImage(Image.open("senal_18.png").resize((90, 90))),
            20: ImageTk.PhotoImage(Image.open("senal_20.png").resize((90, 90))),
        }
        self.senal_canvas_id = self.canvas.create_image(10, 10, anchor=tk.NW, image=None, tags="senal")
        self.senal_actual_limite = None
        
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
            self.ultimo_utm = None
            self.canvas.coords(self.coche, -20, -20, -20, -20) 

            self.canvas.itemconfig(self.senal_canvas_id, image=None)
            self.senal_actual_limite = None
            
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

    def calcular_velocidad_y_sentido(self, n_actual, e_actual):
        if not self.ultimo_utm:
            return 0.0, 0.0
        
        n_prev, e_prev = self.ultimo_utm
        
        distancia_m = math.sqrt((n_actual - n_prev)**2 + (e_actual - e_prev)**2)
        
        velocidad_kmh = (distancia_m / 1.0) * 3.6
        
        delta_n = n_actual - n_prev
        delta_e = e_actual - e_prev
        sentido_rad = math.atan2(delta_e, delta_n)
        sentido_grados = (math.degrees(sentido_rad) + 360) % 360
        
        return velocidad_kmh, sentido_grados

    def actualizar_interfaz(self, easting, northing, num_sats):
        velocidad_actual, sentido = self.calcular_velocidad_y_sentido(northing, easting)
        self.ultimo_utm = (northing, easting)
        
        if self.mapa_seleccionado.get() == "INSIA":
            # NUEVO: Aquí le pasamos el "sentido" para que sepa en qué dirección vamos
            limite = self.mapa_electronico.obtener_limite_velocidad(northing, easting, sentido)
            color_fondo = self.mapa_electronico.evaluar_aviso(velocidad_actual, limite)
            
            self.frame_aviso.config(bg=color_fondo)
            self.lbl_velocidad.config(text=f"{velocidad_actual:.1f} Km/h", bg=color_fondo)
            self.lbl_limite.config(text=f"Límite: {limite} Km/h | Sentido: {sentido:.1f}º", bg=color_fondo)

            limite_int = int(round(limite))
            if limite_int in self.senales_tk and limite_int != self.senal_actual_limite:
                self.canvas.itemconfig(self.senal_canvas_id, image=self.senales_tk[limite_int])
                self.senal_actual_limite = limite_int
        else:
            self.frame_aviso.config(bg="gray")
            self.lbl_velocidad.config(text=f"{velocidad_actual:.1f} Km/h", bg="gray")
            self.lbl_limite.config(text="Fuera del INSIA (Sin límites)", bg="lightgray")

            self.canvas.itemconfig(self.senal_canvas_id, image=None)
            self.senal_actual_limite = None

        x, y = self.utm_a_pixeles(easting, northing)
        
        if self.historial_puntos:
            ult_x, ult_y = self.historial_puntos[-1]
            self.canvas.create_line(ult_x, ult_y, x, y, fill="blue", width=3, tags="ruta")
            
        self.historial_puntos.append((x, y))
        
        self.canvas.coords(self.coche, 
                           x - self.radio_coche, y - self.radio_coche, 
                           x + self.radio_coche, y + self.radio_coche)
        self.canvas.tag_raise(self.coche)
        
        self.canvas.tag_raise("senal")
        
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
            self.root.after(0, lambda: messagebox.showerror("Error", f"Problema con el puerto:\n{e}"))
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