import tkinter as tk
from tkinter import ttk, messagebox
from Pillow import Image, ImageTk
import serial
import threading
import math
import os
import requests
from io import BytesIO

from parseo_tramas import parsear_gga
from conversion_utm import geograficas_a_utm

# ==========================================
# PRÁCTICA 3: MAPA INSIA Y AVISOS DE VELOCIDAD
# ==========================================
class MapaINSIA:
    def __init__(self, ruta_archivo):
        self.puntos = []
        self.cargar_mapa(ruta_archivo)

    def cargar_mapa(self, ruta_archivo):
        if not os.path.exists(ruta_archivo):
            print(f"[AVISO] No se encontró '{ruta_archivo}'.")
            return
        try:
            with open(ruta_archivo, 'r') as f:
                for linea in f:
                    if linea.strip():
                        partes = linea.replace(',', ' ').split()
                        if len(partes) >= 3:
                            self.puntos.append({
                                'N': float(partes[0]), 
                                'E': float(partes[1]), 
                                'Vmax': float(partes[2])
                            })
            
            # Cálculo del sentido de la marcha para cada tramo
            for i in range(len(self.puntos) - 1):
                p_actual = self.puntos[i]
                p_sig = self.puntos[i+1]
                delta_n = p_sig['N'] - p_actual['N']
                delta_e = p_sig['E'] - p_actual['E']
                sentido_rad = math.atan2(delta_e, delta_n)
                p_actual['Sentido'] = (math.degrees(sentido_rad) + 360) % 360
                
            if len(self.puntos) > 1:
                self.puntos[-1]['Sentido'] = self.puntos[-2]['Sentido']
                
            print(f"[INFO] Mapa INSIA cargado con {len(self.puntos)} puntos.")
        except Exception as e:
            print(f"[ERROR] No se pudo cargar el mapa: {e}")

    def obtener_limite_velocidad(self, utm_n, utm_e, sentido_coche):
        if not self.puntos:
            return 0
        distancia_minima = float('inf')
        limite_actual = 0
        
        for p in self.puntos:
            dist = math.sqrt((utm_n - p['N'])**2 + (utm_e - p['E'])**2)
            if 'Sentido' in p:
                diff_angulo = abs((sentido_coche - p['Sentido']) % 360)
                if diff_angulo > 180:
                    diff_angulo = 360 - diff_angulo
                es_mismo_sentido = diff_angulo <= 90
            else:
                es_mismo_sentido = True

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

# ==========================================
# PRÁCTICA 4: MATEMÁTICAS DEL IGN Y BBOX
# ==========================================
def bbox_from_center_zoom_vertical(lat, lon, zoom, width, height):
    """Calcula la caja (Bounding Box) en grados para el servidor IGN"""
    base_half_side_deg = 0.1  
    half_side_y = base_half_side_deg / (2 ** (zoom - 1))
    # Ajuste trigonométrico por la esfericidad terrestre
    half_side_x = half_side_y * (width / height) / math.cos(math.radians(lat))
    
    min_lat = lat - half_side_y
    max_lat = lat + half_side_y
    min_lon = lon - half_side_x
    max_lon = lon + half_side_x
    return min_lat, min_lon, max_lat, max_lon

