from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Obtener credenciales de Twilio desde variables de entorno (configuradas en Railway)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "TU_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "TU_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# URL para enviar mensajes mediante la API de Twilio
WHATSAPP_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json  # Recibe los datos del pedido desde Shopify

    # Extraer información relevante del pedido
    nombre = data.get("customer", {}).get("first_name", "Cliente")
    telefono = data.get("customer", {}).get("phone", None)
    productos = ", ".join([item.get("title", "") for item in data.get("line_items", [])])

    # Validar que el teléfono exista
    if not telefono:
        return jsonify({"error": "No se encontró un número de teléfono"}), 400

    mensaje = (f"¡Hola {nombre}! Tu pedido ha sido confirmado y está en proceso. "
               f"Productos: {productos}. Gracias por tu compra.")

    # Enviar mensaje a WhatsApp mediante la API de Twilio
    payload = {
        "From": TWILIO_WHATSAPP_NUMBER,
        "To": f"whatsapp:{telefono}",
        "Body": mensaje
    }
    response = requests.post(WHATSAPP_API_URL, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

    return jsonify({"message": "Notificación enviada"}), response.status_code

if __name__ == "__main__":
    # Railway asigna el puerto en la variable de entorno PORT; si no, usa 5000 por defecto.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
