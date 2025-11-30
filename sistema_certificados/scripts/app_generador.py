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

# --- 1. FUNCIÓN DE RUTAS (SOLUCIÓN LOGO) ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

RUTA_ICONO = resource_path("logo_iisep.ico")
RUTA_LOGO_PNG = resource_path("logo_iisep.png")

# --- 2. PALETA "DUAL" (Magia de CustomTkinter) ---
# Formato: (Color_Modo_Claro, Color_Modo_Oscuro)
COLORS = {
    "bg_app":     ("#f1f5f9", "#0f172a"),  # Fondo general
    "panel":      ("#ffffff", "#1e293b"),  # Paneles
    "text":       ("#0f172a", "#f8fafc"),  # Texto Principal
    "text_sec":   ("#64748b", "#cbd5e1"),  # Texto Secundario (Alto contraste en oscuro)
    "input":      ("#e2e8f0", "#334155"),  # Cajas de texto
    "border":     ("#cbd5e1", "#475569"),  # Bordes
    "accent":     ("#0f5bb5", "#3b82f6"),  # Azul Principal
    "accent_hover": ("#0a458a", "#2563eb"),
    "success":    ("#10b981", "#059669"),  # Verde
    "danger":     ("#ef4444", "#dc2626"),  # Rojo
    "preview_bg": ("#cbd5e1", "#020617")   # Fondo del visor PDF
}

# --- DATOS IISEP ---
CARRERAS_IISEP = [
    "--- CARRERAS TÉCNICAS ---", "Computación", "Logística y Almacenes", "Gastronomía",
    "Instalaciones Electrotécnicas", "Cosmetología",
    "--- MÓDULOS Y TALLERES ---", "Ofimática", "Diseño Gráfico", "Ensamblaje de PC",
    "Barber Shop", "Inglés", "Uñas Acrílicas",
    "--- OTROS ---", "Otro (Especificar)"
]

URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s"
WEB_URL = "https://validador-certificados.vercel.app/"

class SingleCertApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración Visual
        ctk.set_appearance_mode("Dark") # Iniciar en oscuro por defecto
        ctk.set_default_color_theme("blue")

        self.title("Sistema de Certificación IISEP v2.1")
        self.geometry("1100x750")
        self.minsize(1000, 700)
        
        # Asignar colores una sola vez (la tupla maneja el cambio auto)
        self.configure(fg_color=COLORS["bg_app"])
        
        try:
            if os.path.exists(RUTA_ICONO):
                self.iconbitmap(RUTA_ICONO)
        except: pass

        # Estado
        self.selected_file_path = None
        self.generated_file_path = None
        self.supabase = None
        self.preview_image_ref = None 
        self.logo_image_ref = None 

        # Grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(1, weight=1)

        self.setup_header()
        self.setup_left_panel()
        self.setup_right_panel()
        
        threading.Thread(target=self.connect_db, daemon=True).start()

    def setup_header(self):
        # Header usa color de panel
        self.header = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color=COLORS["panel"])
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        inner = ctk.CTkFrame(self.header, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=30, pady=10)
        
        # Logo
        try:
            if os.path.exists(RUTA_LOGO_PNG):
                img_pil = Image.open(RUTA_LOGO_PNG)
                h = 50
                w = int((h / img_pil.size[1]) * img_pil.size[0])
                img_pil = img_pil.resize((w, h), Image.Resampling.LANCZOS)
                self.logo_image_ref = ImageTk.PhotoImage(img_pil)
                ctk.CTkLabel(inner, image=self.logo_image_ref, text="").pack(side="left", padx=(0, 20))
        except: pass

        # Título
        txt_frame = ctk.CTkFrame(inner, fg_color="transparent")
        txt_frame.pack(side="left", fill="y", pady=5)
        
        ctk.CTkLabel(txt_frame, text="SISTEMA DE CERTIFICACIÓN DIGITAL", 
                   font=("Roboto Medium", 20), text_color=COLORS["text"]).pack(anchor="w")
        
        ctk.CTkLabel(txt_frame, text="Validador Institucional IISEP", 
                    font=("Roboto", 12), text_color=COLORS["text_sec"]).pack(anchor="w")

        # Switch
        self.switch_var = ctk.StringVar(value="Modo Oscuro")
        self.switch = ctk.CTkSwitch(inner, text="Modo Oscuro", command=self.toggle_theme,
                                  variable=self.switch_var, onvalue="Modo Oscuro", offvalue="Modo Claro",
                                  progress_color=COLORS["accent"], text_color=COLORS["text"])
        self.switch.pack(side="right")
        self.switch.select()

    def setup_left_panel(self):
        self.frame_left = ctk.CTkFrame(self, corner_radius=15, fg_color=COLORS["panel"], 
                                     border_width=1, border_color=COLORS["border"])
        self.frame_left.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=20)
        
        scroll = ctk.CTkScrollableFrame(self.frame_left, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=15)

        # Helper para campos
        def add_field(label, widget_cls, **kwargs):
            ctk.CTkLabel(scroll, text=label, font=("Roboto Medium", 13), 
                       text_color=COLORS["text_sec"]).pack(anchor="w", pady=(10, 2))
            
            widget = widget_cls(scroll, height=45, font=("Roboto", 14), 
                              fg_color=COLORS["input"], border_color=COLORS["border"],
                              text_color=COLORS["text"], **kwargs)
            widget.pack(fill="x", pady=(0, 10))
            return widget

        # Formulario
        ctk.CTkLabel(scroll, text="DATOS DEL ESTUDIANTE", 
                   font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", pady=(10, 15))
        
        self.entry_nom = add_field("Nombre Completo", ctk.CTkEntry, placeholder_text="Ej: JUAN PEREZ", placeholder_text_color=COLORS["text_sec"])
        self.entry_dni = add_field("DNI", ctk.CTkEntry, placeholder_text="8 dígitos", placeholder_text_color=COLORS["text_sec"])
        
        ctk.CTkLabel(scroll, text="Especialidad / Taller", font=("Roboto Medium", 13), 
                       text_color=COLORS["text_sec"]).pack(anchor="w", pady=(10, 2))
        
        self.combo_carrera = ctk.CTkComboBox(scroll, values=CARRERAS_IISEP, height=45,
                                           font=("Roboto", 14), fg_color=COLORS["input"],
                                           dropdown_fg_color=COLORS["panel"],
                                           text_color=COLORS["text"], dropdown_text_color=COLORS["text"],
                                           border_color=COLORS["border"],
                                           button_color=COLORS["border"], button_hover_color=COLORS["accent"])
        self.combo_carrera.set("Computación")
        self.combo_carrera.pack(fill="x", pady=(0, 10))

        self.entry_fecha = add_field("Fecha de Emisión", ctk.CTkEntry)
        self.entry_fecha.insert(0, time.strftime("%d/%m/%Y"))

        # Sección Archivo
        ctk.CTkLabel(scroll, text="DOCUMENTO BASE", 
                   font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", pady=(25, 10))
        
        self.lbl_filename = ctk.CTkLabel(scroll, text="Seleccione el PDF de la constancia", 
                                       text_color=COLORS["text_sec"], font=("Roboto", 12))
        self.lbl_filename.pack(anchor="w")

        self.btn_load = ctk.CTkButton(scroll, text="📂 Seleccionar PDF", height=45, 
                                    font=("Roboto Medium", 13), command=self.select_file,
                                    fg_color=COLORS["input"], text_color=COLORS["text"],
                                    hover_color=COLORS["border"], border_width=1, border_color=COLORS["border"])
        self.btn_load.pack(fill="x", pady=10)

        self.btn_process = ctk.CTkButton(self.frame_left, text="GENERAR CERTIFICADO", height=55,
                                       font=("Roboto", 15, "bold"), command=self.start_processing,
                                       state="disabled", fg_color=COLORS["accent"], 
                                       hover_color=COLORS["accent_hover"], corner_radius=12)
        self.btn_process.pack(side="bottom", fill="x", padx=20, pady=20)

    def setup_right_panel(self):
        self.frame_right = ctk.CTkFrame(self, corner_radius=15, fg_color=COLORS["preview_bg"],
                                      border_width=1, border_color=COLORS["border"])
        self.frame_right.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=20)
        self.frame_right.grid_rowconfigure(0, weight=1)
        self.frame_right.grid_columnconfigure(0, weight=1)

        self.lbl_preview = ctk.CTkLabel(self.frame_right, text="\nVista Previa del Documento",
                                      font=("Roboto", 16), text_color=COLORS["text_sec"])
        self.lbl_preview.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        # Acciones
        actions = ctk.CTkFrame(self.frame_right, fg_color="transparent", height=60)
        actions.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        actions.grid_columnconfigure((0,1,2), weight=1)

        self.btn_open = ctk.CTkButton(actions, text="Abrir PDF", command=self.open_file, state="disabled",
                                    height=45, fg_color=COLORS["success"], font=("Roboto", 13, "bold"))
        self.btn_open.grid(row=0, column=0, padx=5, sticky="ew")

        self.btn_clean = ctk.CTkButton(actions, text="Limpiar", command=self.reset_form,
                                     height=45, fg_color=COLORS["danger"], font=("Roboto", 13, "bold"))
        self.btn_clean.grid(row=0, column=1, padx=5, sticky="ew")

        self.btn_info = ctk.CTkButton(actions, text="Info", command=self.show_info,
                                    height=45, fg_color=COLORS["input"], text_color=COLORS["text"],
                                    hover_color=COLORS["border"])
        self.btn_info.grid(row=0, column=2, padx=5, sticky="ew")

    # --- LÓGICA DEL CAMBIO DE TEMA SIMPLIFICADA ---
    def toggle_theme(self):
        # SOLO cambiamos el modo global. CustomTkinter hace el resto automáticamente
        # porque ya definimos los colores como tuplas (claro, oscuro).
        if self.switch.get() == "Modo Oscuro":
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")
        
        # Pequeño truco para forzar el repintado inmediato del Canvas de la imagen si existe
        if self.preview_image_ref:
            self.lbl_preview.configure(image=self.preview_image_ref)

    # --- RESTO DE FUNCIONES (LÓGICA) ---
    def connect_db(self):
        try:
            self.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
            self.after(0, lambda: self.btn_process.configure(state="normal"))
        except:
            self.after(0, lambda: self.btn_process.configure(text="Sin conexión a BD", fg_color=COLORS["danger"]))

    def select_file(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.selected_file_path = path
            self.lbl_filename.configure(text=f"✓ {os.path.basename(path)}")
            self.show_preview(path)

    def show_preview(self, path):
        try:
            doc = fitz.open(path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)) 
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            frame_h = self.frame_right.winfo_height() - 100
            if frame_h < 400: frame_h = 500
            
            ratio = frame_h / float(img.size[1])
            w_target = int(float(img.size[0]) * float(ratio))
            
            img = img.resize((w_target, frame_h), Image.Resampling.LANCZOS)
            
            # NOTA: Creamos una CTkImage. Al pasar la misma img para light y dark,
            # la imagen se ve igual en ambos modos, pero el fondo cambia.
            self.preview_image_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(w_target, frame_h))
            self.lbl_preview.configure(image=self.preview_image_ref, text="")
        except Exception as e:
            self.lbl_preview.configure(text=f"Error visualizando: {e}")

    def start_processing(self):
        if not self.selected_file_path or not self.entry_dni.get().strip():
            messagebox.showwarning("Faltan datos", "Por favor cargue un PDF e ingrese el DNI.")
            return

        self.btn_process.configure(state="disabled", text="Generando...", fg_color=COLORS["border"])
        
        datos = {
            "nom": self.entry_nom.get().upper().strip(),
            "dni": self.entry_dni.get().strip(),
            "car": self.combo_carrera.get(),
            "fec": self.entry_fecha.get().strip()
        }
        threading.Thread(target=self.bg_process, args=(datos,), daemon=True).start()

    def bg_process(self, datos):
        try:
            payload = {
                "nombre_completo": datos["nom"],
                "dni": datos["dni"],
                "modulo_curso": datos["car"],
                "carrera": "IISEP",
                "fecha_emision_texto": datos["fec"]
            }
            res = self.supabase.table("certificados").insert(payload).execute()
            uuid = res.data[0]['uuid_publico']

            qr = qrcode.QRCode(box_size=10, border=1)
            qr.add_data(f"{WEB_URL}?id={uuid}")
            qr.make(fit=True)
            img_mem = io.BytesIO()
            qr.make_image(fill_color="black", back_color="white").save(img_mem, format='PNG')

            doc = fitz.open(self.selected_file_path)
            page = doc[0]
            
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
            # Restaurar botón si falla
            self.after(0, lambda: self.btn_process.configure(text="GENERAR CERTIFICADO", state="normal", fg_color=COLORS["accent"]))

    def on_success(self):
        self.btn_process.configure(text="¡Certificado Generado!", state="normal", fg_color=COLORS["accent"])
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