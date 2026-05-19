import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import serial
import threading
import math
import os
import requests
from io import BytesIO

from parseo_tramas import parsear_gga
from conversion_utm import geograficas_a_utm

# ==========================================
# CLASE MAPA INSIA (PRÁCTICA 3)
# ==========================================
class MapaINSIA:
    def __init__(self, ruta_archivo):
        self.puntos = []
        self.cargar_mapa(ruta_archivo)

    def cargar_mapa(self, ruta_archivo):
        if not os.path.exists(ruta_archivo): return
        try:
            with open(ruta_archivo, 'r') as f:
                for linea in f:
                    if linea.strip():
                        partes = linea.replace(',', ' ').split()
                        if len(partes) >= 3:
                            self.puntos.append({'N': float(partes[0]), 'E': float(partes[1]), 'Vmax': float(partes[2])})
            
            for i in range(len(self.puntos) - 1):
                p_actual = self.puntos[i]
                p_sig = self.puntos[i+1]
                sentido_rad = math.atan2(p_sig['E'] - p_actual['E'], p_sig['N'] - p_actual['N'])
                p_actual['Sentido'] = (math.degrees(sentido_rad) + 360) % 360
                
            if len(self.puntos) > 1:
                self.puntos[-1]['Sentido'] = self.puntos[-2]['Sentido']
        except: pass

    def obtener_limite_velocidad(self, utm_n, utm_e, sentido_coche):
        if not self.puntos: return 0
        distancia_minima = float('inf')
        limite_actual = 0
        for p in self.puntos:
            dist = math.sqrt((utm_n - p['N'])**2 + (utm_e - p['E'])**2)
            if 'Sentido' in p:
                diff_angulo = abs((sentido_coche - p['Sentido']) % 360)
                if diff_angulo > 180: diff_angulo = 360 - diff_angulo
                es_mismo_sentido = diff_angulo <= 90
            else: es_mismo_sentido = True

            if es_mismo_sentido and dist < distancia_minima:
                distancia_minima = dist
                limite_actual = p['Vmax']
        return limite_actual if distancia_minima < 15 else 0

    def evaluar_aviso(self, velocidad_actual, velocidad_maxima):
        if velocidad_maxima == 0: return "gray"
        margen = velocidad_maxima * 0.10
        if velocidad_actual < (velocidad_maxima - margen): return "green"
        elif velocidad_actual > (velocidad_maxima + margen): return "red"
        else: return "yellow"

MAPAS_ESTATICOS = {
    "Campus Sur": {"archivo": "etsisi.PNG", "E_MIN": 446193.0, "N_MAX": 4471374.0, "E_MAX": 447008.0, "N_MIN": 4470787.0},
    "INSIA": {"archivo": "insia.PNG", "E_MIN": 446237.0, "N_MAX": 4470980.0, "E_MAX": 446444.0, "N_MIN": 4470777.0}
}

