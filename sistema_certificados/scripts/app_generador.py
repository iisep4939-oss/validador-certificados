import customtkinter as ctk
import os
import threading
import time
import io
import qrcode
import fitz  # PyMuPDF
from PIL import Image
from tkinter import filedialog, messagebox
import tkinter
from supabase import create_client

# --- CONFIGURACIÓN VISUAL ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# --- CREDENCIALES ---
URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s"
WEB_URL = "https://validador-certificados.vercel.app/"

class CertificadosApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema de Certificación Digital IISEP - Ingreso Manual")
        self.geometry("1150x750")
        self.minsize(1000, 650)
        
        self.files_queue = []
        self.stop_process_flag = False
        self.output_folder = ""
        
        # Datos temporales para el formulario
        self.temp_data = {"nombre": "", "dni": "", "carrera": ""}

        # Conexión BD
        self.supabase = None
        threading.Thread(target=self.conectar_bd, daemon=True).start()

        self.setup_ui()

    def conectar_bd(self):
        try:
            self.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
            print("Conexión BD OK")
        except Exception as e:
            print(f"Error BD: {e}")

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        # 1. HEADER
        self.header = ctk.CTkFrame(self, height=60, fg_color="#1a1a1a", corner_radius=0)
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(self.header, text="EMISIÓN DE CERTIFICADOS (MANUAL)", font=("Roboto", 20, "bold"), text_color="white").pack(side="left", padx=25)
        self.lbl_status = ctk.CTkLabel(self.header, text="Sistema Listo", font=("Roboto", 14), text_color="gray")
        self.lbl_status.pack(side="right", padx=25)

        # 2. PANEL IZQUIERDO (Archivos)
        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        self.left_panel.grid_rowconfigure(2, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)

        self.btn_box = ctk.CTkFrame(self.left_panel, fg_color="#2b2b2b")
        self.btn_box.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkButton(self.btn_box, text="📂 Seleccionar Carpeta", command=self.load_folder, fg_color="#34495e", height=40).pack(fill="x", padx=15, pady=10)
        ctk.CTkButton(self.btn_box, text="📄 Seleccionar Archivo", command=self.load_file, fg_color="#34495e", height=40).pack(fill="x", padx=15, pady=(0, 10))

        self.file_list_frame = ctk.CTkScrollableFrame(self.left_panel, label_text="Documentos en Cola")
        self.file_list_frame.grid(row=2, column=0, sticky="nsew")

        # 3. PANEL DERECHO (Preview)
        self.right_panel = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=10)
        self.right_panel.grid(row=1, column=1, sticky="nsew", padx=15, pady=15)
        self.preview_label = ctk.CTkLabel(self.right_panel, text="\n\n(Vista Previa)", font=("Roboto", 16), text_color="#555")
        self.preview_label.pack(expand=True, fill="both", padx=10, pady=10)

        # 4. FOOTER
        self.footer = ctk.CTkFrame(self, height=90, fg_color="#2b2b2b")
        self.footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        self.progress = ctk.CTkProgressBar(self.footer, height=18, progress_color="#27ae60", fg_color="#444")
        self.progress.pack(fill="x")
        self.progress.set(0)

        self.btn_start = ctk.CTkButton(self.footer, text="▶ COMENZAR CARGA", command=self.start_process, font=("Roboto", 15, "bold"), height=50, fg_color="#27ae60", hover_color="#2ecc71", state="disabled")
        self.btn_start.pack(side="left", padx=25, pady=20, fill="x", expand=True)

        self.btn_open = ctk.CTkButton(self.footer, text="📂 ABRIR RESULTADOS", command=self.open_output, font=("Roboto", 13, "bold"), height=50, fg_color="#e67e22", hover_color="#d35400", state="disabled")
        self.btn_open.pack(side="left", padx=(0, 25), pady=20)

        self.btn_stop = ctk.CTkButton(self.footer, text="⏹ DETENER", command=self.stop_processing, font=("Roboto", 15, "bold"), height=50, fg_color="#c0392b", state="disabled")
        self.btn_stop.pack(side="right", padx=25, pady=20)

    # --- UI HELPERS ---
    def update_file_list(self):
        for w in self.file_list_frame.winfo_children(): w.destroy()
        
        for f in self.files_queue[:40]: # Mostrar solo primeros 40
            ctk.CTkButton(self.file_list_frame, text=f"📄 {os.path.basename(f)}", anchor="w", fg_color="transparent", height=25, command=lambda p=f: self.trigger_preview(p)).pack(fill="x", pady=1)
        
        if self.files_queue:
            self.btn_start.configure(state="normal")
            self.trigger_preview(self.files_queue[0])
            self.lbl_status.configure(text=f"{len(self.files_queue)} archivos listos")

    def trigger_preview(self, path):
        threading.Thread(target=self._generate_preview, args=(path,), daemon=True).start()

    def _generate_preview(self, path):
        try:
            doc = fitz.open(path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            
            h_target = 500
            ratio = h_target / float(img.size[1])
            w_target = int(float(img.size[0]) * float(ratio))
            img = img.resize((w_target, h_target), Image.Resampling.NEAREST)
            
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(w_target, h_target))
            self.after(0, lambda: self.preview_label.configure(image=ctk_img, text=""))
        except: pass

    def load_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.files_queue = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(".pdf")]
            self.output_folder = os.path.join(path, "CERTIFICADOS_QR")
            if not os.path.exists(self.output_folder): os.makedirs(self.output_folder)
            self.update_file_list()

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.files_queue = [path]
            self.output_folder = os.path.join(os.path.dirname(path), "CERTIFICADOS_QR")
            if not os.path.exists(self.output_folder): os.makedirs(self.output_folder)
            self.update_file_list()

    def open_output(self):
        if os.path.exists(self.output_folder): os.startfile(self.output_folder)

    # --- PROCESO PRINCIPAL ---
    def start_process(self):
        if not self.supabase:
            messagebox.showerror("Error", "Sin conexión a Base de Datos")
            return
        
        self.stop_process_flag = False
        self.btn_start.configure(state="disabled")
        self.btn_box.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        
        threading.Thread(target=self.worker, daemon=True).start()

    def stop_processing(self):
        self.stop_process_flag = True
        self.lbl_status.configure(text="Deteniendo...", text_color="#e74c3c")

    def worker(self):
        total = len(self.files_queue)
        success_count = 0
        
        for i, filepath in enumerate(self.files_queue):
            if self.stop_process_flag: break
            
            filename = os.path.basename(filepath)
            self.after(0, lambda t=f"Procesando {i+1}/{total}: {filename}": self.lbl_status.configure(text=t, text_color="#3498db"))
            self.progress.set((i+1)/total)
            self.trigger_preview(filepath)
            
            # --- 1. PEDIR DATOS AL USUARIO ---
            # Bloqueamos el hilo hasta obtener respuesta
            datos = self.ask_user_data(filename)
            
            # Si el usuario canceló o cerró la ventana, saltamos o paramos
            if not datos: 
                continue 

            try:
                # --- 2. SUBIR A BD ---
                payload = {
                    "nombre_completo": datos['nombre'],
                    "dni": datos['dni'],
                    "modulo_curso": datos['carrera'], # Usamos el campo de carrera
                    "carrera": "IISEP", # Hardcodeamos institución o lo que quieras
                    "fecha_emision_texto": time.strftime("%d/%m/%Y")
                }
                res = self.supabase.table("certificados").insert(payload).execute()
                uuid = res.data[0]['uuid_publico']

                # --- 3. ESTAMPAR QR (FITZ) ---
                self.stamp_qr(filepath, uuid, filename)
                success_count += 1

            except Exception as e:
                print(f"Error: {e}")

        # Fin
        self.after(0, lambda: self.finish_ui(success_count))

    def finish_ui(self, count):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_box.configure(state="normal")
        self.btn_open.configure(state="normal")
        self.lbl_status.configure(text="Proceso Finalizado", text_color="#2ecc71")
        if not self.stop_process_flag:
            messagebox.showinfo("Listo", f"Se generaron {count} certificados.")

    # --- DIÁLOGO DE INGRESO MANUAL ---
    def ask_user_data(self, filename):
        result = None
        done_event = threading.Event()

        def submit():
            nonlocal result
            n = entry_nom.get().strip().upper()
            d = entry_dni.get().strip()
            c = entry_car.get().strip().upper()
            
            if not n or not d or not c:
                messagebox.showwarning("Faltan datos", "Por favor llena todos los campos.")
                return
            
            result = {"nombre": n, "dni": d, "carrera": c}
            win.destroy()
            done_event.set()

        def cancel():
            win.destroy()
            done_event.set() # Result se queda como None

        # Crear ventana en el hilo principal
        def open_window():
            global win, entry_nom, entry_dni, entry_car
            win = ctk.CTkToplevel(self)
            win.title("Ingreso de Datos")
            win.geometry("400x450")
            win.attributes("-topmost", True)
            win.protocol("WM_DELETE_WINDOW", cancel)
            
            # Centrar
            x = self.winfo_x() + (self.winfo_width()//2) - 200
            y = self.winfo_y() + (self.winfo_height()//2) - 225
            win.geometry(f"+{x}+{y}")

            ctk.CTkLabel(win, text=f"Archivo: {filename}", font=("Roboto", 14, "bold"), text_color="#f39c12").pack(pady=(20,10))
            
            ctk.CTkLabel(win, text="Nombre Completo:").pack(anchor="w", padx=40)
            entry_nom = ctk.CTkEntry(win, width=320)
            entry_nom.pack(pady=5)
            
            ctk.CTkLabel(win, text="DNI:").pack(anchor="w", padx=40)
            entry_dni = ctk.CTkEntry(win, width=320)
            entry_dni.pack(pady=5)
            
            ctk.CTkLabel(win, text="Carrera / Curso:").pack(anchor="w", padx=40)
            entry_car = ctk.CTkEntry(win, width=320)
            entry_car.pack(pady=5)

            ctk.CTkButton(win, text="GUARDAR Y GENERAR QR", command=submit, fg_color="#27ae60", height=40).pack(pady=30)
            ctk.CTkButton(win, text="Saltar este archivo", command=cancel, fg_color="transparent", border_width=1).pack()

        self.after(0, open_window)
        done_event.wait()
        return result

    # --- ESTAMPADO ULTRARRÁPIDO ---
    def stamp_qr(self, filepath, uuid, filename):
        # Generar QR en memoria
        qr = qrcode.QRCode(box_size=10, border=1)
        qr.add_data(f"{WEB_URL}?id={uuid}")
        qr.make(fit=True)
        img_byte_arr = io.BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        try:
            doc = fitz.open(filepath)
            page = doc[0]
            # Coordenadas (Izq, Arriba, Der, Abajo)
            rect = fitz.Rect(50, 50, 140, 140) 
            page.insert_image(rect, stream=img_bytes)
            page.insert_text((55, 45), "Escanee para validar", fontsize=7, color=(0,0,0))

            out_path = os.path.join(self.output_folder, filename)
            if os.path.exists(out_path):
                out_path = os.path.join(self.output_folder, f"{os.path.splitext(filename)[0]}_{int(time.time())}.pdf")
            
            doc.save(out_path)
            doc.close()
        except Exception as e:
            print(f"Error stamp: {e}")

if __name__ == "__main__":
    try:
        app = CertificadosApp()
        app.mainloop()
    except Exception as e:
        pass