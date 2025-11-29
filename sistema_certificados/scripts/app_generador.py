import customtkinter as ctk
import os
import threading
import time
import io
import re
import qrcode
import pdfplumber
from tkinter import filedialog, messagebox
from supabase import create_client
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURACIÓN DE TEMA ---
ctk.set_appearance_mode("Dark")  # "System", "Dark", "Light"
ctk.set_default_color_theme("dark-blue")  # "blue", "green", "dark-blue"

# --- TUS CREDENCIALES ---
URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s" # <--- PEGA TU KEY AQUÍ
WEB_URL = "https://validador-certificados-tau.vercel.app"

class CertificadosApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración Ventana Principal
        self.title("Sistema de Certificación Digital IISEP")
        self.geometry("800x600")
        self.minsize(800, 600)
        
        # Variables de control
        self.input_path = ""
        self.output_folder = ""
        self.is_single_file = False
        self.stop_process_flag = False
        self.files_to_process = []
        
        # Cliente Supabase
        try:
            self.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"No se pudo conectar a Supabase:\n{e}")

        self.setup_ui()

    def setup_ui(self):
        # --- LAYOUT PRINCIPAL (Grid 2 columnas) ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Header
        self.grid_rowconfigure(1, weight=0) # Selección
        self.grid_rowconfigure(2, weight=1) # Consola
        self.grid_rowconfigure(3, weight=0) # Controles

        # 1. HEADER
        self.frame_header = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        self.lbl_title = ctk.CTkLabel(self.frame_header, text="EMISIÓN DE CERTIFICADOS QR", font=("Roboto Medium", 24))
        self.lbl_title.pack(side="left")
        
        self.lbl_status = ctk.CTkLabel(self.frame_header, text="● Sistema Listo", text_color="#2ecc71", font=("Roboto", 14))
        self.lbl_status.pack(side="right")

        # 2. ZONA DE SELECCIÓN (Card Style)
        self.frame_select = ctk.CTkFrame(self)
        self.frame_select.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.lbl_instruct = ctk.CTkLabel(self.frame_select, text="Seleccione el origen de los documentos (PDF):", text_color="gray")
        self.lbl_instruct.pack(pady=(15, 5), padx=15, anchor="w")

        self.btn_folder = ctk.CTkButton(self.frame_select, text="📁  Seleccionar Carpeta Completa", command=self.select_folder, height=35, fg_color="#34495e")
        self.btn_folder.pack(pady=5, padx=20, fill="x")

        self.btn_file = ctk.CTkButton(self.frame_select, text="Pg  Seleccionar Un Solo Archivo", command=self.select_file, height=35, fg_color="#34495e")
        self.btn_file.pack(pady=(5, 15), padx=20, fill="x")
        
        self.lbl_path_display = ctk.CTkLabel(self.frame_select, text="Ningún archivo seleccionado", font=("Consolas", 12), text_color="#bdc3c7")
        self.lbl_path_display.pack(pady=(0, 15))

        # 3. CONSOLA DE LOGS
        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 11))
        self.textbox.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.textbox.insert("0.0", "--- Registro de Actividad ---\n")
        self.textbox.configure(state="disabled")

        # 4. ZONA DE CONTROL Y PROGRESO
        self.frame_controls = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_controls.grid(row=3, column=0, padx=20, pady=20, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(self.frame_controls, height=15)
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0)

        # Botones de Acción (Grid interno para ponerlos lado a lado)
        self.frame_btns = ctk.CTkFrame(self.frame_controls, fg_color="transparent")
        self.frame_btns.pack(fill="x")

        self.btn_start = ctk.CTkButton(self.frame_btns, text="▶  INICIAR PROCESO", command=self.start_thread, height=45, font=("Roboto", 14, "bold"), fg_color="#27ae60", hover_color="#2ecc71")
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_stop = ctk.CTkButton(self.frame_btns, text="⏹  CANCELAR", command=self.stop_process, height=45, font=("Roboto", 14, "bold"), fg_color="#c0392b", hover_color="#e74c3c", state="disabled")
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(10, 0))

    # --- LÓGICA DE INTERFAZ ---
    def log(self, msg, type="info"):
        self.textbox.configure(state="normal")
        prefix = ">> "
        if type == "error": prefix = "❌ "
        if type == "success": prefix = "✅ "
        if type == "warning": prefix = "⚠️ "
        
        self.textbox.insert("end", f"{prefix}{msg}\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def select_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.input_path = path
            self.is_single_file = False
            self.lbl_path_display.configure(text=f"CARPETA: {path}")
            self.log(f"Carpeta seleccionada: {path}")

    def select_file(self):
        path = filedialog.askopenfilename(filetypes=[("Archivos PDF", "*.pdf")])
        if path:
            self.input_path = path
            self.is_single_file = True
            self.lbl_path_display.configure(text=f"ARCHIVO: {os.path.basename(path)}")
            self.log(f"Archivo seleccionado: {os.path.basename(path)}")

    def stop_process(self):
        if messagebox.askyesno("Confirmar", "¿Desea detener el proceso actual?"):
            self.stop_process_flag = True
            self.btn_stop.configure(state="disabled")
            self.log("Solicitando detención...", "warning")

    def start_thread(self):
        if not self.input_path:
            messagebox.showwarning("Atención", "Por favor seleccione una carpeta o archivo primero.")
            return
        
        self.stop_process_flag = False
        threading.Thread(target=self.worker_process, daemon=True).start()

    # --- LÓGICA DE FONDO (WORKER) ---
    def worker_process(self):
        # 1. Preparar UI
        self.btn_start.configure(state="disabled")
        self.btn_folder.configure(state="disabled")
        self.btn_file.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="● Procesando...", text_color="#f39c12")
        self.progress_bar.set(0)

        # 2. Identificar Archivos
        files = []
        if self.is_single_file:
            files = [self.input_path]
            # Carpeta de salida es la misma donde está el archivo
            self.output_folder = os.path.join(os.path.dirname(self.input_path), "CERTIFICADOS_QR")
        else:
            files = [os.path.join(self.input_path, f) for f in os.listdir(self.input_path) if f.lower().endswith('.pdf')]
            self.output_folder = os.path.join(self.input_path, "CERTIFICADOS_QR")

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        total_files = len(files)
        if total_files == 0:
            self.log("No se encontraron PDFs válidos.", "warning")
            self.reset_ui()
            return

        self.log(f"Iniciando lote de {total_files} documentos.", "info")

        # 3. Bucle de Procesamiento
        errors = 0
        success = 0

        for i, filepath in enumerate(files):
            # --- CHECK STOP ---
            if self.stop_process_flag:
                self.log("Proceso detenido por el usuario.", "warning")
                break
            
            filename = os.path.basename(filepath)
            
            try:
                self.procesar_documento(filepath, filename)
                success += 1
            except Exception as e:
                self.log(f"Error en {filename}: {str(e)}", "error")
                errors += 1
            
            # Actualizar progreso
            progreso = (i + 1) / total_files
            self.progress_bar.set(progreso)
            self.update_idletasks() # Forzar actualización visual

        # 4. Finalización
        self.log(f"FIN. Éxitos: {success} | Errores: {errors}", "info")
        if self.stop_process_flag:
            self.lbl_status.configure(text="● Detenido", text_color="#c0392b")
            messagebox.showinfo("Detenido", "El proceso fue cancelado manualmente.")
        else:
            self.lbl_status.configure(text="● Finalizado", text_color="#2ecc71")
            messagebox.showinfo("Completado", f"Se procesaron {success} archivos correctamente.\nRevisa la carpeta 'CERTIFICADOS_QR'.")
        
        self.reset_ui()

    def reset_ui(self):
        self.btn_start.configure(state="normal")
        self.btn_folder.configure(state="normal")
        self.btn_file.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def procesar_documento(self, filepath, filename):
        # A. Extraer Texto
        nombre = "NO DETECTADO"
        dni = "NO DETECTADO"
        
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""
            
            # Regex DNI
            match_dni = re.search(r'DNI N°\s*(\d{8})', text)
            if match_dni: dni = match_dni.group(1)
            
            # Lógica Nombre (Ajustar según tu PDF)
            lines = text.split('\n')
            for idx, line in enumerate(lines):
                if "otorga a" in line.lower() or "conferido a" in line.lower():
                    if idx + 1 < len(lines):
                        nombre = lines[idx+1].strip()
                    break

        self.log(f"Procesando: {nombre} ({dni})")

        # B. Base de Datos
        data = {
            "nombre_completo": nombre,
            "dni": dni,
            "modulo_curso": "Validación Auto", # Puedes mejorar esto con más Regex
            "carrera": "IISEP",
            "fecha_emision_texto": time.strftime("%d/%m/%Y")
        }
        res = self.supabase.table("certificados").insert(data).execute()
        uuid_val = res.data[0]['uuid_publico']

        # C. Generar QR
        url = f"{WEB_URL}?id={uuid_val}"
        qr_img = qrcode.make(url)
        qr_temp = f"temp_qr_{int(time.time())}.png"
        qr_img.save(qr_temp)

        # D. Estampar
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        
        # --- COORDENADAS DEL QR ---
        # Ajusta esto según dónde quieras el QR en el papel
        can.drawImage(qr_temp, 50, 50, width=90, height=90) 
        can.setFont("Helvetica", 8)
        can.drawString(50, 40, "Verificar autenticidad")
        can.save()
        
        packet.seek(0)
        new_pdf = PdfReader(packet)
        existing_pdf = PdfReader(open(filepath, "rb"))
        output = PdfWriter()
        
        page = existing_pdf.pages[0]
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)

        output_path = os.path.join(self.output_folder, filename)
        
        # Evitar error de archivo bloqueado usando nombre único si es necesario
        if os.path.exists(output_path):
            base, ext = os.path.splitext(filename)
            output_path = os.path.join(self.output_folder, f"{base}_QR{ext}")

        with open(output_path, "wb") as f:
            output.write(f)
            
        if os.path.exists(qr_temp): os.remove(qr_temp)
        self.log(f"--> Guardado: {os.path.basename(output_path)}", "success")

if __name__ == "__main__":
    app = CertificadosApp()
    app.mainloop()