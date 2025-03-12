from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Credenciales Twilio para enviar WhatsApp
TWILIO_ACCOUNT_SID = "TU_SID"
TWILIO_AUTH_TOKEN = "TU_TOKEN"
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"  # Número de Twilio
WHATSAPP_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json  # Recibe los datos del pedido desde Shopify

    # Extraer información relevante del pedido
    nombre = data.get("customer", {}).get("first_name", "Cliente")
    telefono = data.get("customer", {}).get("phone", None)
    productos = ", ".join([item["title"] for item in data.get("line_items", [])])

    # Si no hay teléfono, evitar enviar el mensaje
    if not telefono:
        return jsonify({"error": "No se encontró un número de teléfono"}), 400

    mensaje = f"¡Hola {nombre}! Tu pedido ha sido confirmado y está en proceso. Productos: {productos}. Gracias por tu compra."

    # Enviar mensaje a WhatsApp mediante Twilio
    payload = {
        "From": TWILIO_WHATSAPP_NUMBER,
        "To": f"whatsapp:{telefono}",
        "Body": mensaje
    }
    response = requests.post(WHATSAPP_API_URL, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

    return jsonify({"message": "Notificación enviada"}), response.status_code

if __name__ == "__main__":
    app.run(port=5000)
