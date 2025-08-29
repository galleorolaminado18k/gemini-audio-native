import os
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai

# --- 🔹 NUEVO: Librerías para Google Sheets
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

# 👉 Usa la API_KEY fija (como la tienes) o si detecta variable de entorno la prioriza
API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI")
client = genai.Client(api_key=API_KEY)

# --- 🔹 NUEVO: Configurar conexión con Google Sheets de forma SEGURA
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1GD_HKVDQLQgYX_XaOkyVpI9RBSAgkRNPVnWC3KaY5P0"

gs_ready = False
sheet = None
try:
    # ⚠️ Si este archivo no existe en tu imagen, NO queremos que la app se caiga.
    creds = Credentials.from_service_account_file("credenciales.json", scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
    gs_ready = True
    print("✅ Google Sheets listo")
except Exception as e:
    # Seguimos vivos aunque no haya credenciales — lo registramos en logs.
    print(f"⚠️ Google Sheets deshabilitado: {e}")

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Validar JSON
        if not request.is_json:
            return jsonify({'error': 'Content-Type debe ser application/json'}), 400

        data = request.get_json(silent=True) or {}
        user_text = (data.get('text') or "").strip()

        if not user_text:
            return jsonify({'error': 'Campo text requerido'}), 400

        print(f"Texto recibido: {user_text}")

        # Usar generateContent normal (funciona en todos los hostings)
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=user_text
        )

        generated_text = getattr(response, "text", "") or ""
        print(f"Respuesta generada: {generated_text}")

        # Simular audio base64 con la respuesta
        audio_data = b"AUDIO:" + generated_text.encode('utf-8')[:500]
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # --- 🔹 NUEVO: Guardar en Google Sheets (sin romper si falla)
        if gs_ready and sheet is not None:
            try:
                sheet.append_row([user_text, generated_text, audio_base64])
            except Exception as e_sheet:
                # No rompas la respuesta; solo registra el fallo.
                print(f"⚠️ No se pudo escribir en Sheets: {e_sheet}")

        return jsonify({
            'candidates': [{
                'content': {
                    'role': 'model',
                    'parts': [{
                        'inlineData': {
                            'mimeType': 'audio/ogg',
                            'data': audio_base64
                        }
                    }]
                }
            }]
        })

    except Exception as e:
        # Log detallado y respuesta 500 controlada
        print(f"❌ Error en /chat: {e}")
        return jsonify({'error': str(e)}), 500

# --- 🔹 NUEVO: endpoint de salud real
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'sheets': 'ready' if gs_ready else 'disabled',
        'version': 'no-live-api'
    }), 200

if __name__ == '__main__':
    # Cloud Run usa 8080
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

