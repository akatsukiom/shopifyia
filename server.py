from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Si prefieres usar variables de entorno en Railway:
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "TU_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "TU_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# URL para enviar mensajes mediante la API de Twilio
WHATSAPP_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json  # Recibe los datos del pedido desde Shopify

    # 1. Imprimir el JSON en logs para diagnosticar dónde viene el teléfono
    print("=== Shopify Webhook Data ===")
    print(data)

    # 2. Extraer el nombre (siempre intenta sacar un nombre aunque sea genérico)
    nombre = data.get("customer", {}).get("first_name", "Cliente")

    # 3. Intentar capturar el teléfono en distintos campos
    telefono = data.get("customer", {}).get("phone")  # 1) customer

    if not telefono:
        telefono = data.get("billing_address", {}).get("phone")  # 2) billing_address

    if not telefono:
        telefono = data.get("shipping_address", {}).get("phone")  # 3) shipping_address

    # 4. Validar que el teléfono exista
    if not telefono:
        return jsonify({"error": "No se encontró un número de teléfono"}), 400

    # 5. Obtener lista de productos
    line_items = data.get("line_items", [])
    productos = ", ".join([item.get("title", "Sin título") for item in line_items])

    # 6. Crear el mensaje de WhatsApp
    mensaje = (
        f"¡Hola {nombre}! Tu pedido ha sido confirmado y está en proceso. "
        f"Productos: {productos}. ¡Gracias por tu compra!"
    )

    # 7. Enviar mensaje a WhatsApp mediante la API de Twilio
    payload = {
        "From": TWILIO_WHATSAPP_NUMBER,
        "To": f"whatsapp:{telefono}",
        "Body": mensaje
    }
    response = requests.post(WHATSAPP_API_URL, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

    # 8. Retornar el resultado al final
    return jsonify({"message": "Notificación enviada"}), response.status_code

if __name__ == "__main__":
    # Usa el puerto asignado por Railway, o 5000 por defecto
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
