from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Variables de entorno (ideal para Railway):
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "TU_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "TU_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

WHATSAPP_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json  # Datos del pedido desde Shopify
    
    # Imprimir JSON en logs (Railway) para diagnosticar
    print("=== Shopify Webhook Data ===")
    print(data)
    
    # 1. Extraer nombre
    nombre = data.get("customer", {}).get("first_name", "Cliente")
    
    # 2. Buscar el teléfono en distintos campos
    telefono = data.get("customer", {}).get("phone")
    if not telefono:
        telefono = data.get("billing_address", {}).get("phone")
    if not telefono:
        telefono = data.get("shipping_address", {}).get("phone")
    
    # 3. Validar que tengamos un teléfono
    if not telefono:
        return jsonify({"error": "No se encontró un número de teléfono"}), 400
    
    # 4. Ajustar formato para México (agregar '1' tras '+52' si no está)
    if telefono.startswith("+52") and not telefono.startswith("+521"):
        telefono = "+521" + telefono[3:]
    
    # 5. Obtener lista de productos
    line_items = data.get("line_items", [])
    productos = ", ".join([item.get("title", "Sin título") for item in line_items])
    
    # 6. Crear el mensaje
    mensaje = (
        f"¡Hola {nombre}! Tu pedido ha sido confirmado y está en proceso. "
        f"Productos: {productos}. ¡Gracias por tu compra!"
    )
    
    # 7. Preparar payload para Twilio
    payload = {
        "From": TWILIO_WHATSAPP_NUMBER,     # Debe ser "whatsapp:+14155238886" si usas Sandbox
        "To": f"whatsapp:{telefono}",
        "Body": mensaje
    }
    
    # 8. Enviar mensaje a Twilio
    response = requests.post(WHATSAPP_API_URL, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    
    # 9. Imprimir respuesta de Twilio para ver errores (por ejemplo, 21910)
    print("Twilio Response:", response.status_code, response.text)
    
    # 10. Devolver el status code de Twilio a Shopify
    return jsonify({"message": "Notificación enviada"}), response.status_code

if __name__ == "__main__":
    # Usa el puerto asignado por Railway o 5000 por defecto
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
