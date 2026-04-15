import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import serial
import threading
import csv
import math
import os
import logging

from parseo_tramas import parsear_gga
from conversion_utm import geograficas_a_utm

# --- CONFIGURACIÓN DE LOS MAPAS ---
MAPAS = {
    "Campus Sur": {
        "archivo": "etsisi.PNG",
        "E_MIN": 446193.00, "N_MAX": 4471374.00,
        "E_MAX": 447008.00, "N_MIN": 4470787.00,
        "mapa_velocidad": "campus_sur_mapa.csv"
    },
    "INSIA": {
        "archivo": "insia.PNG", 
        "E_MIN": 446237.00, "N_MAX": 4470980.00,
        "E_MAX": 446444.00, "N_MIN": 4470777.00,
        "mapa_velocidad": "insia_mapa.csv"
    }
}

MARGEN_AVISO = 0.10
VELOCIDAD_MAX_VALIDA_KMH = 250.0
COLOR_VELOCIDAD_BAJA = "green"
COLOR_VELOCIDAD_MEDIA = "yellow"
COLOR_VELOCIDAD_ALTA = "red"
DT_MAX_VALIDO_S = 5.0

logger = logging.getLogger(__name__)

class NavegadorGPS:
    def __init__(self, root):
        self.root = root
        self.root.title("Navegador GPS - Práctica 3")
        
        self.leyendo = False
        self.historial_puntos = [] # lista vacia donde se guardarán las coordenadas en píxeles para trazar la ruta
        self.mapa_velocidades = []
        self.archivo_mapa_velocidad = None
        self.ultimo_idx_mapa = None
        self.ultima_pos_utm = None
        self.ultimo_tiempo_s = None
        self.velocidad_kmh = 0.0
        self.sentido_texto = "N/D"
        self.limite_actual = None
        
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

        self.btn_cargar_mapa = tk.Button(
            frame_controles,
            text="Cargar mapa velocidades",
            command=self.seleccionar_mapa_velocidad
        )
        self.btn_cargar_mapa.pack(side=tk.LEFT, padx=(10, 5))
        
        self.canvas = tk.Canvas(root, bg="gray")
        self.canvas.pack()
        
        self.imagen_tk = None
        self.mapa_actual = None
        
        self.radio_coche = 6
        self.coche = self.canvas.create_oval(-20, -20, -20, -20, fill="red", outline="black", width=2)
        
        self.label_info = tk.Label(root, text="Esperando conexión...", bg="white", font=("Arial", 10), pady=5)
        self.label_info.pack(fill=tk.X, side=tk.BOTTOM)

        self.label_aviso = tk.Label(
            root,
            text="Velocidad: 0.0 km/h",
            bg="lightgray",
            fg="black",
            font=("Arial", 18, "bold"),
            pady=8
        )
        self.label_aviso.pack(fill=tk.X, side=tk.BOTTOM)
        
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
            self.ultimo_idx_mapa = None
            self.ultima_pos_utm = None
            self.ultimo_tiempo_s = None
            self.velocidad_kmh = 0.0
            self.sentido_texto = "N/D"
            self.limite_actual = None
            self.label_aviso.config(text="Velocidad: 0.0 km/h", bg="lightgray")
            self.archivo_mapa_velocidad = self.mapa_actual.get("mapa_velocidad")
            self.cargar_mapa_velocidades(self.archivo_mapa_velocidad)
            
            self.label_info.config(text=f"Mapa cambiado a {nombre_mapa}. Esperando GPS...")
            
        except FileNotFoundError:
            messagebox.showerror("Error", f"No se encuentra la imagen '{self.mapa_actual['archivo']}'.")

    def seleccionar_mapa_velocidad(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar mapa de velocidad",
            filetypes=[("CSV", "*.csv"), ("Texto", "*.txt"), ("Todos", "*.*")]
        )
        if not archivo:
            return
        self.archivo_mapa_velocidad = archivo
        self.cargar_mapa_velocidades(archivo)

    def cargar_mapa_velocidades(self, ruta_archivo):
        self.mapa_velocidades = []
        if not ruta_archivo:
            return

        ruta_resuelta = ruta_archivo
        if not os.path.isabs(ruta_resuelta):
            ruta_resuelta = os.path.join(os.path.dirname(__file__), ruta_resuelta)

        try:
            with open(ruta_resuelta, "r", encoding="utf-8") as f:
                lector = csv.reader(f)
                for fila in lector:
                    if not fila:
                        continue
                    if len(fila) == 1:
                        fila = [v.strip() for v in fila[0].replace(";", ",").split(",")]
                    else:
                        fila = [v.strip() for v in fila]
                    if len(fila) < 3:
                        continue
                    try:
                        # CSV esperado: 1) UTM_Norte (Northing), 2) UTM_Este (Easting), 3) Velocidad_Máxima.
                        northing_utm = float(fila[0])
                        easting_utm = float(fila[1])
                        vmax = float(fila[2])
                        self.mapa_velocidades.append((northing_utm, easting_utm, vmax))
                    except ValueError:
                        continue

            if self.mapa_velocidades:
                self.label_info.config(
                    text=f"Mapa velocidades cargado: {os.path.basename(ruta_resuelta)} ({len(self.mapa_velocidades)} puntos)"
                )
            else:
                self.label_info.config(text=f"No se encontraron puntos válidos en {os.path.basename(ruta_resuelta)}.")
        except FileNotFoundError:
            self.label_info.config(text=f"Mapa velocidades no encontrado: {os.path.basename(ruta_resuelta)}.")
        except Exception as e:
            self.label_info.config(text=f"Error cargando mapa velocidades: {e}")

    def hora_utc_a_segundos(self, hora_utc):
        if not hora_utc or "UTC" not in hora_utc:
            return None
        try:
            hora = hora_utc.replace(" UTC", "")
            h, m, s = hora.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            return None

    def calcular_velocidad_kmh(self, easting, northing, hora_utc):
        t_actual = self.hora_utc_a_segundos(hora_utc)
        if self.ultima_pos_utm is None or t_actual is None or self.ultimo_tiempo_s is None:
            self.ultima_pos_utm = (easting, northing)
            self.ultimo_tiempo_s = t_actual
            return 0.0

        dt = t_actual - self.ultimo_tiempo_s
        if dt < 0:
            # Ajuste por cruce de medianoche UTC (23:59:xx -> 00:00:xx).
            dt += 24 * 3600
        if dt <= 0 or dt > DT_MAX_VALIDO_S:
            return self.velocidad_kmh

        distancia_m = math.hypot(easting - self.ultima_pos_utm[0], northing - self.ultima_pos_utm[1])

        velocidad = (distancia_m / dt) * 3.6
        if velocidad > VELOCIDAD_MAX_VALIDA_KMH:
            logger.warning("Velocidad GPS descartada (%.1f km/h).", velocidad)
            return self.velocidad_kmh

        self.ultima_pos_utm = (easting, northing)
        self.ultimo_tiempo_s = t_actual
        return velocidad

    def map_matching(self, easting, northing):
        if not self.mapa_velocidades:
            return None

        idx_min = None
        dist_min = float("inf")
        for idx, (n_map, e_map, _) in enumerate(self.mapa_velocidades):
            d2 = (e_map - easting) ** 2 + (n_map - northing) ** 2
            if d2 < dist_min:
                dist_min = d2
                idx_min = idx
        return idx_min

    def calcular_sentido(self, idx_actual):
        if idx_actual is None or self.ultimo_idx_mapa is None or not self.mapa_velocidades:
            return self.sentido_texto

        # El mapa de la pista se trata como circuito cerrado; usamos módulo para gestionar el salto inicio/fin.
        total = len(self.mapa_velocidades)
        avance = (idx_actual - self.ultimo_idx_mapa) % total
        retroceso = (self.ultimo_idx_mapa - idx_actual) % total

        if avance == retroceso:
            # Movimiento ambiguo o sin avance apreciable entre muestras.
            return self.sentido_texto
        if avance < retroceso:
            return "Horario"
        return "Antihorario"

    def utm_a_pixeles(self, easting, northing):
        E_MIN = self.mapa_actual["E_MIN"]
        E_MAX = self.mapa_actual["E_MAX"]
        N_MIN = self.mapa_actual["N_MIN"]
        N_MAX = self.mapa_actual["N_MAX"]
        
        x = ((easting - E_MIN) / (E_MAX - E_MIN)) * self.ancho_img
        y = ((N_MAX - northing) / (N_MAX - N_MIN)) * self.alto_img
        
        return int(x), int(y)

    def actualizar_interfaz(self, easting, northing, num_sats, velocidad_kmh, limite, sentido):
        x, y = self.utm_a_pixeles(easting, northing)
        
        if self.historial_puntos:
            ult_x, ult_y = self.historial_puntos[-1]
            self.canvas.create_line(ult_x, ult_y, x, y, fill="blue", width=3, tags="ruta")
            
        self.historial_puntos.append((x, y))
        
        self.canvas.coords(self.coche, 
                           x - self.radio_coche, y - self.radio_coche, 
                           x + self.radio_coche, y + self.radio_coche)
        self.canvas.tag_raise(self.coche)

        color = "lightgray"
        if limite is not None and limite > 0:
            umbral_bajo = limite * (1.0 - MARGEN_AVISO)
            umbral_alto = limite * (1.0 + MARGEN_AVISO)
            if velocidad_kmh < umbral_bajo:
                color = COLOR_VELOCIDAD_BAJA
            elif velocidad_kmh <= umbral_alto:
                color = COLOR_VELOCIDAD_MEDIA
            else:
                color = COLOR_VELOCIDAD_ALTA

        self.label_aviso.config(text=f"Velocidad: {velocidad_kmh:.1f} km/h", bg=color)

        limite_txt = f"{limite:.1f} km/h" if limite is not None else "N/D"
        texto = (
            f"Easting: {easting:.2f} | Northing: {northing:.2f} | Satélites: {num_sats} | "
            f"Límite: {limite_txt} | Sentido: {sentido}"
        )
        self.label_info.config(text=texto)

    def procesar_posicion(self, easting, northing, num_sats, hora_utc):
        self.velocidad_kmh = self.calcular_velocidad_kmh(easting, northing, hora_utc)
        idx_mapa = self.map_matching(easting, northing)
        limite = None
        sentido = self.sentido_texto

        if idx_mapa is not None:
            sentido = self.calcular_sentido(idx_mapa)
            limite = self.mapa_velocidades[idx_mapa][2]
            self.ultimo_idx_mapa = idx_mapa
            self.sentido_texto = sentido
            self.limite_actual = limite

        self.root.after(
            0,
            self.actualizar_interfaz,
            easting,
            northing,
            num_sats,
            self.velocidad_kmh,
            self.limite_actual,
            self.sentido_texto
        )

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
                        self.procesar_posicion(
                            utm['easting'],
                            utm['northing'],
                            datos['num_satelites'],
                            datos.get("hora_utc")
                        )
                        
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
