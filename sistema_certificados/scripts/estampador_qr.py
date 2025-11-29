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

# --- CONFIGURACIÓN VISUAL ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# --- CREDENCIALES (¡OJO! No compartas estas llaves en foros públicos) ---
URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s"
WEB_URL = "https://validador-certificados.vercel.app/"

class CertificadosApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema de Certificación IISEP - v8.1 (Fixed Threading)")
        self.geometry("1200x800")
        self.minsize(1000, 650)
        
        # Variables de estado
        self.files_queue = []
        self.current_index = 0
        self.stop_process_flag = False
        self.output_folder = ""
        self.success_count = 0
        self.supabase = None
        self.current_preview_image = None # Referencia para evitar Garbage Collection

        self.setup_ui()
        self.setup_overlay()
        
        # Inicializar conexión en segundo plano
        self.lbl_status.configure(text="Conectando a base de datos...", text_color="yellow")
        threading.Thread(target=self.connect_db_thread, daemon=True).start()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        # 1. HEADER
        self.header = ctk.CTkFrame(self, height=60, fg_color="#1a1a1a", corner_radius=0)
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(self.header, text="EMISIÓN DE CERTIFICADOS", font=("Roboto", 22, "bold"), text_color="white").pack(side="left", padx=25)
        self.lbl_status = ctk.CTkLabel(self.header, text="Iniciando...", font=("Roboto", 14), text_color="gray")
        self.lbl_status.pack(side="right", padx=25)

        # 2. PANEL IZQUIERDO
        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        self.left_panel.grid_rowconfigure(2, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)

        self.btn_box = ctk.CTkFrame(self.left_panel, fg_color="#2b2b2b")
        self.btn_box.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        # Botones desactivados hasta que haya conexión
        self.btn_load_folder = ctk.CTkButton(self.btn_box, text="📂 Cargar Carpeta", command=self.load_folder, fg_color="#34495e", height=40, state="disabled")
        self.btn_load_folder.pack(fill="x", padx=15, pady=10)
        self.btn_load_file = ctk.CTkButton(self.btn_box, text="📄 Cargar Archivo", command=self.load_file, fg_color="#34495e", height=40, state="disabled")
        self.btn_load_file.pack(fill="x", padx=15, pady=(0, 10))

        self.file_list_frame = ctk.CTkScrollableFrame(self.left_panel, label_text="Documentos")
        self.file_list_frame.grid(row=2, column=0, sticky="nsew")

        # 3. PANEL DERECHO (Vista Previa)
        self.right_panel = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=10)
        self.right_panel.grid(row=1, column=1, sticky="nsew", padx=15, pady=15)
        self.preview_label = ctk.CTkLabel(self.right_panel, text="\n\n(Vista Previa)", font=("Roboto", 16), text_color="#555")
        self.preview_label.pack(expand=True, fill="both", padx=10, pady=10)

        # 4. FOOTER
        self.footer = ctk.CTkFrame(self, height=90, fg_color="#2b2b2b")
        self.footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        self.progress = ctk.CTkProgressBar(self.footer, height=18, progress_color="#27ae60", fg_color="#444")
        self.progress.pack(fill="x", padx=0, pady=0)
        self.progress.set(0)

        self.btn_start = ctk.CTkButton(self.footer, text="▶ COMENZAR CARGA", command=self.iniciar_proceso, font=("Roboto", 15, "bold"), height=50, fg_color="#27ae60", hover_color="#2ecc71", state="disabled")
        self.btn_start.pack(side="left", padx=25, pady=20, fill="x", expand=True)

        self.btn_open = ctk.CTkButton(self.footer, text="📂 ABRIR RESULTADOS", command=self.open_output, font=("Roboto", 13, "bold"), height=50, fg_color="#e67e22", hover_color="#d35400", state="disabled")
        self.btn_open.pack(side="left", padx=(0, 25), pady=20)

        self.btn_stop = ctk.CTkButton(self.footer, text="⏹ DETENER", command=self.detener_proceso, font=("Roboto", 15, "bold"), height=50, fg_color="#c0392b", state="disabled")
        self.btn_stop.pack(side="right", padx=25, pady=20)

    # --- CAPA SUPERPUESTA (OVERLAY) ---
    def setup_overlay(self):
        self.overlay = ctk.CTkFrame(self, fg_color="rgba(0,0,0,0.7)", corner_radius=0)
        
        self.card = ctk.CTkFrame(self.overlay, width=450, height=500, fg_color="#2b2b2b", corner_radius=15, border_width=2, border_color="#3498db")
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(self.card, text="INGRESO DE DATOS", font=("Roboto", 20, "bold"), text_color="white").pack(pady=(30, 10))
        self.lbl_current_file = ctk.CTkLabel(self.card, text="Archivo: ...", text_color="#f39c12")
        self.lbl_current_file.pack(pady=(0, 20))

        ctk.CTkLabel(self.card, text="Nombre Completo:").pack(anchor="w", padx=50)
        self.entry_nom = ctk.CTkEntry(self.card, width=350, height=40)
        self.entry_nom.pack(pady=5)

        ctk.CTkLabel(self.card, text="DNI:").pack(anchor="w", padx=50)
        self.entry_dni = ctk.CTkEntry(self.card, width=350, height=40)
        self.entry_dni.pack(pady=5)

        ctk.CTkLabel(self.card, text="Carrera / Curso:").pack(anchor="w", padx=50)
        self.entry_car = ctk.CTkEntry(self.card, width=350, height=40)
        self.entry_car.pack(pady=5)

        # Event binding para Enter
        self.entry_car.bind("<Return>", lambda event: self.on_overlay_save())

        btn_row = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_row.pack(pady=30)
        
        ctk.CTkButton(btn_row, text="GUARDAR Y SEGUIR", command=self.on_overlay_save, fg_color="#27ae60", height=45, width=160).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="SALTAR", command=self.on_overlay_skip, fg_color="#c0392b", height=45, width=100).pack(side="left", padx=10)

    # --- CONEXIÓN BD ---
    def connect_db_thread(self):
        try:
            self.supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
            # Actualizar UI en hilo principal
            self.after(0, lambda: self.lbl_status.configure(text="Sistema Listo - BD Conectada", text_color="#2ecc71"))
            self.after(0, lambda: self.btn_load_folder.configure(state="normal"))
            self.after(0, lambda: self.btn_load_file.configure(state="normal"))
        except Exception as e:
            self.after(0, lambda: self.lbl_status.configure(text=f"Error BD: {str(e)}", text_color="red"))

    # --- LÓGICA DE ARCHIVOS ---
    def load_folder(self):
        path = filedialog.askdirectory()
        if path:
            # Evitar leer archivos ya procesados en la carpeta de salida
            files = [
                os.path.join(path, f) for f in os.listdir(path) 
                if f.lower().endswith(".pdf") and "CERTIFICADOS_QR" not in path
            ]
            self.prepare_queue(files, path)

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.prepare_queue([path], os.path.dirname(path))

    def prepare_queue(self, files, base_path):
        self.files_queue = files
        self.output_folder = os.path.join(base_path, "CERTIFICADOS_QR")
        if not os.path.exists(self.output_folder): os.makedirs(self.output_folder)
        
        for w in self.file_list_frame.winfo_children(): w.destroy()
        
        # Limitamos la vista a 50 archivos para no congelar la UI al cargar
        for f in self.files_queue[:50]:
            ctk.CTkButton(self.file_list_frame, text=f"📄 {os.path.basename(f)}", anchor="w", fg_color="transparent", height=25).pack(fill="x", pady=1)
        
        if len(self.files_queue) > 50:
            ctk.CTkLabel(self.file_list_frame, text=f"... y {len(self.files_queue)-50} más").pack()

        if self.files_queue:
            self.btn_start.configure(state="normal")
            self.trigger_preview(self.files_queue[0])
            self.lbl_status.configure(text=f"{len(self.files_queue)} archivos cargados", text_color="white")

    # --- PREVIEW SEGURO ---
    def trigger_preview(self, path):
        threading.Thread(target=self._preview_thread, args=(path,), daemon=True).start()

    def _preview_thread(self, path):
        try:
            doc = fitz.open(path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(0.6, 0.6))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            
            h = 550
            ratio = h / float(img.size[1])
            w = int(float(img.size[0]) * float(ratio))
            img = img.resize((w, h), Image.Resampling.NEAREST)
            
            # ¡IMPORTANTE! Guardar referencia en self para que el Garbage Collector no la borre
            self.current_preview_image = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
            
            self.after(0, lambda: self.preview_label.configure(image=self.current_preview_image, text=""))
        except Exception as e:
            print(f"Error preview: {e}")

    # --- MOTOR DE PROCESO ---
    def iniciar_proceso(self):
        if not self.supabase:
            messagebox.showerror("Error", "No hay conexión con la base de datos.")
            return

        self.btn_start.configure(state="disabled")
        self.btn_load_folder.configure(state="disabled")
        self.btn_load_file.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        
        self.stop_process_flag = False
        self.current_index = 0
        self.success_count = 0
        
        self.procesar_siguiente()

    def detener_proceso(self):
        self.stop_process_flag = True
        self.lbl_status.configure(text="Deteniendo...", text_color="red")
        self.hide_overlay()
        self.btn_stop.configure(state="disabled")

    def procesar_siguiente(self):
        if self.stop_process_flag or self.current_index >= len(self.files_queue):
            self.finish_process()
            return

        filepath = self.files_queue[self.current_index]
        filename = os.path.basename(filepath)
        
        self.lbl_status.configure(text=f"Procesando {self.current_index + 1}/{len(self.files_queue)}...", text_color="#3498db")
        progress_val = (self.current_index) / len(self.files_queue)
        self.progress.set(progress_val)
        
        self.trigger_preview(filepath)
        self.show_overlay(filename)

    # --- MANEJO DE OVERLAY ---
    def show_overlay(self, filename):
        self.lbl_current_file.configure(text=f"Archivo: {filename}")
        self.entry_nom.delete(0, 'end')
        self.entry_dni.delete(0, 'end')
        self.entry_car.delete(0, 'end')
        
        self.overlay.grid(row=0, column=0, rowspan=3, columnspan=2, sticky="nsew")
        self.overlay.lift()
        self.entry_nom.focus()

    def hide_overlay(self):
        self.overlay.grid_forget()

    def on_overlay_save(self):
        n = self.entry_nom.get().strip().upper()
        d = self.entry_dni.get().strip()
        c = self.entry_car.get().strip().upper()
        
        if not n or not d or not c:
            self.lbl_current_file.configure(text="⚠️ Faltan datos", text_color="red")
            return 
        
        self.hide_overlay()
        
        # Lanzar hilo de trabajo pesado
        filepath = self.files_queue[self.current_index]
        filename = os.path.basename(filepath)
        threading.Thread(target=self.bg_upload_stamp, args=(filepath, filename, n, d, c), daemon=True).start()

    def on_overlay_skip(self):
        self.hide_overlay()
        self.current_index += 1
        self.after(100, self.procesar_siguiente)

    # --- TRABAJO DE FONDO (CRÍTICO) ---
    def bg_upload_stamp(self, filepath, filename, nombre, dni, carrera):
        try:
            # 1. Supabase (Puede tardar)
            self.after(0, lambda: self.lbl_status.configure(text="Subiendo a nube...", text_color="#e67e22"))
            
            res = self.supabase.table("certificados").insert({
                "nombre_completo": nombre,
                "dni": dni,
                "modulo_curso": carrera,
                "carrera": "IISEP",
                "fecha_emision_texto": time.strftime("%d/%m/%Y")
            }).execute()
            
            # Validación robusta de respuesta
            if not res.data:
                raise Exception("Supabase no devolvió datos")
                
            uuid = res.data[0]['uuid_publico']

            # 2. Estampado
            self.after(0, lambda: self.lbl_status.configure(text="Generando PDF...", text_color="#e67e22"))
            
            qr = qrcode.QRCode(box_size=10, border=1)
            qr.add_data(f"{WEB_URL}?id={uuid}")
            qr.make(fit=True)
            img_bytes = io.BytesIO()
            qr.make_image(fill_color="black", back_color="white").save(img_bytes, format='PNG')
            
            doc = fitz.open(filepath)
            page = doc[0]
            page.insert_image(fitz.Rect(50, 50, 140, 140), stream=img_bytes.getvalue())
            page.insert_text((55, 45), "Escanee para validar", fontsize=7, color=(0,0,0))
            
            out = os.path.join(self.output_folder, filename)
            # Evitar sobreescribir si nombre existe (timestamp)
            if os.path.exists(out):
                out = os.path.join(self.output_folder, f"{os.path.splitext(filename)[0]}_{int(time.time())}.pdf")
            
            doc.save(out)
            doc.close()
            self.success_count += 1
            
        except Exception as e:
            print(f"ERROR CRÍTICO EN HILO: {e}")
            self.after(0, lambda: messagebox.showerror("Error en proceso", f"Fallo en {filename}:\n{e}"))
            
        finally:
            # ESTO ES LO QUE ARREGLA EL CONGELAMIENTO
            # Siempre asegura que el bucle continúe, incluso si hubo error.
            self.current_index += 1
            self.after(100, self.procesar_siguiente)

    def finish_process(self):
        self.progress.set(1)
        self.btn_open.configure(state="normal")
        self.reset_ui()
        
        msg = "Proceso Detenido" if self.stop_process_flag else "Finalizado con Éxito"
        messagebox.showinfo("Reporte", f"{msg}\nSe generaron {self.success_count} certificados correctamente.")

    def reset_ui(self):
        self.btn_start.configure(state="normal")
        self.btn_load_folder.configure(state="normal")
        self.btn_load_file.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="Listo", text_color="#2ecc71")

    def open_output(self):
        if os.path.exists(self.output_folder): os.startfile(self.output_folder)

if __name__ == "__main__":
    app = CertificadosApp()
    app.mainloop()