from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    text = data.get("text", "")
    return jsonify({
        "text_received": text,
        "reply": f"Respuesta para: {text}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Cloud Run asigna este puerto
    app.run(host="0.0.0.0", port=port)
