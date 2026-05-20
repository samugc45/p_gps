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


class NavegadorGPS:
    def __init__(self, root):
        self.root = root
        self.root.title("Navegador GPS - Edición Profesional")
        
        self.API_KEY = "sLxMqoKMmWHIEVqLfAL84uoma0iijdBA"
        
        self.leyendo = False
        self.ultimo_utm = None     
        self.mapa_electronico = MapaINSIA("mapa_insia.txt") 
        self.descargando_mapa = False
        
        self.historial_gps = []

        self.distancia_total = 0.0
        self.lecturas_velocidad = []
        self.nivel_zoom = 18
        self.tipo_vista = tk.StringVar(value="hyb") 
        self.rotar_mapa = tk.BooleanVar(value=False)
        
        self.frame_aviso = tk.Frame(root, bg="gray", height=120)
        self.frame_aviso.pack(fill=tk.X, side=tk.TOP)
        self.frame_aviso.pack_propagate(False) 
        
        self.lbl_velocidad = tk.Label(self.frame_aviso, text="0.0 Km/h", font=("Arial", 32, "bold"), bg="gray", fg="black")
        self.lbl_velocidad.pack(expand=True, fill=tk.BOTH)
        
        self.lbl_trip = tk.Label(self.frame_aviso, text="Recorrido: 0.0 m | V. Media: 0.0 Km/h", font=("Arial", 11, "bold"), bg="black", fg="white")
        self.lbl_trip.pack(fill=tk.X)

        self.lbl_limite = tk.Label(self.frame_aviso, text="Límite: -- Km/h | Sentido: --º", font=("Arial", 11), bg="lightgray")
        self.lbl_limite.pack(fill=tk.X, side=tk.BOTTOM)

        frame_controles = tk.Frame(root, padx=10, pady=5)
        frame_controles.pack(fill=tk.X)
        
        tk.Label(frame_controles, text="Puerto:").pack(side=tk.LEFT)
        self.entry_puerto = tk.Entry(frame_controles, width=8)
        self.entry_puerto.insert(0, "COM1") 
        self.entry_puerto.pack(side=tk.LEFT, padx=5)
        
        self.btn_conectar = tk.Button(frame_controles, text="Conectar GPS", command=self.iniciar_conexion, bg="lightblue", font=("Arial", 10, "bold"))
        self.btn_conectar.pack(side=tk.LEFT, padx=5)

        frame_mejoras = tk.Frame(root, padx=10, pady=5)
        frame_mejoras.pack(fill=tk.X)

        tk.Label(frame_mejoras, text="Capa:").pack(side=tk.LEFT)
        ttk.Radiobutton(frame_mejoras, text="Satélite", variable=self.tipo_vista, value="hyb").pack(side=tk.LEFT)
        ttk.Radiobutton(frame_mejoras, text="Calles", variable=self.tipo_vista, value="map").pack(side=tk.LEFT, padx=(0, 10))

        
        tk.Button(frame_mejoras, text="➖", command=self.zoom_out, width=2).pack(side=tk.LEFT)
        self.lbl_zoom = tk.Label(frame_mejoras, text=f"Z: {self.nivel_zoom}", width=5)
        self.lbl_zoom.pack(side=tk.LEFT)
        tk.Button(frame_mejoras, text="➕", command=self.zoom_in, width=2).pack(side=tk.LEFT, padx=(0, 10))

        
        ttk.Checkbutton(frame_mejoras, text="Rotar Mapa (Track-Up)", variable=self.rotar_mapa).pack(side=tk.LEFT, padx=10)

        self.ancho_canvas, self.alto_canvas = 600, 600
        self.canvas = tk.Canvas(root, bg="black", width=self.ancho_canvas, height=self.alto_canvas)
        self.canvas.pack()
        
        self.imagen_tk = None
        self.coche = self.canvas.create_polygon(0,0, 0,0, 0,0, fill="red", outline="white", width=2, tags="coche")

        self.senales_tk = {}
        for s in [5, 10, 15, 18, 20]:
            try: self.senales_tk[s] = ImageTk.PhotoImage(Image.open(f"senal_{s}.png").resize((90, 90)))
            except: pass
        self.senal_canvas_id = self.canvas.create_image(10, 10, anchor=tk.NW, image=None, tags="senal")
        
        self.label_info = tk.Label(root, text="Esperando conexión...", bg="white", font=("Arial", 10), pady=5)
        self.label_info.pack(fill=tk.X, side=tk.BOTTOM)

    def zoom_in(self):
        if self.nivel_zoom < 20:
            self.nivel_zoom += 1
            self.lbl_zoom.config(text=f"Z: {self.nivel_zoom}")

    def zoom_out(self):
        if self.nivel_zoom > 10:
            self.nivel_zoom -= 1
            self.lbl_zoom.config(text=f"Z: {self.nivel_zoom}")

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

    def calcular_velocidad_y_sentido(self, n_actual, e_actual):
        if not self.ultimo_utm: return 0.0, 0.0, 0.0
        n_prev, e_prev = self.ultimo_utm
        distancia_m = math.sqrt((n_actual - n_prev)**2 + (e_actual - e_prev)**2)
        velocidad_kmh = distancia_m * 3.6
        sentido_rad = math.atan2(e_actual - e_prev, n_actual - n_prev)
        sentido_grados = (math.degrees(sentido_rad) + 360) % 360
        return velocidad_kmh, sentido_grados, distancia_m

    def _latlon_to_world_px(self, lat, lon, zoom):
        tile_size = 256
        siny = math.sin(math.radians(lat))
        siny = min(max(siny, -0.9999), 0.9999)
        scale = tile_size * (2 ** zoom)
        x = (lon + 180.0) / 360.0 * scale
        y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * scale
        return x, y

    def latlon_to_screen(self, lat, lon, center_lat, center_lon):
        world_x, world_y = self._latlon_to_world_px(lat, lon, self.nivel_zoom)
        center_x, center_y = self._latlon_to_world_px(center_lat, center_lon, self.nivel_zoom)
        screen_x = (world_x - center_x) + self.ancho_canvas / 2
        screen_y = (world_y - center_y) + self.alto_canvas / 2
        return screen_x, screen_y

    def rotar_punto(self, x, y, cx, cy, ang_deg):
        ang = math.radians(ang_deg)
        dx, dy = x - cx, y - cy
        rx = dx * math.cos(ang) - dy * math.sin(ang) + cx
        ry = dx * math.sin(ang) + dy * math.cos(ang) + cy
        return rx, ry

    def peticion_mapquest(self, lat, lon, sentido):
        ancho_req = 850 if self.rotar_mapa.get() else self.ancho_canvas
        alto_req = 850 if self.rotar_mapa.get() else self.alto_canvas
        
        url = (f"https://www.mapquestapi.com/staticmap/v5/map?"
               f"key={self.API_KEY}&center={lat},{lon}&zoom={self.nivel_zoom}&"
               f"size={ancho_req},{alto_req}&type={self.tipo_vista.get()}")
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                img = Image.open(BytesIO(res.content))
                
                if self.rotar_mapa.get():
                    img = img.rotate(sentido, resample=Image.BICUBIC)
                    borde_izq = (850 - 600) // 2
                    borde_sup = (850 - 600) // 2
                    img = img.crop((borde_izq, borde_sup, borde_izq + 600, borde_sup + 600))
                
                return img
        except: pass
        return None

    def actualizar_imagen_mapa(self, img_mapa):
        if img_mapa:
            self.imagen_tk = ImageTk.PhotoImage(img_mapa)
            self.canvas.delete("fondo")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.imagen_tk, tags="fondo")
            self.canvas.tag_lower("fondo")

    def descargar_mapa_async(self, lat, lon, sentido):
        if self.descargando_mapa: return
        self.descargando_mapa = True
        def tarea_fondo():
            img = self.peticion_mapquest(lat, lon, sentido)
            if img: self.root.after(0, self.actualizar_imagen_mapa, img)
            self.descargando_mapa = False
        threading.Thread(target=tarea_fondo, daemon=True).start()

    def actualizar_interfaz(self, lat, lon, altitud, easting, northing, num_sats):
        vel, sentido, dist_m = self.calcular_velocidad_y_sentido(northing, easting)
        self.ultimo_utm = (northing, easting)

        self.distancia_total += dist_m
        if vel > 0.5:
            self.lecturas_velocidad.append(vel)
        v_media = sum(self.lecturas_velocidad) / len(self.lecturas_velocidad) if self.lecturas_velocidad else 0.0
        self.lbl_trip.config(text=f"Recorrido: {self.distancia_total:.1f} m  |  V. Media: {v_media:.1f} Km/h")

        self.historial_gps.append((lat, lon))
        self.canvas.delete("ruta")

        if len(self.historial_gps) > 1:
            puntos = []
            cx, cy = self.ancho_canvas // 2, self.alto_canvas // 2

            for plat, plon in self.historial_gps:
                x, y = self.latlon_to_screen(plat, plon, lat, lon)

                if self.rotar_mapa.get():
                    x, y = self.rotar_punto(x, y, cx, cy, -sentido)

                puntos.extend([x, y])

            if len(puntos) >= 4:
                self.canvas.create_line(puntos, fill="blue", width=3, tags="ruta")

        cx, cy = self.ancho_canvas // 2, self.alto_canvas // 2
        
        if self.rotar_mapa.get():
            self.dibujar_coche_flecha(cx, cy, 0)
        else:
            self.dibujar_coche_flecha(cx, cy, sentido)
            
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
            ser = serial.Serial(port=puerto, baudrate=4800, timeout=1)
            self.root.after(0, lambda: self.label_info.config(text="GPS Conectado. Procesando..."))
            while self.leyendo:
                try: 
                    linea = ser.readline().decode("ascii", errors="replace").strip()
                    if "$GPGGA" in linea or "$GNGGA" in linea:
                        datos = parsear_gga(linea)
                        if datos and datos.get("calidad_fix", 0) > 0:
                            lat, lon = datos["latitud_decimal"], datos["longitud_decimal"]
                            alt = datos.get("altitud", 0.0)
                            utm = geograficas_a_utm(lat, lon)
                            
                            vel, sentido, dist = self.calcular_velocidad_y_sentido(utm['northing'], utm['easting'])
                            
                            self.root.after(0, self.actualizar_interfaz, lat, lon, alt, utm['easting'], utm['northing'], datos['num_satelites'])
                            
                            if self.API_KEY and "Pon_Tu_Clave" not in self.API_KEY:
                                self.descargar_mapa_async(lat, lon, sentido)
                except Exception:
                    continue
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Problema puerto:\n{e}"))
            self.root.after(0, self.desconectar)

    def desconectar(self):
        self.leyendo = False
        self.btn_conectar.config(text="Conectar GPS", state=tk.NORMAL)
        self.label_info.config(text="Desconectado.")

    def cerrar(self):
        self.leyendo = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NavegadorGPS(root)
    root.protocol("WM_DELETE_WINDOW", app.cerrar)
    root.mainloop()