# ==========================================
# GUI: NAVEGADOR GPS UNIFICADO
# ==========================================
class NavegadorGPS:
    def __init__(self, root):
        self.root = root
        self.root.title("Navegador GPS Avanzado - MapQuest (Satélite)")
        
        # --- AQUÍ PONES TU CLAVE DE MAPQUEST ---
        self.API_KEY = "sLxMqoKMmWHIEVqLfAL84uoma0iijdBA"
        
        self.leyendo = False
        self.historial_puntos_pixeles = [] 
        self.ultimo_utm = None     
        self.mapa_electronico = MapaINSIA("mapa_insia.txt") 
        self.descargando_mapa = False
        
        # --- VARIABLES MEJORA PERSONAL (Ordenador a bordo) ---
        self.distancia_total = 0.0
        self.lecturas_velocidad = []
        
        # UI: Avisos Superiores
        self.frame_aviso = tk.Frame(root, bg="gray", height=120)
        self.frame_aviso.pack(fill=tk.X, side=tk.TOP)
        self.frame_aviso.pack_propagate(False) 
        
        self.lbl_velocidad = tk.Label(self.frame_aviso, text="0.0 Km/h", font=("Arial", 32, "bold"), bg="gray", fg="black")
        self.lbl_velocidad.pack(expand=True, fill=tk.BOTH)
        
        # Etiqueta de la Mejora Personal
        self.lbl_trip = tk.Label(self.frame_aviso, text="Recorrido: 0.0 m | V. Media: 0.0 Km/h", font=("Arial", 11, "bold"), bg="black", fg="white")
        self.lbl_trip.pack(fill=tk.X)

        self.lbl_limite = tk.Label(self.frame_aviso, text="Límite: -- Km/h | Sentido: --º", font=("Arial", 11), bg="lightgray")
        self.lbl_limite.pack(fill=tk.X, side=tk.BOTTOM)

        # UI: Controles
        frame_controles = tk.Frame(root, padx=10, pady=5)
        frame_controles.pack(fill=tk.X)
        
        tk.Label(frame_controles, text="Puerto:").pack(side=tk.LEFT)
        self.entry_puerto = tk.Entry(frame_controles, width=8)
        self.entry_puerto.insert(0, "COM1") 
        self.entry_puerto.pack(side=tk.LEFT, padx=2)
        
        self.btn_conectar = tk.Button(frame_controles, text="Conectar", command=self.iniciar_conexion, bg="lightblue")
        self.btn_conectar.pack(side=tk.LEFT, padx=5)
        
        tk.Label(frame_controles, text="Mapa:").pack(side=tk.LEFT, padx=(5, 0))
        self.mapa_seleccionado = tk.StringVar(value="Campus Sur")
        opciones_mapa = list(MAPAS_ESTATICOS.keys()) + ["Internet (MapQuest Satélite)"]
        combo_mapas = ttk.Combobox(frame_controles, textvariable=self.mapa_seleccionado, values=opciones_mapa, state="readonly", width=24)
        combo_mapas.pack(side=tk.LEFT, padx=5)
        combo_mapas.bind("<<ComboboxSelected>>", self.cambiar_mapa)

        # UI: Canvas
        self.ancho_canvas, self.alto_canvas = 600, 600
        self.canvas = tk.Canvas(root, bg="black", width=self.ancho_canvas, height=self.alto_canvas)
        self.canvas.pack()
        
        self.imagen_tk = None
        self.mapa_actual = None
        
        self.coche = self.canvas.create_polygon(0,0, 0,0, 0,0, fill="red", outline="white", width=2, tags="coche")

        # Señales
        self.senales_tk = {}
        for s in [5, 10, 15, 18, 20]:
            try: self.senales_tk[s] = ImageTk.PhotoImage(Image.open(f"senal_{s}.png").resize((90, 90)))
            except: pass
        self.senal_canvas_id = self.canvas.create_image(10, 10, anchor=tk.NW, image=None, tags="senal")
        
        self.label_info = tk.Label(root, text="Esperando conexión...", bg="white", font=("Arial", 10), pady=5)
        self.label_info.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.cambiar_mapa()

    def dibujar_coche_flecha(self, x, y, sentido_grados):
        r_largo = 14; r_corto = 8   
        rad = math.radians(sentido_grados)
        x1 = x + math.sin(rad) * r_largo
        y1 = y - math.cos(rad) * r_largo
        x2 = x + math.sin(math.radians(sentido_grados - 140)) * r_corto
        y2 = y - math.cos(math.radians(sentido_grados - 140)) * r_corto
        x3 = x + math.sin(math.radians(sentido_grados + 140)) * r_corto
        y3 = y - math.cos(math.radians(sentido_grados + 140)) * r_corto
        self.canvas.coords(self.coche, x1, y1, x2, y2, x3, y3)

    def cambiar_mapa(self, event=None):
        nombre_mapa = self.mapa_seleccionado.get()
        self.canvas.delete("ruta")
        self.historial_puntos_pixeles.clear()
        
        if nombre_mapa in MAPAS_ESTATICOS:
            self.mapa_actual = MAPAS_ESTATICOS[nombre_mapa]
            try:
                imagen_pil = Image.open(self.mapa_actual["archivo"])
                self.ancho_canvas, self.alto_canvas = imagen_pil.size
                self.imagen_tk = ImageTk.PhotoImage(imagen_pil)
                self.canvas.config(width=self.ancho_canvas, height=self.alto_canvas)
                self.canvas.delete("fondo") 
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.imagen_tk, tags="fondo")
                self.canvas.tag_lower("fondo")
            except: pass
        else:
            self.mapa_actual = None
            self.ancho_canvas, self.alto_canvas = 600, 600
            self.canvas.config(width=self.ancho_canvas, height=self.alto_canvas)
            self.canvas.delete("fondo")

        self.canvas.tag_raise("coche")
        self.canvas.tag_raise("senal")
        self.canvas.itemconfig(self.senal_canvas_id, image=None)

    def utm_a_pixeles(self, easting, northing):
        if not self.mapa_actual: return self.ancho_canvas // 2, self.alto_canvas // 2
        E_MIN, E_MAX = self.mapa_actual["E_MIN"], self.mapa_actual["E_MAX"]
        N_MIN, N_MAX = self.mapa_actual["N_MIN"], self.mapa_actual["N_MAX"]
        x = ((easting - E_MIN) / (E_MAX - E_MIN)) * self.ancho_canvas
        y = ((N_MAX - northing) / (N_MAX - N_MIN)) * self.alto_canvas
        return int(x), int(y)

    def calcular_velocidad_y_sentido(self, n_actual, e_actual):
        if not self.ultimo_utm: return 0.0, 0.0, 0.0
        n_prev, e_prev = self.ultimo_utm
        distancia_m = math.sqrt((n_actual - n_prev)**2 + (e_actual - e_prev)**2)
        velocidad_kmh = distancia_m * 3.6
        sentido_rad = math.atan2(e_actual - e_prev, n_actual - n_prev)
        sentido_grados = (math.degrees(sentido_rad) + 360) % 360
        return velocidad_kmh, sentido_grados, distancia_m

    def peticion_mapquest(self, lat, lon, api_key):
        url = (f"https://www.mapquestapi.com/staticmap/v5/map?"
               f"key={api_key}&center={lat},{lon}&zoom=18&"
               f"size={self.ancho_canvas},{self.alto_canvas}&type=hyb")
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200: return Image.open(BytesIO(res.content))
        except: pass
        return None

    def actualizar_imagen_mapa(self, img_mapa):
        if img_mapa:
            self.imagen_tk = ImageTk.PhotoImage(img_mapa)
            self.canvas.delete("fondo")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.imagen_tk, tags="fondo")
            self.canvas.tag_lower("fondo")

    def descargar_mapa_async(self, lat, lon, api_key):
        if self.descargando_mapa: return
        self.descargando_mapa = True
        def tarea_fondo():
            img = self.peticion_mapquest(lat, lon, api_key)
            if img: self.root.after(0, self.actualizar_imagen_mapa, img)
            self.descargando_mapa = False
        threading.Thread(target=tarea_fondo, daemon=True).start()

    def actualizar_interfaz(self, lat, lon, altitud, easting, northing, num_sats):
        vel, sentido, dist_m = self.calcular_velocidad_y_sentido(northing, easting)
        self.ultimo_utm = (northing, easting)

        # --- LÓGICA ORDENADOR DE A BORDO ---
        self.distancia_total += dist_m
        if vel > 0.5: # Solo hacemos media si el coche se mueve algo
            self.lecturas_velocidad.append(vel)
        v_media = sum(self.lecturas_velocidad) / len(self.lecturas_velocidad) if self.lecturas_velocidad else 0.0
        
        self.lbl_trip.config(text=f"Recorrido: {self.distancia_total:.1f} m  |  V. Media: {v_media:.1f} Km/h")

        if self.mapa_seleccionado.get() != "Internet (MapQuest Satélite)":
            x, y = self.utm_a_pixeles(easting, northing)
            if self.historial_puntos_pixeles:
                ult_x, ult_y = self.historial_puntos_pixeles[-1]
                self.canvas.create_line(ult_x, ult_y, x, y, fill="blue", width=3, tags="ruta")
            self.historial_puntos_pixeles.append((x, y))
        else:
            x, y = self.ancho_canvas // 2, self.alto_canvas // 2

        self.dibujar_coche_flecha(x, y, sentido)
        self.canvas.tag_raise("coche")
        self.canvas.tag_raise("senal")

        limite = self.mapa_electronico.obtener_limite_velocidad(northing, easting, sentido)
        if limite > 0:
            color = self.mapa_electronico.evaluar_aviso(vel, limite)
            txt_limite = f"INSIA - Límite: {limite} Km/h | Sentido: {sentido:.1f}º"
            if int(limite) in self.senales_tk:
                self.canvas.itemconfig(self.senal_canvas_id, image=self.senales_tk[int(limite)])
        else:
            color = "gray"
            txt_limite = f"Fuera de pista de pruebas | Sentido: {sentido:.1f}º"
            self.canvas.itemconfig(self.senal_canvas_id, image=None)

        self.frame_aviso.config(bg=color)
        self.lbl_velocidad.config(text=f"{vel:.1f} Km/h", bg=color)
        self.lbl_limite.config(text=txt_limite, bg="lightgray")
        self.label_info.config(text=f"Lat: {lat:.5f} | Lon: {lon:.5f} | Satélites: {num_sats}")

    def iniciar_conexion(self):
        if self.leyendo: return 
        puerto = self.entry_puerto.get().strip()
        if not puerto: return
        self.leyendo = True
        self.btn_conectar.config(text="Conectado", state=tk.DISABLED)
        threading.Thread(target=self.leer_gps_continuamente, args=(puerto,), daemon=True).start()

    def leer_gps_continuamente(self, puerto):
        try:
            # Nota: Algunos G-MOUSE modernos van mejor a 9600 baudios. 
            # Si a 4800 te va bien a baja velocidad, déjalo así.
            ser = serial.Serial(port=puerto, baudrate=4800, timeout=1)
            self.root.after(0, lambda: self.label_info.config(text="GPS Conectado. Procesando..."))
            
            while self.leyendo:
                try: # <-- ESTE TRY NUEVO EVITA QUE PETE CON LÍNEAS CORRUPTAS
                    linea = ser.readline().decode("ascii", errors="replace").strip()
                    if "$GPGGA" in linea or "$GNGGA" in linea:
                        datos = parsear_gga(linea)
                        if datos and datos.get("calidad_fix", 0) > 0:
                            lat, lon = datos["latitud_decimal"], datos["longitud_decimal"]
                            alt = datos.get("altitud", 0.0)
                            utm = geograficas_a_utm(lat, lon)
                            
                            self.root.after(0, self.actualizar_interfaz, lat, lon, alt, utm['easting'], utm['northing'], datos['num_satelites'])
                            
                            if self.mapa_seleccionado.get() == "Internet (MapQuest Satélite)":
                                if self.API_KEY and "Pon_Tu_Clave" not in self.API_KEY:
                                    self.descargar_mapa_async(lat, lon, self.API_KEY)
                except Exception as e_linea:
                    # Si la línea viene rota a 80km/h, la ignoramos silenciosamente y seguimos
                    continue
                    
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Problema puerto:\n{e}"))
            self.root.after(0, self.desconectar)

    def desconectar(self):
        self.leyendo = False
        self.btn_conectar.config(text="Conectar", state=tk.NORMAL)

    def cerrar(self):
        self.leyendo = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NavegadorGPS(root)
    root.protocol("WM_DELETE_WINDOW", app.cerrar)
    root.mainloop()