# ==========================================
# CLASE PRINCIPAL: NAVEGADOR GPS (GUI)
# ==========================================
class NavegadorGPS:
    def __init__(self, root):
        self.root = root
        self.root.title("Navegador GPS - Práctica 4 (IGN en Vivo)")
        
        # Variables de estado
        self.leyendo = False
        self.ultimo_utm = None
        self.historial_gps = [] 
        self.mapa_electronico = MapaINSIA("mapa_insia.txt") 
        
        # Parámetros del mapa y lienzo
        self.ancho_canvas = 800
        self.alto_canvas = 600
        self.zoom = 18 # Zoom dinámico
        
        self.construir_interfaz()

    def construir_interfaz(self):
        # 1. Panel Superior (Avisos Práctica 3)
        self.frame_aviso = tk.Frame(self.root, bg="gray", height=100)
        self.frame_aviso.pack(fill=tk.X, side=tk.TOP)
        self.frame_aviso.pack_propagate(False) 
        
        self.lbl_velocidad = tk.Label(self.frame_aviso, text="0.0 Km/h", font=("Arial", 36, "bold"), bg="gray", fg="black")
        self.lbl_velocidad.pack(expand=True, fill=tk.BOTH)
        
        self.lbl_limite = tk.Label(self.frame_aviso, text="Esperando señal GPS...", font=("Arial", 12), bg="lightgray")
        self.lbl_limite.pack(fill=tk.X, side=tk.BOTTOM)

        # 2. Panel de Controles
        frame_controles = tk.Frame(self.root, padx=10, pady=5)
        frame_controles.pack(fill=tk.X)
        
        tk.Label(frame_controles, text="Puerto Serie:").pack(side=tk.LEFT)
        self.entry_puerto = tk.Entry(frame_controles, width=15)
        self.entry_puerto.insert(0, "COM1") 
        self.entry_puerto.pack(side=tk.LEFT, padx=5)
        
        self.btn_conectar = tk.Button(frame_controles, text="Conectar", command=self.iniciar_conexion, bg="lightblue")
        self.btn_conectar.pack(side=tk.LEFT, padx=5)
        
        # 3. El Lienzo (Canvas)
        self.canvas = tk.Canvas(self.root, width=self.ancho_canvas, height=self.alto_canvas, bg="black")
        self.canvas.pack()
        self.imagen_tk = None
        
        # 4. El coche fijo en el centro
        self.radio_coche = 6
        cx = self.ancho_canvas // 2
        cy = self.alto_canvas // 2
        self.coche = self.canvas.create_oval(
            cx - self.radio_coche, cy - self.radio_coche, 
            cx + self.radio_coche, cy + self.radio_coche, 
            fill="red", outline="white", width=2
        )

        # 5. Carga de señales visuales (Práctica 3)
        self.senales_tk = {}
        for limite in [5, 10, 15, 18, 20]:
            try:
                # Omitimos el error si falta alguna imagen
                self.senales_tk[limite] = ImageTk.PhotoImage(Image.open(f"senal_{limite}.png").resize((80, 80)))
            except Exception: pass
            
        self.senal_canvas_id = self.canvas.create_image(10, 10, anchor=tk.NW, image=None, tags="senal")
        
        # 6. Barra inferior
        self.label_info = tk.Label(self.root, text="Desconectado.", bg="white", font=("Arial", 10), pady=5)
        self.label_info.pack(fill=tk.X, side=tk.BOTTOM)

    # --- Lógica de la Práctica 3 ---
    def calcular_velocidad_y_sentido(self, n_actual, e_actual):
        if not self.ultimo_utm: return 0.0, 0.0
        n_prev, e_prev = self.ultimo_utm
        distancia_m = math.sqrt((n_actual - n_prev)**2 + (e_actual - e_prev)**2)
        velocidad_kmh = distancia_m * 3.6
        sentido_rad = math.atan2(e_actual - e_prev, n_actual - n_prev)
        sentido_grados = (math.degrees(sentido_rad) + 360) % 360
        return velocidad_kmh, sentido_grados

    # --- Lógica de la Práctica 4 (Descarga WMS) ---
    def peticion_ign(self, lat, lon):
        bbox = bbox_from_center_zoom_vertical(lat, lon, self.zoom, self.ancho_canvas, self.alto_canvas)
        url = "https://www.ign.es/wms-inspire/pnoa-ma?"
        params = {
            "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
            "LAYERS": "OI.OrthoimageCoverage", "CRS": "EPSG:4326",
            "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "WIDTH": self.ancho_canvas, "HEIGHT": self.alto_canvas, "FORMAT": "image/png"
        }
        try:
            # timeout corto para evitar que el programa se congele si no hay red
            res = requests.get(url, params=params, timeout=3)
            if res.status_code == 200:
                return Image.open(BytesIO(res.content)), bbox
        except Exception as e:
            print(f"[ERROR IGN] {e}")
        return None, bbox

    # --- Motor de Dibujado ---
    def actualizar_interfaz(self, lat, lon, easting, northing, num_sats, img_pil, bbox):
        # 1. Pintar el mapa descargado
        if img_pil:
            self.imagen_tk = ImageTk.PhotoImage(img_pil)
            self.canvas.delete("fondo")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.imagen_tk, tags="fondo")
            self.canvas.tag_lower("fondo")

        # 2. Recalcular y pintar la estela de puntos azules
        self.historial_gps.append((lat, lon))
        self.canvas.delete("ruta")
        if len(self.historial_gps) > 1 and bbox:
            puntos_pantalla = []
            min_lat, min_lon, max_lat, max_lon = bbox
            for plat, plon in self.historial_gps:
                x = ((plon - min_lon) / (max_lon - min_lon)) * self.ancho_canvas
                y = ((max_lat - plat) / (max_lat - min_lat)) * self.alto_canvas
                puntos_pantalla.extend([x, y])
            if len(puntos_pantalla) >= 4:
                self.canvas.create_line(puntos_pantalla, fill="blue", width=3, tags="ruta")

        # 3. Elevar el coche y la señal para que se vean
        self.canvas.tag_raise(self.coche)
        self.canvas.tag_raise("senal")

        # 4. Velocidad, Avisos y Señales (Práctica 3)
        vel, sentido = self.calcular_velocidad_y_sentido(northing, easting)
        self.ultimo_utm = (northing, easting)
        
        limite = self.mapa_electronico.obtener_limite_velocidad(northing, easting, sentido)
        if limite > 0:
            color = self.mapa_electronico.evaluar_aviso(vel, limite)
            txt_limite = f"INSIA - Límite: {limite} Km/h | Sentido: {sentido:.1f}º"
            if int(limite) in self.senales_tk:
                self.canvas.itemconfig(self.senal_canvas_id, image=self.senales_tk[int(limite)])
        else:
            color = "gray"
            txt_limite = f"Fuera de pista controlada | Sentido: {sentido:.1f}º"
            self.canvas.itemconfig(self.senal_canvas_id, image=None)

        self.frame_aviso.config(bg=color)
        self.lbl_velocidad.config(text=f"{vel:.1f} Km/h", bg=color)
        self.lbl_limite.config(text=txt_limite, bg="lightgray")

        # 5. Barra inferior
        self.label_info.config(text=f"Lat: {lat:.5f} | Lon: {lon:.5f} | Satélites: {num_sats}")

    # --- Gestión de la Conexión Serie ---
    def iniciar_conexion(self):
        if self.leyendo: return 
        puerto = self.entry_puerto.get().strip()
        if not puerto:
            messagebox.showwarning("Aviso", "Por favor, introduce un puerto serie.")
            return
            
        self.leyendo = True
        self.btn_conectar.config(text="Conectado", state=tk.DISABLED)
        self.hilo_gps = threading.Thread(target=self.leer_gps_continuamente, args=(puerto,), daemon=True)
        self.hilo_gps.start()

    def leer_gps_continuamente(self, puerto):
        try:
            ser = serial.Serial(port=puerto, baudrate=4800, timeout=1)
            self.root.after(0, lambda: self.label_info.config(text="GPS Conectado..."))
            
            while self.leyendo:
                linea = ser.readline().decode("ascii", errors="replace").strip()
                if "$GPGGA" in linea or "$GNGGA" in linea:
                    datos = parsear_gga(linea)
                    
                    if datos and datos.get("calidad_fix", 0) > 0:
                        lat = datos["latitud_decimal"]
                        lon = datos["longitud_decimal"]
                        utm = geograficas_a_utm(lat, lon)
                        
                        # [NUEVO P4] Petición síncrona al IGN en el hilo de fondo
                        img_pil, bbox = self.peticion_ign(lat, lon)
                        
                        # Mandamos la información a la GUI principal
                        self.root.after(0, self.actualizar_interfaz, lat, lon, utm['easting'], utm['northing'], datos['num_satelites'], img_pil, bbox)
                        
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Problema con el puerto:\n{e}"))
            self.root.after(0, self.desconectar)

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