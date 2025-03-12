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

# Lista de números a notificar
# IMPORTANTE: Cada número debe estar aprobado en el sandbox de Twilio
# Para aprobar un número, este debe haber enviado el mensaje de verificación al 
# número de sandbox de Twilio primero.
NUMEROS_NOTIFICACION = [
    "+5214962541655",
    "+5214961436947",
    "+5214961015725",  # Tu número principal
    # Agrega más números aquí, todos deben estar verificados en Twilio
]

# Cache para evitar duplicados
PROCESSED_ORDERS = set()
CACHE_FILE = "processed_orders.json"

# Intentar cargar órdenes procesadas anteriormente
try:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            PROCESSED_ORDERS = set(json.load(f))
except Exception as e:
    print(f"Error cargando el archivo de caché: {e}")

def formatear_numero(numero):
    """Formatea correctamente un número para WhatsApp"""
    numero = numero.strip()
    if not numero.startswith('+'):
        numero = '+' + numero
    return numero

def enviar_whatsapp(numero, mensaje):
    """Envía un mensaje de WhatsApp a un número específico"""
    numero_formateado = formatear_numero(numero)
    
    payload = {
        "From": TWILIO_WHATSAPP_NUMBER,
        "To": f"whatsapp:{numero_formateado}",
        "Body": mensaje
    }
    
    try:
        response = requests.post(WHATSAPP_API_URL, data=payload, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        print(f"Twilio Response para {numero_formateado}:", response.status_code, response.text)
        
        # Imprimir más detalles para diagnóstico
        if response.status_code != 201:
            print(f"Error al enviar WhatsApp a {numero_formateado}. Detalles:")
            print(f"Status: {response.status_code}")
            print(f"Respuesta: {response.text}")
            
            # Verificar si es error de "número no verificado"
            if "is not a verified" in response.text:
                print(f"ADVERTENCIA: El número {numero_formateado} no está verificado en el sandbox de Twilio.")
                print("El usuario debe enviar primero 'join [código]' al número del sandbox de Twilio.")
        
        return response.status_code == 201
    except Exception as e:
        print(f"Excepción al enviar WhatsApp a {numero_formateado}: {e}")
        return False

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
    
    # Extraer datos básicos del cliente
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
    
    # Información del pago
    moneda = data.get("currency", "MXN")
    total_precio = data.get("total_price", "0.00")
    
    # Métodos de pago
    payment_gateway_names = data.get("payment_gateway_names", [])
    metodo_pago = "No especificado"
    if payment_gateway_names:
        metodo_pago = ", ".join(payment_gateway_names)
    
    # Estado financiero del pedido
    estado_financiero = data.get("financial_status", "No disponible")
    
    # Obtener productos
    line_items = data.get("line_items", [])
    productos_detalles = []
    for item in line_items:
        titulo = item.get("title", "Sin título")
        cantidad = item.get("quantity", 1)
        precio = item.get("price", "0.00")
        productos_detalles.append(f"{titulo} (x{cantidad}) - ${precio} {moneda}")
    
    productos = "\n   • " + "\n   • ".join(productos_detalles) if productos_detalles else "No hay productos"
    
    # Crear el mensaje de notificación
    mensaje = (
        f"📦 ¡NUEVO PEDIDO!\n\n"
        f"🔢 Orden: {numero_orden}\n"
        f"👤 Cliente: {nombre_cliente} {apellido_cliente}\n"
        f"📧 Correo: {correo}\n"
        f"📱 Teléfono: {telefono}\n"
        f"🗓️ Fecha: {fecha_pedido}\n"
        f"💰 Total: ${total_precio} {moneda}\n"
        f"💳 Método de pago: {metodo_pago}\n"
        f"📊 Estado: {estado_financiero}\n\n"
        f"🛒 Productos: {productos}"
    )
    
    # Registrar a qué números se intentó enviar y el resultado
    resultados = {}
    exito = False
    
    # Enviar mensajes a todos los números configurados
    for numero in NUMEROS_NOTIFICACION:
        # Registrar intento
        print(f"Intentando enviar a {numero}...")
        
        # Enviar mensaje
        resultado = enviar_whatsapp(numero, mensaje)
        resultados[numero] = resultado
        
        if resultado:
            exito = True
            print(f"✓ Enviado correctamente a {numero}")
        else:
            print(f"✗ Falló el envío a {numero}")
            
        # Esperar entre envíos
        time.sleep(1)
    
    # Registrar en logs todos los resultados
    print("=== Resumen de envíos ===")
    for numero, resultado in resultados.items():
        print(f"Número: {numero} - {'Éxito' if resultado else 'Fallo'}")
    
    # Si al menos un mensaje fue enviado exitosamente, marcar el pedido como procesado
    if exito:
        PROCESSED_ORDERS.add(order_id)
        
        # Guardar en el archivo de caché
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(list(PROCESSED_ORDERS), f)
        except Exception as e:
            print(f"Error guardando caché: {e}")
        
        return jsonify({
            "message": "Notificaciones enviadas", 
            "resultados": resultados
        }), 200
    else:
        return jsonify({
            "message": "Error al enviar notificaciones",
            "resultados": resultados
        }), 500

@app.route("/test-numeros", methods=["GET"])
def test_numeros():
    """Endpoint para probar el envío a todos los números configurados"""
    resultados = {}
    mensaje_prueba = (
        f"🧪 MENSAJE DE PRUEBA 🧪\n\n"
        f"Este es un mensaje para verificar que las notificaciones "
        f"de pedidos de Shopify están funcionando correctamente.\n\n"
        f"Fecha y hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
    
    for numero in NUMEROS_NOTIFICACION:
        resultado = enviar_whatsapp(numero, mensaje_prueba)
        resultados[numero] = resultado
        time.sleep(1)
    
    return jsonify({
        "message": "Prueba completada",
        "resultados": resultados
    })

@app.route("/", methods=["GET"])
def health_check():
    """Endpoint de verificación de salud"""
    return jsonify({
        "status": "ok", 
        "message": "El servidor de notificaciones está funcionando correctamente",
        "numeros_configurados": NUMEROS_NOTIFICACION,
        "twilio_number": TWILIO_WHATSAPP_NUMBER
    })

if __name__ == "__main__":
    # Usa el puerto asignado por Railway o 5000 por defecto
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)