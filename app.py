import os
import json
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai  # sdk google-genai (ya está en tus requirements)

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

# --- API KEY de Gemini (respetamos tu valor por defecto)
API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyC3895F5JKZSHKng1IVL_3DywImp4lwVyI")
client = genai.Client(api_key=API_KEY)

# --- Google Sheets (seguro: env var primero, archivo después)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1GD_HKVDQLQgYX_XaOkyVpI9RBSAgkRNPVnWC3KaY5P0"

gs_ready = False
sheet = None
try:
    creds = None
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json:
        # credenciales desde variable de entorno (JSON completo)
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        # fallback local (archivo dentro de la imagen): credenciales.json
        creds = Credentials.from_service_account_file("credenciales.json", scopes=SCOPES)

    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
    gs_ready = True
    print("✅ Google Sheets listo")
except Exception as e:
    print(f"⚠️ Google Sheets deshabilitado: {e}")

@app.route('/chat', methods=['POST'])
def chat():
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type debe ser application/json'}), 400

        data = request.get_json(silent=True) or {}
        user_text = (data.get('text') or '').strip()

        if not user_text:
            return jsonify({'error': 'Campo text requerido'}), 400

        print(f"Texto recibido: {user_text}")

        # Generar texto con Gemini (sdk google-genai)
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=user_text
        )
        generated_text = getattr(response, "text", "") or ""
        print(f"Respuesta generada: {generated_text}")

        # Simular audio base64 con la respuesta (tu lógica original)
        audio_data = b"AUDIO:" + generated_text.encode('utf-8')[:500]
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # Guardar en Google Sheets (no romper si falla)
        if gs_ready and sheet is not None:
            try:
                sheet.append_row([user_text, generated_text, audio_base64])
            except Exception as e_sheet:
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
        }), 200

    except Exception as e:
        print(f"❌ Error en /chat: {e}")
        return jsonify({'error': str(e)}), 500

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
t)

