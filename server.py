from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Obtener credenciales de Twilio desde variables de entorno (configuradas en Railway)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "TU_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "TU_TOKEN")
# Asegúrate de actualizar este número con el número de Twilio que estés usando (ej. sandbox o número de producción)
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# URL para enviar mensajes mediante la API de Twilio
WHATSAPP_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json  # Recibe los datos del pedido desde Shopify
    
    # Imprimir el JSON completo para ver dónde vienen los datos y diagnosticar
    print("=== Shopify Webhook Data ===")
    print(data)
    
    # Extraer el nombre del cliente (por defecto "Cliente" si no viene)
    nombre = data.get("customer", {}).get("first_name", "Cliente")
    
    # Intentar capturar el teléfono en distintos campos
    telefono = data.get("customer", {}).get("phone")
    if not telefono:
        telefono = data.get("billing_address", {}).get("phone")
    if not telefono:
        telefono = data.get("shipping_address", {}).get("phone")
    
    # Si no se encontró teléfono, devolver error 400
    if not telefono:
        return jsonify({"error": "No se encontró un número de teléfono en el pedido"}), 400
    
    # Opcional: Ajustar el formato del teléfono para México
    # Por ejemplo, si el número viene como "+524961337974", puede que se requiera "+5214961337974"
    # Descomenta y ajusta según necesites:
    # if telefono.startswith("+52") and not telefono.startswith("+521"):
    #     telefono = "+521" + telefono[3:]
    
    # Obtener lista de productos
    line_items = data.get("line_items", [])
    productos = ", ".join([item.get("title", "Sin título") for item in line_items])
    
    # Crear el mensaje de WhatsApp
    mensaje = (
        f"¡Hola {nombre}! Tu pedido ha sido confirmado y está en proceso. "
        f"Productos: {productos}. ¡Gracias por tu compra!"
    )
    
    # Preparar payload para enviar a Twilio
    payload = {
        "From": TWILIO_WHATSAPP_NUMBER,
        "To": f"whatsapp:{telefono}",
        "Body": mensaje
    }
    
    # Enviar mensaje a WhatsApp mediante la API de Twilio
    response = requests.post(WHATSAPP_API_URL, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    
    # Imprimir la respuesta de Twilio para depurar posibles errores
    print("Twilio Response:", response.status_code, response.text)
    
    # Devuelve la respuesta de Twilio (si es 400 se propagará ese código)
    return jsonify({"message": "Notificación enviada"}), response.status_code

if __name__ == "__main__":
    # Railway asigna el puerto en la variable de entorno PORT; se usa 5000 por defecto.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
