import customtkinter as ctk
import os
import threading
import time
import io
import qrcode
import fitz  # PyMuPDF
from PIL import Image
from tkinter import filedialog, messagebox
from supabase import create_client

# --- 1. CONFIGURACIÓN DE DATOS ---
CARRERAS_IISEP = [
    "--- CARRERAS TÉCNICAS ---",
    "Computación",
    "Logística y Almacenes",
    "Gastronomía",
    "Instalaciones Electrotécnicas",
    "Cosmetología",
    "--- MÓDULOS Y TALLERES ---",
    "Ofimática",
    "Diseño Gráfico",
    "Ensamblaje de PC",
    "Barber Shop",
    "Inglés",
    "Uñas Acrílicas",
    "--- OTROS ---",
    "Otro (Especificar)"
]

# --- CREDENCIALES ---
URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s"
WEB_URL = "https://validador-certificados.vercel.app/"

class SingleCertApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración inicial de tema
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Generador IISEP v2.1 - Stable")
        self.geometry("1100x750")
        self.minsize(950, 650)
        
        # Variables de Estado
        self.selected_file_path = None
        self.generated_file_path = None
        self.supabase = None
        self.preview_image_ref = None 

        # Layout Principal (Grid 2x2)
        self.grid_columnconfigure(0, weight=1) # Panel Izquierdo
        self.grid_columnconfigure(1, weight=2) # Panel Derecho
        self.grid_rowconfigure(1, weight=1)    # El row 0 es el header

        self.setup_header()
        self.setup_left_panel()
        self.setup_right_panel()

        # Conexión silenciosa
        threading.Thread(target=self.connect_db, daemon=True).start()

    def connect_db(self):
        try:
            self.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
            self.btn_process.configure(state="normal", text="GENERAR CERTIFICADO")
        except Exception as e:
            print(f"Error conexión: {e}")
            self.btn_process.configure(text="Error de Conexión (Reiniciar)")

    # --- HEADER CON SWITCH DE TEMA (CORREGIDO) ---
    def setup_header(self):
        self.header = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=("gray90", "#1a1a1a"))
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        ctk.CTkLabel(self.header, text="SISTEMA DE CERTIFICACIÓN DIGITAL", font=("Roboto", 16, "bold")).pack(side="left", padx=20)
        
        # Switch simplificado (sin argumentos conflictivos)
        self.switch = ctk.CTkSwitch(self.header, text="Modo Oscuro", command=self.toggle_theme)
        self.switch.pack(side="right", padx=20)
        self.switch.select() # Activamos el switch por defecto (Modo Oscuro)

    def toggle_theme(self):
        # 1 es activado (Dark), 0 es desactivado (Light)
        if self.switch.get() == 1:
            ctk.set_appearance_mode("Dark")
            self.lbl_filename.configure(text_color="gray")
        else:
            ctk.set_appearance_mode("Light")
            self.lbl_filename.configure(text_color="black")

    # --- PANEL IZQUIERDO: FORMULARIO ---
    def setup_left_panel(self):
        self.frame_left = ctk.CTkFrame(self, corner_radius=0)
        self.frame_left.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        
        ctk.CTkLabel(self.frame_left, text="DATOS DEL ALUMNO", font=("Roboto", 20, "bold")).pack(pady=(30, 20))

        # Inputs
        self.create_label("Nombre Completo:")
        self.entry_nom = ctk.CTkEntry(self.frame_left, width=280, placeholder_text="Ej: MARIA LOPEZ")
        self.entry_nom.pack(pady=(0, 15))

        self.create_label("DNI:")
        self.entry_dni = ctk.CTkEntry(self.frame_left, width=280, placeholder_text="8 dígitos")
        self.entry_dni.pack(pady=(0, 15))

        self.create_label("Especialidad / Taller:")
        self.combo_carrera = ctk.CTkComboBox(self.frame_left, values=CARRERAS_IISEP, width=280)
        self.combo_carrera.set("Computación") 
        self.combo_carrera.pack(pady=(0, 15))

        self.create_label("Fecha de Emisión:")
        self.entry_fecha = ctk.CTkEntry(self.frame_left, width=280)
        self.entry_fecha.insert(0, time.strftime("%d/%m/%Y")) 
        self.entry_fecha.pack(pady=(0, 30))

        # Selección de Archivo
        ctk.CTkLabel(self.frame_left, text="DOCUMENTO BASE", font=("Roboto", 14, "bold")).pack(pady=(10, 5))
        
        self.lbl_filename = ctk.CTkLabel(self.frame_left, text="Ningún archivo seleccionado", text_color="gray", wraplength=280)
        self.lbl_filename.pack(pady=(0, 10))
        
        ctk.CTkButton(self.frame_left, text="📂 Cargar PDF", command=self.select_file, fg_color="#34495e").pack(pady=5)

        # Botón Principal
        self.btn_process = ctk.CTkButton(self.frame_left, text="⏳ Iniciando...", state="disabled", 
                                         command=self.start_processing, 
                                         fg_color="#27ae60", hover_color="#2ecc71", 
                                         height=50, font=("Roboto", 15, "bold"))
        self.btn_process.pack(side="bottom", pady=40, padx=20, fill="x")

    def create_label(self, text):
        ctk.CTkLabel(self.frame_left, text=text, anchor="w", font=("Roboto", 12)).pack(anchor="center", padx=45, fill="x")

    # --- PANEL DERECHO: VISTA PREVIA ---
    def setup_right_panel(self):
        self.frame_right = ctk.CTkFrame(self, fg_color=("gray85", "#1e1e1e"), corner_radius=0)
        self.frame_right.grid(row=1, column=1, sticky="nsew")
        
        self.frame_right.grid_rowconfigure(0, weight=1)
        self.frame_right.grid_columnconfigure(0, weight=1)

        # Label para la imagen
        self.lbl_preview = ctk.CTkLabel(self.frame_right, text="\n\nVista Previa del Documento", font=("Roboto", 16), text_color="gray")
        self.lbl_preview.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        # Botones de Acción Post-Proceso
        self.frame_actions = ctk.CTkFrame(self.frame_right, fg_color="transparent")
        self.frame_actions.grid(row=1, column=0, pady=20)

        self.btn_open = ctk.CTkButton(self.frame_actions, text="📂 ABRIR RESULTADO", state="disabled", command=self.open_file, fg_color="#e67e22", width=180, height=40)
        self.btn_open.pack(side="left", padx=10)
        
        self.btn_clean = ctk.CTkButton(self.frame_actions, text="🔄 NUEVO TRÁMITE", command=self.reset_form, fg_color="#c0392b", width=150, height=40)
        self.btn_clean.pack(side="left", padx=10)

    # --- LÓGICA DE ARCHIVOS Y PREVIEW ---
    def select_file(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.selected_file_path = path
            self.lbl_filename.configure(text=f"📄 {os.path.basename(path)}")
            self.show_preview(path)

    def show_preview(self, path):
        try:
            doc = fitz.open(path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(0.8, 0.8)) 
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            h_avail = self.frame_right.winfo_height() - 100
            if h_avail < 400: h_avail = 500
            
            ratio = h_avail / float(img.size[1])
            w_target = int(float(img.size[0]) * float(ratio))
            
            img = img.resize((w_target, h_avail), Image.Resampling.LANCZOS)
            
            self.preview_image_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(w_target, h_avail))
            self.lbl_preview.configure(image=self.preview_image_ref, text="") 
        except Exception as e:
            self.lbl_preview.configure(text=f"Error visualizando: {e}", image=None)

    # --- PROCESAMIENTO (HILO SECUNDARIO) ---
    def start_processing(self):
        if not self.selected_file_path:
            messagebox.showwarning("Atención", "Selecciona primero un archivo PDF.")
            return
        if not self.entry_dni.get().strip():
            messagebox.showwarning("Atención", "El DNI es obligatorio.")
            return

        self.btn_process.configure(state="disabled", text="⏳ Procesando...")
        
        datos = {
            "nom": self.entry_nom.get().upper().strip(),
            "dni": self.entry_dni.get().strip(),
            "car": self.combo_carrera.get(),
            "fec": self.entry_fecha.get().strip()
        }
        
        threading.Thread(target=self.bg_process, args=(datos,), daemon=True).start()

    def bg_process(self, datos):
        try:
            # 1. Base de Datos
            payload = {
                "nombre_completo": datos["nom"],
                "dni": datos["dni"],
                "modulo_curso": datos["car"],
                "carrera": "IISEP",
                "fecha_emision_texto": datos["fec"]
            }
            res = self.supabase.table("certificados").insert(payload).execute()
            uuid = res.data[0]['uuid_publico']

            # 2. Generar QR
            qr = qrcode.QRCode(box_size=10, border=1)
            qr.add_data(f"{WEB_URL}?id={uuid}")
            qr.make(fit=True)
            img_mem = io.BytesIO()
            qr.make_image(fill_color="black", back_color="white").save(img_mem, format='PNG')

            # 3. Estampar PDF
            doc = fitz.open(self.selected_file_path)
            page = doc[0]
            
            # --- CÁLCULO DE POSICIÓN INFERIOR ---
            page_h = page.rect.height
            qr_size = 110 
            margin_bottom = 70 
            margin_left = 60
            
            rect = fitz.Rect(
                margin_left, 
                page_h - qr_size - margin_bottom, 
                margin_left + qr_size, 
                page_h - margin_bottom
            )
            
            page.insert_image(rect, stream=img_mem.getvalue())
            text_y = page_h - margin_bottom + 10 
            page.insert_text((margin_left, text_y), "Escanee para validar", fontsize=7, color=(0,0,0))

            # Guardar
            folder = os.path.dirname(self.selected_file_path)
            out_folder = os.path.join(folder, "CERTIFICADOS_LISTOS")
            if not os.path.exists(out_folder): os.makedirs(out_folder)
            
            final_name = f"CERT_{datos['dni']}_{int(time.time())}.pdf"
            self.generated_file_path = os.path.join(out_folder, final_name)
            
            doc.save(self.generated_file_path)
            doc.close()

            self.after(0, self.on_success)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.btn_process.configure(state="normal", text="GENERAR CERTIFICADO"))

    def on_success(self):
        self.btn_process.configure(state="normal", text="GENERAR CERTIFICADO")
        self.btn_open.configure(state="normal")
        messagebox.showinfo("Éxito", "Certificado generado correctamente.")
        
        if self.generated_file_path:
            self.show_preview(self.generated_file_path)

    def open_file(self):
        if self.generated_file_path:
            os.startfile(self.generated_file_path)

    def reset_form(self):
        self.entry_nom.delete(0, 'end')
        self.entry_dni.delete(0, 'end')
        self.selected_file_path = None
        self.generated_file_path = None
        
        self.lbl_filename.configure(text="Ningún archivo seleccionado")
        self.btn_open.configure(state="disabled")
        
        self.preview_image_ref = None 
        self.lbl_preview.configure(image=None, text="\n\nVista Previa del Documento\n(Cargue un nuevo PDF)")
        self.lbl_preview.update()

if __name__ == "__main__":
    app = SingleCertApp()
    app.mainloop()