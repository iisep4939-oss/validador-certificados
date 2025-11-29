import customtkinter as ctk
import os
import threading
import time
import io
import re
import qrcode
import pdfplumber
import subprocess
from tkinter import filedialog, messagebox
from supabase import create_client
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURACIÓN VISUAL ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# --- TUS CREDENCIALES ---
URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s"
WEB_URL = "https://validador-certificados-tau.vercel.app"

class CertificadosApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Ventana Principal
        self.title("Generador de Certificados IISEP v3.1")
        self.geometry("1000x750")
        self.minsize(900, 650)
        
        # Variables
        self.input_path = ""
        self.output_folder = ""
        self.is_single_file = False
        self.stop_process_flag = False
        
        # Conexión BD
        try:
            self.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
        except Exception as e:
            messagebox.showerror("Error Crítico", f"No hay conexión con la base de datos:\n{e}")

        self.setup_ui()

    def setup_ui(self):
        # Grid Principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Header
        self.grid_rowconfigure(1, weight=0) # Panel de control
        self.grid_rowconfigure(2, weight=1) # Log / Lista
        self.grid_rowconfigure(3, weight=0) # Acciones

        # 1. HEADER MODERNO
        self.frame_header = ctk.CTkFrame(self, height=100, corner_radius=0, fg_color="#1a1a1a")
        self.frame_header.grid(row=0, column=0, sticky="ew")
        self.frame_header.grid_columnconfigure(0, weight=1)
        
        self.lbl_title = ctk.CTkLabel(self.frame_header, text="GENERADOR DE CERTIFICADOS", font=("Roboto", 24, "bold"), text_color="white")
        self.lbl_title.grid(row=0, column=0, sticky="w", padx=30, pady=(15, 0))
        
        self.lbl_subtitle = ctk.CTkLabel(self.frame_header, text="Sistema de Estampado de Códigos QR", font=("Roboto", 14), text_color="#b0b0b0")
        self.lbl_subtitle.grid(row=1, column=0, sticky="w", padx=30, pady=(0, 15))

        self.lbl_status_top = ctk.CTkLabel(self.frame_header, text="● Sistema listo", text_color="#2ecc71", font=("Roboto", 12, "bold"))
        self.lbl_status_top.grid(row=0, column=1, rowspan=2, sticky="e", padx=30, pady=20)

        # 2. PANEL DE CONTROL
        self.frame_control = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_control.grid(row=1, column=0, padx=20, pady=15, sticky="ew")
        self.frame_control.grid_columnconfigure(1, weight=1)

        # Panel de selección
        self.frame_selection = ctk.CTkFrame(self.frame_control, fg_color="#2a2a2a")
        self.frame_selection.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        self.frame_selection.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.frame_selection, text="SELECCIÓN DE ARCHIVOS", font=("Roboto", 14, "bold"), text_color="#e0e0e0").grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))
        
        self.btn_frame = ctk.CTkFrame(self.frame_selection, fg_color="transparent")
        self.btn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))
        self.btn_frame.grid_columnconfigure(0, weight=1)
        self.btn_frame.grid_columnconfigure(1, weight=1)
        self.btn_frame.grid_columnconfigure(2, weight=3)
        
        self.btn_folder = ctk.CTkButton(self.btn_frame, text="📂 SELECCIONAR CARPETA", command=self.select_folder, height=40, fg_color="#34495e", hover_color="#2c3e50", font=("Roboto", 12, "bold"))
        self.btn_folder.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        self.btn_file = ctk.CTkButton(self.btn_frame, text="📄 SELECCIONAR ARCHIVO", command=self.select_file, height=40, fg_color="#34495e", hover_color="#2c3e50", font=("Roboto", 12, "bold"))
        self.btn_file.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        self.lbl_path = ctk.CTkLabel(self.btn_frame, text="Ninguna ruta seleccionada", text_color="#95a5a6", anchor="w", font=("Roboto", 11))
        self.lbl_path.grid(row=0, column=2, sticky="ew", padx=(10, 0))

        # Panel de información
        self.frame_info = ctk.CTkFrame(self.frame_control, fg_color="#2a2a2a")
        self.frame_info.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        self.frame_info.grid_columnconfigure(0, weight=1)
        self.frame_info.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.frame_info, text="INFORMACIÓN DEL SISTEMA", font=("Roboto", 14, "bold"), text_color="#e0e0e0").grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))
        
        self.stats_frame = ctk.CTkFrame(self.frame_info, fg_color="transparent")
        self.stats_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        
        self.lbl_files = ctk.CTkLabel(self.stats_frame, text="Archivos listos: 0", text_color="#3498db", font=("Roboto", 12))
        self.lbl_files.grid(row=0, column=0, sticky="w", padx=(0, 20))
        
        self.lbl_status = ctk.CTkLabel(self.stats_frame, text="Estado: Esperando", text_color="#f39c12", font=("Roboto", 12))
        self.lbl_status.grid(row=0, column=1, sticky="w")

        # 3. ZONA DE REGISTRO
        self.frame_console = ctk.CTkFrame(self, corner_radius=10)
        self.frame_console.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.frame_console.grid_columnconfigure(0, weight=1)
        self.frame_console.grid_rowconfigure(0, weight=1)
        
        console_header = ctk.CTkFrame(self.frame_console, fg_color="#2a2a2a", height=40)
        console_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        console_header.grid_propagate(False)
        
        ctk.CTkLabel(console_header, text="REGISTRO DE ACTIVIDAD", font=("Roboto", 14, "bold"), text_color="#e0e0e0").grid(row=0, column=0, sticky="w", padx=15, pady=10)
        
        self.textbox = ctk.CTkTextbox(self.frame_console, font=("Consolas", 12), fg_color="#1e1e1e", text_color="#ecf0f1")
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.textbox.insert("0.0", ">> Bienvenido al sistema v3.1.\n>> Seleccione una carpeta o archivo para comenzar.\n\n")
        self.textbox.configure(state="disabled")

        # 4. BARRA DE ACCIONES
        self.frame_actions = ctk.CTkFrame(self, height=120, fg_color="#2d2d2d")
        self.frame_actions.grid(row=3, column=0, sticky="ew")
        self.frame_actions.grid_columnconfigure(0, weight=1)
        self.frame_actions.grid_propagate(False)

        self.inner_actions = ctk.CTkFrame(self.frame_actions, fg_color="transparent")
        self.inner_actions.grid(row=0, column=0, sticky="nsew", padx=20, pady=15)
        self.inner_actions.grid_columnconfigure(0, weight=1)
        self.inner_actions.grid_columnconfigure(1, weight=1)
        self.inner_actions.grid_columnconfigure(2, weight=1)

        self.progress = ctk.CTkProgressBar(self.inner_actions, height=15, progress_color="#27ae60", fg_color="#34495e")
        self.progress.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        self.progress.set(0)
        
        self.lbl_progress = ctk.CTkLabel(self.inner_actions, text="0%", text_color="#7f8c8d", font=("Roboto", 12))
        self.lbl_progress.grid(row=0, column=2, sticky="e", pady=(0, 15))

        self.btn_start = ctk.CTkButton(self.inner_actions, text="▶ INICIAR PROCESO", command=self.start_thread, font=("Roboto", 14, "bold"), height=45, fg_color="#27ae60", hover_color="#2ecc71")
        self.btn_start.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        self.btn_stop = ctk.CTkButton(self.inner_actions, text="⏹ DETENER", command=self.stop_process, font=("Roboto", 14, "bold"), height=45, fg_color="#c0392b", hover_color="#e74c3c", state="disabled")
        self.btn_stop.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        
        self.btn_open_res = ctk.CTkButton(self.inner_actions, text="↗ ABRIR CARPETA", command=self.open_output_folder, font=("Roboto", 14, "bold"), height=45, fg_color="#f39c12", hover_color="#e67e22", state="disabled")
        self.btn_open_res.grid(row=1, column=2, sticky="ew")

    # --- FUNCIONES ---
    def log(self, msg, color="white"):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", f">> {msg}\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def select_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.input_path = path
            self.is_single_file = False
            self.lbl_path.configure(text=f"CARPETA: ...{path[-40:]}")
            self.log(f"Origen seleccionado: {path}")
            self.output_folder = os.path.join(path, "CERTIFICADOS_QR")
            if os.path.exists(self.output_folder):
                self.btn_open_res.configure(state="normal")
            
            files = [f for f in os.listdir(path) if f.lower().endswith('.pdf')]
            self.lbl_files.configure(text=f"Archivos listos: {len(files)}")
            self.lbl_status.configure(text="Estado: Listo para procesar", text_color="#2ecc71")

    def select_file(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.input_path = path
            self.is_single_file = True
            self.lbl_path.configure(text=f"ARCHIVO: {os.path.basename(path)}")
            self.log(f"Archivo único: {os.path.basename(path)}")
            self.output_folder = os.path.join(os.path.dirname(path), "CERTIFICADOS_QR")
            
            self.lbl_files.configure(text="Archivos listos: 1")
            self.lbl_status.configure(text="Estado: Listo para procesar", text_color="#2ecc71")

    def open_output_folder(self):
        if self.output_folder and os.path.exists(self.output_folder):
            os.startfile(self.output_folder)
        else:
            messagebox.showinfo("Información", "La carpeta de resultados aún no ha sido creada.")

    def stop_process(self):
        self.stop_process_flag = True
        self.log("⚠️ Solicitando detención...")

    def start_thread(self):
        if not self.input_path:
            messagebox.showwarning("Error", "Selecciona una carpeta o archivo primero.")
            return
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        self.stop_process_flag = False
        self.btn_start.configure(state="disabled")
        self.btn_folder.configure(state="disabled")
        self.btn_file.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_open_res.configure(state="disabled")
        self.lbl_status_top.configure(text="● Procesando...", text_color="#f39c12")
        self.lbl_status.configure(text="Estado: Procesando...", text_color="#f39c12")
        
        files_to_proc = []
        if self.is_single_file:
            files_to_proc = [self.input_path]
            base_dir = os.path.dirname(self.input_path)
        else:
            base_dir = self.input_path
            files_to_proc = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.lower().endswith('.pdf')]

        self.output_folder = os.path.join(base_dir, "CERTIFICADOS_QR")
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)
            self.log(f"Carpeta creada: {self.output_folder}")

        total = len(files_to_proc)
        if total == 0:
            self.log("❌ No se encontraron PDFs.")
            self.reset_ui()
            return

        success_count = 0
        
        for i, filepath in enumerate(files_to_proc):
            if self.stop_process_flag:
                break
                
            filename = os.path.basename(filepath)
            try:
                self.process_one_pdf(filepath, filename)
                success_count += 1
            except Exception as e:
                self.log(f"❌ Error en {filename}: {e}")

            progress_value = (i + 1) / total
            self.progress.set(progress_value)
            self.lbl_progress.configure(text=f"{int(progress_value * 100)}%")

        self.reset_ui()
        self.lbl_status_top.configure(text="● Finalizado", text_color="#2ecc71")
        self.lbl_status.configure(text="Estado: Finalizado", text_color="#2ecc71")
        self.btn_open_res.configure(state="normal")
        
        msg = "Proceso completado." if not self.stop_process_flag else "Proceso detenido."
        messagebox.showinfo("Reporte", f"{msg}\nProcesados: {success_count} de {total}")

    def process_one_pdf(self, filepath, filename):
        # A. Leer PDF (extracción de texto)
        nombre = "SIN NOMBRE"
        dni = "---"
        
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""
            match = re.search(r'DNI N°\s*(\d{8})', text)
            if match: dni = match.group(1)
            
            lines = text.split('\n')
            for idx, line in enumerate(lines):
                if "otorga a" in line.lower() or "conferido a" in line.lower():
                    if idx + 1 < len(lines):
                        nombre = lines[idx+1].strip()
                    break
        
        self.log(f"Procesando: {nombre}...")

        # B. Supabase
        res = self.supabase.table("certificados").insert({
            "nombre_completo": nombre,
            "dni": dni,
            "modulo_curso": "Validación QR",
            "carrera": "IISEP",
            "fecha_emision_texto": time.strftime("%d/%m/%Y")
        }).execute()
        uuid_code = res.data[0]['uuid_publico']

        # C. Generar QR
        qr_img = qrcode.make(f"{WEB_URL}?id={uuid_code}")
        qr_temp = f"temp_{int(time.time())}.png"
        qr_img.save(qr_temp)

        # D. Estampar (CORRECCIÓN CRÍTICA AQUÍ)
        try:
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=A4)
            # Ajusta posición (X, Y)
            can.drawImage(qr_temp, 50, 50, width=90, height=90) 
            can.setFont("Helvetica", 8)
            can.drawString(50, 40, "Escanear para validar")
            can.save()
            
            packet.seek(0)
            new_pdf = PdfReader(packet)

            # --- LA CLAVE DEL ARREGLO: 'with open' ---
            # Abrimos el archivo PDF original en modo binario
            # y lo mantenemos abierto durante el merge
            with open(filepath, "rb") as f_in:
                existing_pdf = PdfReader(f_in)
                output = PdfWriter()
                
                # Obtenemos la página y la fusionamos
                page = existing_pdf.pages[0]
                page.merge_page(new_pdf.pages[0])
                output.add_page(page)
                
                # Guardamos el resultado
                out_path = os.path.join(self.output_folder, filename)
                with open(out_path, "wb") as f_out:
                    output.write(f_out)
                    
        finally:
            if os.path.exists(qr_temp):
                os.remove(qr_temp)

    def reset_ui(self):
        self.btn_start.configure(state="normal")
        self.btn_folder.configure(state="normal")
        self.btn_file.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.progress.set(0)
        self.lbl_progress.configure(text="0%")

if __name__ == "__main__":
    app = CertificadosApp()
    app.mainloop()