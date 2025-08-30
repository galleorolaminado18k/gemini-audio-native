import os
import json
import time
import base64
from collections import deque
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

# --- Google Sheets (seguro: variable de entorno primero, archivo después)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1GD_HKVDQLQgYX_XaOkyVpI9RBSAgkRNPVnWC3KaY5P0"

gs_ready = False
sheet = None
try:
    creds = None
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json:
        # credenciales desde variable de entorno (JSON completo en string)
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

# =========================
# 🔹 Rate limiting local (simple por IP)
# Permite N requests por ventana de T segundos por IP
# =========================
RATE_WINDOW_SECONDS = 10
RATE_MAX_REQUESTS = 5
_ip_hits = {}

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    q = _ip_hits.setdefault(ip, deque())
    # Limpia timestamps fuera de ventana
    while q and (now - q[0]) > RATE_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= RATE_MAX_REQUESTS:
        return True
    q.append(now)
    return False

# =========================
# 🔹 Helper: llamada a Gemini con reintentos (exponencial backoff)
# =========================
def generate_with_backoff(user_text: str, max_retries=3):
    backoffs = [0.5, 1.0, 2.0]  # segundos
    attempt = 0
    while True:
        try:
            resp = client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=user_text
            )
            return resp
        except Exception as e:
            # Si parece error de cuota/velocidad, reintenta con backoff
            msg = str(e).lower()
            is_rate = ("rate" in msg) or ("quota" in msg) or ("429" in msg) or ("too many" in msg)
            attempt += 1
            if is_rate and attempt <= max_retries:
                time.sleep(backoffs[min(attempt - 1, len(backoffs) - 1)])
                continue
            raise  # otros errores o agotados los reintentos

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Validar JSON
        if not request.is_json:
            return jsonify({'error': 'Content-Type debe ser application/json'}), 400

        data = request.get_json(silent=True) or {}
        user_text = (data.get('text') or '').strip()

        if not user_text:
            return jsonify({'error': 'Campo text requerido'}), 400

        # Rate limit por IP
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        if is_rate_limited(ip):
            # Devuelve 429 con Retry-After sugerido
            resp = jsonify({
                'error': 'Too Many Requests',
                'detail': f'Has superado {RATE_MAX_REQUESTS} solicitudes en {RATE_WINDOW_SECONDS}s. Intenta nuevamente en unos segundos.'
            })
            resp.status_code = 429
            resp.headers['Retry-After'] = '5'
            return resp

        print(f"[{ip}] Texto recibido: {user_text}")

        # Llamada a Gemini con reintentos
        try:
            response = generate_with_backoff(user_text)
        except Exception as e_genai:
            # Si aquí cayó por cuota (429), propagamos como 429
            msg = str(e_genai).lower()
            if ("rate" in msg) or ("quota" in msg) or ("429" in msg) or ("too many" in msg):
                resp = jsonify({'error': 'Rate limit de Gemini', 'detail': str(e_genai)})
                resp.status_code = 429
                resp.headers['Retry-After'] = '5'
                return resp
            # Otros errores: 502 (upstream)
            return jsonify({'error': 'Gemini upstream error', 'detail': str(e_genai)}), 502

        generated_text = getattr(response, "text", "") or ""
        print(f"Respuesta generada: {generated_text[:200]}")

        # Simular audio base64 con la respuesta (tu lógica original)
        audio_data = b"AUDIO:" + generated_text.encode('utf-8')[:500]
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # Guardar en Google Sheets (sin romper si falla)
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
    # Cloud Run necesita escuchar en 8080
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

