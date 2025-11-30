import customtkinter as ctk
import os
import sys
import threading
import time
import io
import qrcode
import fitz  # PyMuPDF
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox
from supabase import create_client

# --- 1. FUNCIÓN CRÍTICA PARA RUTAS (SOLUCIÓN LOGO) ---
def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # En desarrollo, busca relativo a donde está este script
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

# --- CONFIGURACIÓN DE RUTAS ---
# Usamos solo el nombre del archivo porque resource_path se encarga de ubicarlo en la misma carpeta
RUTA_ICONO = resource_path("logo_iisep.ico")
RUTA_LOGO_PNG = resource_path("logo_iisep.png")

# --- NUEVA PALETA INSTITUCIONAL (IISEP) ---
THEME = {
    "dark": {
        "bg_app": "#0f172a",       # Azul noche profundo (Slate 900)
        "panel": "#1e293b",        # Azul pizarra oscuro (Slate 800)
        "text": "#f8fafc",         # Blanco hueso
        "text_sec": "#94a3b8",     # Gris azulado
        "input": "#334155",        # Slate 700
        "border": "#475569",       # Slate 600
        "accent": "#2563eb",       # Azul Real (Botones principales)
        "accent_hover": "#1d4ed8", 
        "success": "#059669",      # Verde esmeralda sobrio
        "danger": "#dc2626",       # Rojo institucional
        "preview_bg": "#020617"    # Casi negro para el fondo del PDF
    },
    "light": {
        "bg_app": "#f1f5f9",       # Gris muy claro (Slate 100)
        "panel": "#ffffff",        # Blanco puro
        "text": "#0f172a",         # Azul noche (texto principal)
        "text_sec": "#64748b",     # Gris pizarra
        "input": "#e2e8f0",        # Slate 200
        "border": "#cbd5e1",       # Slate 300
        "accent": "#0f5bb5",       # Azul Institucional Fuerte
        "accent_hover": "#0a458a",
        "success": "#10b981",      # Verde suave
        "danger": "#ef4444",       # Rojo suave
        "preview_bg": "#cbd5e1"    # Gris para fondo PDF
    }
}

# --- DATOS IISEP ---
CARRERAS_IISEP = [
    "--- CARRERAS TÉCNICAS ---", "Computación", "Logística y Almacenes", "Gastronomía",
    "Instalaciones Electrotécnicas", "Cosmetología",
    "--- MÓDULOS Y TALLERES ---", "Ofimática", "Diseño Gráfico", "Ensamblaje de PC",
    "Barber Shop", "Inglés", "Uñas Acrílicas",
    "--- OTROS ---", "Otro (Especificar)"
]

# --- CREDENCIALES (Mantener tus credenciales) ---
URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s"
WEB_URL = "https://validador-certificados.vercel.app/"

class SingleCertApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración Visual Inicial
        ctk.set_appearance_mode("System") # Usa el del sistema por defecto
        ctk.set_default_color_theme("blue")
        
        # Detectar modo inicial
        self.modo_oscuro = ctk.get_appearance_mode() == "Dark"
        self.colors = THEME["dark"] if self.modo_oscuro else THEME["light"]

        self.title("Sistema de Certificación IISEP v2.1")
        self.geometry("1100x750")
        self.minsize(1000, 700)
        
        # Icono de ventana
        try:
            if os.path.exists(RUTA_ICONO):
                self.iconbitmap(RUTA_ICONO)
        except: pass

        # Variables de Estado
        self.selected_file_path = None
        self.generated_file_path = None
        self.supabase = None
        self.preview_image_ref = None 
        self.logo_image_ref = None 

        # Layout Principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3) # Más espacio para la vista previa
        self.grid_rowconfigure(1, weight=1)

        self.setup_ui()
        
        # Conexión silenciosa
        threading.Thread(target=self.connect_db, daemon=True).start()

    def setup_ui(self):
        self.configure(fg_color=self.colors["bg_app"])
        self.setup_header()
        self.setup_left_panel()
        self.setup_right_panel()

    def actualizar_paleta(self):
        """Refresca la paleta de colores según el modo"""
        self.colors = THEME["dark"] if self.modo_oscuro else THEME["light"]
        
        # 1. Fondo Principal
        self.configure(fg_color=self.colors["bg_app"])
        
        # 2. Header
        self.header.configure(fg_color=self.colors["panel"])
        self.lbl_sistema.configure(text_color=self.colors["text"])
        
        # 3. Paneles
        self.frame_left.configure(fg_color=self.colors["panel"], border_color=self.colors["border"])
        self.frame_right.configure(fg_color=self.colors["preview_bg"], border_color=self.colors["border"])
        
        # 4. Textos y Labels Panel Izquierdo
        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, ctk.CTkLabel):
                # Diferenciar entre títulos y texto normal por la fuente (simple heuristic)
                if widget.cget("font")[1] > 14: # Títulos
                    widget.configure(text_color=self.colors["accent"])
                else:
                    widget.configure(text_color=self.colors["text"])
            
            if isinstance(widget, ctk.CTkEntry):
                widget.configure(fg_color=self.colors["input"], 
                               border_color=self.colors["border"], 
                               text_color=self.colors["text"],
                               placeholder_text_color=self.colors["text_sec"])
            
            if isinstance(widget, ctk.CTkComboBox):
                widget.configure(fg_color=self.colors["input"],
                               border_color=self.colors["border"],
                               text_color=self.colors["text"],
                               dropdown_fg_color=self.colors["panel"],
                               dropdown_text_color=self.colors["text"],
                               button_color=self.colors["border"],
                               button_hover_color=self.colors["accent"])

        # 5. Botones
        self.btn_load.configure(fg_color=self.colors["input"], text_color=self.colors["text"], hover_color=self.colors["border"])
        self.btn_process.configure(fg_color=self.colors["accent"], hover_color=self.colors["accent_hover"])
        self.btn_open.configure(fg_color=self.colors["success"])
        self.btn_clean.configure(fg_color=self.colors["danger"])
        self.btn_info.configure(fg_color=self.colors["input"], text_color=self.colors["text"], hover_color=self.colors["border"])

        # 6. Vista Previa
        self.lbl_preview.configure(text_color=self.colors["text_sec"])

    def toggle_theme(self):
        self.modo_oscuro = not self.modo_oscuro
        ctk.set_appearance_mode("Dark" if self.modo_oscuro else "Light")
        self.switch.configure(text="Modo Oscuro" if self.modo_oscuro else "Modo Claro")
        self.actualizar_paleta()

    # --- HEADER ---
    def setup_header(self):
        self.header = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color=self.colors["panel"])
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        inner_header = ctk.CTkFrame(self.header, fg_color="transparent")
        inner_header.pack(expand=True, fill="both", padx=30, pady=10)
        
        # Logo
        try:
            if os.path.exists(RUTA_LOGO_PNG):
                img_pil = Image.open(RUTA_LOGO_PNG)
                # Ajuste de tamaño proporcional
                h = 50
                w = int((h / img_pil.size[1]) * img_pil.size[0])
                img_pil = img_pil.resize((w, h), Image.Resampling.LANCZOS)
                self.logo_image_ref = ImageTk.PhotoImage(img_pil)
                ctk.CTkLabel(inner_header, image=self.logo_image_ref, text="").pack(side="left", padx=(0, 20))
        except Exception as e:
            print(f"Logo no cargado: {e}")

        # Título
        text_frame = ctk.CTkFrame(inner_header, fg_color="transparent")
        text_frame.pack(side="left", fill="y", pady=5)
        
        self.lbl_sistema = ctk.CTkLabel(text_frame, text="SISTEMA DE CERTIFICACIÓN DIGITAL", 
                                      font=("Roboto Medium", 20), text_color=self.colors["text"])
        self.lbl_sistema.pack(anchor="w")
        
        ctk.CTkLabel(text_frame, text="Validador Institucional IISEP", 
                    font=("Roboto", 12), text_color=self.colors["text_sec"]).pack(anchor="w")

        # Switch
        self.switch = ctk.CTkSwitch(inner_header, text="Modo Auto", command=self.toggle_theme,
                                  progress_color=self.colors["accent"])
        self.switch.pack(side="right")
        # Setear switch visualmente correcto al inicio
        if self.modo_oscuro: self.switch.select() 
        self.switch.configure(text="Modo Oscuro" if self.modo_oscuro else "Modo Claro")

    # --- PANEL IZQUIERDO ---
    def setup_left_panel(self):
        self.frame_left = ctk.CTkFrame(self, corner_radius=15, fg_color=self.colors["panel"], 
                                     border_width=1, border_color=self.colors["border"])
        self.frame_left.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=20)
        
        self.scrollable_frame = ctk.CTkScrollableFrame(self.frame_left, fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Helper para crear inputs estilizados
        def add_field(label, widget_cls, **kwargs):
            ctk.CTkLabel(self.scrollable_frame, text=label, font=("Roboto Medium", 13), 
                       text_color=self.colors["text_sec"]).pack(anchor="w", pady=(10, 2))
            widget = widget_cls(self.scrollable_frame, height=45, font=("Roboto", 14), 
                              fg_color=self.colors["input"], border_color=self.colors["border"],
                              text_color=self.colors["text"], **kwargs)
            widget.pack(fill="x", pady=(0, 10))
            return widget

        # Campos
        ctk.CTkLabel(self.scrollable_frame, text="DATOS DEL ESTUDIANTE", 
                   font=("Roboto", 16, "bold"), text_color=self.colors["accent"]).pack(anchor="w", pady=(10, 15))
        
        self.entry_nom = add_field("Nombre Completo", ctk.CTkEntry, placeholder_text="Ej: JUAN PEREZ")
        self.entry_dni = add_field("DNI", ctk.CTkEntry, placeholder_text="8 dígitos")
        
        ctk.CTkLabel(self.scrollable_frame, text="Especialidad / Taller", font=("Roboto Medium", 13), 
                       text_color=self.colors["text_sec"]).pack(anchor="w", pady=(10, 2))
        self.combo_carrera = ctk.CTkComboBox(self.scrollable_frame, values=CARRERAS_IISEP, height=45,
                                           font=("Roboto", 14), fg_color=self.colors["input"],
                                           dropdown_fg_color=self.colors["panel"],
                                           text_color=self.colors["text"], border_color=self.colors["border"],
                                           button_color=self.colors["border"], button_hover_color=self.colors["accent"])
        self.combo_carrera.set("Computación")
        self.combo_carrera.pack(fill="x", pady=(0, 10))

        self.entry_fecha = add_field("Fecha de Emisión", ctk.CTkEntry)
        self.entry_fecha.insert(0, time.strftime("%d/%m/%Y"))

        # Sección Archivo
        ctk.CTkLabel(self.scrollable_frame, text="DOCUMENTO BASE", 
                   font=("Roboto", 16, "bold"), text_color=self.colors["accent"]).pack(anchor="w", pady=(25, 10))
        
        self.lbl_filename = ctk.CTkLabel(self.scrollable_frame, text="Seleccione el PDF de la constancia", 
                                       text_color=self.colors["text_sec"], font=("Roboto", 12))
        self.lbl_filename.pack(anchor="w")

        self.btn_load = ctk.CTkButton(self.scrollable_frame, text="📂 Seleccionar PDF", height=45, 
                                    font=("Roboto Medium", 13), command=self.select_file,
                                    fg_color=self.colors["input"], text_color=self.colors["text"],
                                    hover_color=self.colors["border"], border_width=1, border_color=self.colors["border"])
        self.btn_load.pack(fill="x", pady=10)

        # Botón Principal
        self.btn_process = ctk.CTkButton(self.frame_left, text="GENERAR CERTIFICADO", height=55,
                                       font=("Roboto", 15, "bold"), command=self.start_processing,
                                       state="disabled", fg_color=self.colors["accent"], 
                                       hover_color=self.colors["accent_hover"], corner_radius=12)
        self.btn_process.pack(side="bottom", fill="x", padx=20, pady=20)

    # --- PANEL DERECHO (PREVIEW) ---
    def setup_right_panel(self):
        self.frame_right = ctk.CTkFrame(self, corner_radius=15, fg_color=self.colors["preview_bg"],
                                      border_width=1, border_color=self.colors["border"])
        self.frame_right.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=20)
        self.frame_right.grid_rowconfigure(0, weight=1)
        self.frame_right.grid_columnconfigure(0, weight=1)

        self.lbl_preview = ctk.CTkLabel(self.frame_right, text="\nVista Previa del Documento",
                                      font=("Roboto", 16), text_color=self.colors["text_sec"])
        self.lbl_preview.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        # Botonera inferior
        actions = ctk.CTkFrame(self.frame_right, fg_color="transparent", height=60)
        actions.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        actions.grid_columnconfigure((0,1,2), weight=1)

        self.btn_open = ctk.CTkButton(actions, text="Abrir PDF", command=self.open_file, state="disabled",
                                    height=45, fg_color=self.colors["success"], font=("Roboto", 13, "bold"))
        self.btn_open.grid(row=0, column=0, padx=5, sticky="ew")

        self.btn_clean = ctk.CTkButton(actions, text="Limpiar", command=self.reset_form,
                                     height=45, fg_color=self.colors["danger"], font=("Roboto", 13, "bold"))
        self.btn_clean.grid(row=0, column=1, padx=5, sticky="ew")

        self.btn_info = ctk.CTkButton(actions, text="Info", command=self.show_info,
                                    height=45, fg_color=self.colors["input"], text_color=self.colors["text"],
                                    hover_color=self.colors["border"])
        self.btn_info.grid(row=0, column=2, padx=5, sticky="ew")

    # --- LÓGICA (Mantenida pero adaptada) ---
    def connect_db(self):
        try:
            self.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
            self.after(0, lambda: self.btn_process.configure(state="normal"))
        except:
            self.after(0, lambda: self.btn_process.configure(text="Sin conexión a BD", fg_color=self.colors["danger"]))

    def select_file(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.selected_file_path = path
            self.lbl_filename.configure(text=f"✓ {os.path.basename(path)}")
            self.show_preview(path)

    def show_preview(self, path):
        try:
            doc = fitz.open(path)
            # Renderizar con mejor calidad (zoom=2)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)) 
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            # Calcular tamaño manteniendo relación de aspecto
            frame_h = self.frame_right.winfo_height() - 100
            if frame_h < 400: frame_h = 500
            
            ratio = frame_h / float(img.size[1])
            w_target = int(float(img.size[0]) * float(ratio))
            
            img = img.resize((w_target, frame_h), Image.Resampling.LANCZOS)
            self.preview_image_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(w_target, frame_h))
            self.lbl_preview.configure(image=self.preview_image_ref, text="")
        except Exception as e:
            self.lbl_preview.configure(text=f"Error visualizando: {e}")

    def start_processing(self):
        if not self.selected_file_path or not self.entry_dni.get().strip():
            messagebox.showwarning("Faltan datos", "Por favor cargue un PDF e ingrese el DNI.")
            return

        self.btn_process.configure(state="disabled", text="Generando...", fg_color=self.colors["border"])
        
        datos = {
            "nom": self.entry_nom.get().upper().strip(),
            "dni": self.entry_dni.get().strip(),
            "car": self.combo_carrera.get(),
            "fec": self.entry_fecha.get().strip()
        }
        threading.Thread(target=self.bg_process, args=(datos,), daemon=True).start()

    def bg_process(self, datos):
        try:
            # 1. Insertar en BD
            payload = {
                "nombre_completo": datos["nom"],
                "dni": datos["dni"],
                "modulo_curso": datos["car"],
                "carrera": "IISEP",
                "fecha_emision_texto": datos["fec"]
            }
            res = self.supabase.table("certificados").insert(payload).execute()
            uuid = res.data[0]['uuid_publico']

            # 2. QR y PDF
            qr = qrcode.QRCode(box_size=10, border=1)
            qr.add_data(f"{WEB_URL}?id={uuid}")
            qr.make(fit=True)
            img_mem = io.BytesIO()
            qr.make_image(fill_color="black", back_color="white").save(img_mem, format='PNG')

            doc = fitz.open(self.selected_file_path)
            page = doc[0]
            
            # Posicionamiento QR (Inferior Izquierda)
            rect = fitz.Rect(60, page.rect.height - 180, 170, page.rect.height - 70)
            page.insert_image(rect, stream=img_mem.getvalue())
            page.insert_text((60, page.rect.height - 60), "Escanee para validar", fontsize=7, color=(0,0,0))

            folder = os.path.dirname(self.selected_file_path)
            out_folder = os.path.join(folder, "CERTIFICADOS_LISTOS")
            if not os.path.exists(out_folder): os.makedirs(out_folder)
            
            self.generated_file_path = os.path.join(out_folder, f"CERT_{datos['dni']}.pdf")
            doc.save(self.generated_file_path)
            doc.close()

            self.after(0, self.on_success)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.actualizar_paleta()) # Restaurar colores de botón

    def on_success(self):
        self.actualizar_paleta() # Restaura color botón
        self.btn_process.configure(text="¡Certificado Generado!", state="normal")
        self.btn_open.configure(state="normal")
        self.show_preview(self.generated_file_path)
        messagebox.showinfo("Éxito", "Certificado generado correctamente.")

    def open_file(self):
        if self.generated_file_path: os.startfile(self.generated_file_path)

    def show_info(self):
        messagebox.showinfo("IISEP Digital", "Sistema de Validación de Certificados v2.1")

    def reset_form(self):
        self.entry_nom.delete(0, 'end')
        self.entry_dni.delete(0, 'end')
        self.selected_file_path = None
        self.lbl_preview.configure(image=None, text="\nVista Previa")
        self.btn_open.configure(state="disabled")

if __name__ == "__main__":
    app = SingleCertApp()
    app.mainloop()