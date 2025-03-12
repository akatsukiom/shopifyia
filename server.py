from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Variables de entorno (Railway):
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "TU_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "TU_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

WHATSAPP_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

# Tu número personal en formato E.164 (ej. +521XXXXXXXXXX para México)
MI_NUMERO_PERSONAL = "+5214962541655"  # Ajusta este valor a tu número

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json  # Recibe datos del pedido desde Shopify
    
    # Imprime el JSON para diagnosticar
    print("=== Shopify Webhook Data ===")
    print(data)
    
    # Extraer datos relevantes para el mensaje
    numero_orden = data.get("name", "Sin número")
    nombre_cliente = data.get("customer", {}).get("first_name", "Cliente")
    line_items = data.get("line_items", [])
    
    # Construir una lista de productos
    productos = ", ".join([item.get("title", "Sin título") for item in line_items])
    
    # Crear el mensaje de notificación
    mensaje = (
        f"¡Se ha pagado un nuevo pedido!\n"
        f"Orden: {numero_orden}\n"
        f"Cliente: {nombre_cliente}\n"
        f"Productos: {productos}"
    )
    
    # Enviar siempre a tu número personal
    payload = {
        "From": TWILIO_WHATSAPP_NUMBER,        # Por ejemplo, "whatsapp:+14155238886" (sandbox)
        "To": f"whatsapp:{MI_NUMERO_PERSONAL}", # Tu WhatsApp personal
        "Body": mensaje
    }
    
    # Realizar la petición a Twilio
    response = requests.post(WHATSAPP_API_URL, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    
    # Imprimir la respuesta de Twilio en logs (para ver si hay errores)
    print("Twilio Response:", response.status_code, response.text)
    
    # Devolver el status code de Twilio a Shopify
    return jsonify({"message": "Notificación enviada"}), response.status_code

if __name__ == "__main__":
    # Usa el puerto asignado por Railway o 5000 por defecto
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
