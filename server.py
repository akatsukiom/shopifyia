from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime, timedelta
import time

app = Flask(__name__)

# Variables de entorno (Railway):
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "TU_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "TU_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

WHATSAPP_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

# Tu número personal en formato correcto para WhatsApp
MI_NUMERO_PERSONAL = "+5214962541655"  # NO incluyas "whatsapp:" aquí

# Cache para evitar duplicados
# Almacenará los ID de pedidos procesados (en memoria)
PROCESSED_ORDERS = set()

# Ruta para el archivo de caché persistente
CACHE_FILE = "processed_orders.json"

# Intentar cargar órdenes procesadas anteriormente
try:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            PROCESSED_ORDERS = set(json.load(f))
except Exception as e:
    print(f"Error cargando el archivo de caché: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json  # Recibe datos del pedido desde Shopify
    
    # Obtener ID del pedido para verificar si ya fue procesado
    order_id = str(data.get("id", ""))
    
    # Si ya procesamos este pedido, terminar
    if order_id in PROCESSED_ORDERS:
        print(f"Pedido {order_id} ya fue procesado anteriormente. Ignorando.")
        return jsonify({"message": "Pedido ya procesado"}), 200
    
    # Verificar si el pedido es reciente (últimas 24 horas)
    # Esto es útil para evitar procesar pedidos históricos
    created_at = data.get("created_at", "")
    if created_at:
        try:
            # Convertir fecha ISO de Shopify a objeto datetime
            order_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now().astimezone()  # Obtener fecha actual con zona horaria
            
            # Si el pedido tiene más de 24 horas, ignorarlo
            if (now - order_date) > timedelta(hours=24):
                print(f"Pedido {order_id} es más antiguo que 24 horas. Ignorando.")
                return jsonify({"message": "Pedido antiguo, no procesado"}), 200
        except Exception as e:
            print(f"Error procesando fecha: {e}")
    
    # Imprime el JSON para diagnosticar
    print("=== Shopify Webhook Data ===")
    print(data)
    
    # Extraer datos relevantes para el mensaje
    numero_orden = data.get("name", "Sin número")
    nombre_cliente = data.get("customer", {}).get("first_name", "Cliente")
    apellido_cliente = data.get("customer", {}).get("last_name", "")
    correo = data.get("email", "No disponible")
    
    # Intentar obtener el teléfono de diferentes lugares
    telefono = data.get("phone", None)
    if not telefono:
        telefono = data.get("customer", {}).get("phone")
    if not telefono:
        telefono = data.get("billing_address", {}).get("phone")
    if not telefono:
        telefono = data.get("shipping_address", {}).get("phone")
    
    telefono = telefono or "No disponible"
    
    # Extraer la fecha del pedido
    fecha_pedido = "No disponible"
    if created_at:
        try:
            date_obj = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            fecha_pedido = date_obj.strftime("%d/%m/%Y %H:%M")
        except:
            fecha_pedido = created_at
    
    # Obtener productos
    line_items = data.get("line_items", [])
    productos = ", ".join([item.get("title", "Sin título") for item in line_items])
    
    # Crear el mensaje de notificación
    mensaje = (
        f"📦 ¡NUEVO PEDIDO!\n\n"
        f"🔢 Orden: {numero_orden}\n"
        f"👤 Cliente: {nombre_cliente} {apellido_cliente}\n"
        f"📧 Correo: {correo}\n"
        f"📱 Teléfono: {telefono}\n"
        f"🗓️ Fecha: {fecha_pedido}\n\n"
        f"🛒 Productos: {productos}"
    )
    
    # Formatear correctamente el número de WhatsApp
    numero = MI_NUMERO_PERSONAL.strip()
    if not numero.startswith('+'):
        numero = '+' + numero
    
    # Enviar siempre a tu número personal, con formato correcto
    payload = {
        "From": TWILIO_WHATSAPP_NUMBER,
        "To": f"whatsapp:{numero}",
        "Body": mensaje
    }
    
    # Realizar la petición a Twilio
    response = requests.post(WHATSAPP_API_URL, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    
    # Imprimir la respuesta de Twilio en logs
    print("Twilio Response:", response.status_code, response.text)
    
    # Si el mensaje fue enviado exitosamente, agregar el ID a la lista de procesados
    if response.status_code == 201:
        PROCESSED_ORDERS.add(order_id)
        
        # Guardar en el archivo de caché
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(list(PROCESSED_ORDERS), f)
        except Exception as e:
            print(f"Error guardando caché: {e}")
    
    # Devolver el status code de Twilio a Shopify
    return jsonify({"message": "Notificación enviada"}), response.status_code

if __name__ == "__main__":
    # Usa el puerto asignado por Railway o 5000 por defecto
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)