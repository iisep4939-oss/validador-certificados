import io
import qrcode
from supabase import create_client
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURACIÓN ---
URL_SUPABASE = "https://burdkeuqrguzkmuzrqub.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1cmRrZXVxcmd1emttdXpycXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNjQ0MjAsImV4cCI6MjA3OTk0MDQyMH0.YlLkJuXSpyGdr8KsGIDTO1Cf9sexr4BlzP_pDQoMa5s"
URL_WEB_VALIDADOR = "https://validador-certificados.vercel.app/" # O localhost

# Archivo origen y destino
INPUT_PDF = "CONSTANCIA.pdf"  # El archivo que subiste
OUTPUT_PDF = "CONSTANCIA_CON_QR_BRAYAN.pdf"

supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

def crear_constancia_qr(nombre, dni, modulo, carrera, fecha):
    print(f"1. Registrando a {nombre} en Supabase...")
    
    # A. Insertar en BD
    data = {
        "nombre_completo": nombre,
        "dni": dni,
        "modulo_curso": modulo,
        "carrera": carrera,
        "fecha_emision_texto": fecha
    }
    res = supabase.table("certificados").insert(data).execute()
    uuid_qr = res.data[0]['uuid_publico']
    url_final = f"{URL_WEB_VALIDADOR}?id={uuid_qr}"
    
    print(f"   -> ID Generado: {uuid_qr}")

    # B. Generar la capa del QR (Overlay)
    packet = io.BytesIO()
    # Creamos un canvas del tamaño de una hoja A4 (o el tamaño de tu PDF)
    can = canvas.Canvas(packet, pagesize=A4)
    
    # --- POSICIÓN DEL QR ---
    # Coordenadas (X, Y). (0,0) es abajo a la izquierda.
    # Ajusta estos valores para mover el QR en el documento.
    x_qr = 50   # 50 puntos desde la izquierda
    y_qr = 50   # 50 puntos desde abajo
    tamano = 90 # Tamaño del QR
    
    # Generar imagen QR temporal
    qr_img = qrcode.make(url_final)
    qr_filename = "temp_qr.png"
    qr_img.save(qr_filename)
    
    # Dibujar el QR y un texto pequeño en el PDF
    can.drawImage(qr_filename, x_qr, y_qr, width=tamano, height=tamano)
    can.setFont("Helvetica", 8)
    can.drawString(x_qr, y_qr - 10, "Escanee para validar")
    can.save()

    # C. Fusionar con el PDF original
    packet.seek(0)
    new_pdf = PdfReader(packet) # La capa del QR
    existing_pdf = PdfReader(open(INPUT_PDF, "rb")) # El documento original
    output = PdfWriter()

    # Obtener la primera página (donde está el diploma)
    page = existing_pdf.pages[0]
    # Fusionar (estampar) el QR encima
    page.merge_page(new_pdf.pages[0])
    output.add_page(page)

    # Guardar resultado
    with open(OUTPUT_PDF, "wb") as fStream:
        output.write(fStream)
    
    print(f"2. Documento generado exitosamente: {OUTPUT_PDF}")

# --- EJECUTAR CON LOS DATOS REALES DEL PDF SUBIDO ---
if __name__ == "__main__":
    crear_constancia_qr(
        nombre="BRAYAN CRISTIAN FERNANDO RETAMOZO CORDOVA",
        dni="77146876",
        modulo="Ensamblaje de PC's",
        carrera="Técnica de Operaciones de Computadoras",
        fecha="24 de octubre del 2024"
    )