import os
import re
import time
import io
import qrcode
import pdfplumber
from supabase import create_client
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURACIÓN ---
URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s" # Pega tu key aquí
WEB_URL = "https://validador-certificados-tau.vercel.app"

# Rutas relativas (funciona desde cualquier PC)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FOLDER = os.path.join(BASE_DIR, 'entradas')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'salidas')

supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

def extraer_datos_pdf(path_pdf):
    """Intenta extraer Nombre y DNI usando Regex"""
    with pdfplumber.open(path_pdf) as pdf:
        texto = pdf.pages[0].extract_text()
        
        # 1. Buscar DNI (8 dígitos)
        dni_match = re.search(r'DNI N°\s*(\d{8})', texto)
        dni = dni_match.group(1) if dni_match else "No detectado"

        # 2. Buscar Nombre (Lógica básica: línea después de 'otorga a')
        nombre = "Nombre Manual Requerido"
        lines = texto.split('\n')
        for i, line in enumerate(lines):
            if "otorga a" in line.lower() or "conferido a" in line.lower():
                if i + 1 < len(lines):
                    nombre = lines[i+1].strip()
                break
        
        return nombre, dni, texto # Devolvemos texto por si quieres buscar fecha

def estampar_qr(pdf_path, filename):
    nombre, dni, _ = extraer_datos_pdf(pdf_path)
    print(f"🔄 Procesando: {filename} | Alumno: {nombre}")

    # 1. Subir a Supabase
    data = {
        "nombre_completo": nombre,
        "dni": dni,
        "modulo_curso": "Curso Detectado Automáticamente", # Podrías mejorar el regex para esto
        "carrera": "Carrera Técnica",
        "fecha_emision_texto": "Noviembre 2025" # O extraer fecha actual
    }
    
    try:
        res = supabase.table("certificados").insert(data).execute()
        uuid = res.data[0]['uuid_publico']
    except Exception as e:
        print(f"❌ Error subiendo a BD: {e}")
        return

    # 2. Generar QR
    url_validacion = f"{WEB_URL}?id={uuid}"
    qr_img = qrcode.make(url_validacion)
    qr_temp = "temp_qr.png"
    qr_img.save(qr_temp)

    # 3. Estampar en PDF
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    # AJUSTA ESTAS COORDENADAS (X, Y)
    can.drawImage(qr_temp, 50, 50, width=90, height=90) 
    can.setFont("Helvetica", 8)
    can.drawString(50, 40, "Validar originalidad:")
    can.save()

    packet.seek(0)
    new_pdf = PdfReader(packet)
    existing_pdf = PdfReader(open(pdf_path, "rb"))
    output = PdfWriter()
    
    page = existing_pdf.pages[0]
    page.merge_page(new_pdf.pages[0])
    output.add_page(page)

    # Guardar en carpeta SALIDAS
    output_filename = f"LISTO_{filename}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    
    with open(output_path, "wb") as f:
        output.write(f)
    
    print(f"✅ Guardado en: salidas/{output_filename}")
    os.remove(qr_temp) # Limpiar

def procesar_todo():
    # Asegurar que existan las carpetas
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
    
    archivos = [f for f in os.listdir(INPUT_FOLDER) if f.endswith('.pdf')]
    
    if not archivos:
        print("⚠️ No hay PDFs en la carpeta 'entradas'.")
        return

    print(f"📂 Encontrados {len(archivos)} documentos. Iniciando...")
    for archivo in archivos:
        ruta_completa = os.path.join(INPUT_FOLDER, archivo)
        estampar_qr(ruta_completa, archivo)

if __name__ == "__main__":
    procesar_todo()