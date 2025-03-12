from flask import Flask, request, jsonify, render_template_string
import requests
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import time

app = Flask(__name__)

# Variables de entorno (Railway):
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "TU_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "TU_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# Variables para correo electrónico
EMAIL_REMITENTE = os.environ.get("EMAIL_REMITENTE", "tu_correo@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "tu_password_o_app_password")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com") 
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# Número de WhatsApp para que los clientes envíen su boucher
NUMERO_BOUCHER = os.environ.get("NUMERO_BOUCHER", "4961260597")

WHATSAPP_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

# Lista de números a notificar
NUMEROS_NOTIFICACION = [
    "+5214962541655",
    "+5214961436947",
    "+5214961015725",
    # Agrega más números aquí, todos deben estar verificados en Twilio
]

# Cache para evitar duplicados
PROCESSED_ORDERS = set()
PENDING_ORDERS = {}  # Almacena órdenes pendientes de confirmación
CACHE_FILE = "processed_orders.json"
PENDING_FILE = "pending_orders.json"

# Cargar órdenes procesadas y pendientes
try:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            PROCESSED_ORDERS = set(json.load(f))
    
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, 'r') as f:
            PENDING_ORDERS = json.load(f)
except Exception as e:
    print(f"Error cargando archivos de caché: {e}")

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
        return response.status_code == 201
    except Exception as e:
        print(f"Excepción al enviar WhatsApp a {numero_formateado}: {e}")
        return False

def enviar_correo(destinatario, asunto, mensaje_html):
    """Envía un correo electrónico con formato HTML"""
    # Si no hay configuración de correo, salir
    if not EMAIL_REMITENTE or not EMAIL_PASSWORD:
        print("Configuración de correo electrónico incompleta. No se enviará el correo.")
        return False
    
    try:
        # Crear mensaje
        msg = MIMEMultipart('alternative')
        msg['Subject'] = asunto
        msg['From'] = EMAIL_REMITENTE
        msg['To'] = destinatario
        
        # Agregar contenido HTML
        mensaje_parte = MIMEText(mensaje_html, 'html')
        msg.attach(mensaje_parte)
        
        # Conectar con el servidor SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Iniciar conexión segura
        server.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
        
        # Enviar correo
        server.sendmail(EMAIL_REMITENTE, destinatario, msg.as_string())
        server.quit()
        
        print(f"Correo enviado exitosamente a {destinatario}")
        return True
        
    except Exception as e:
        print(f"Error al enviar correo: {e}")
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
    
    # Guardar en pendientes para futura confirmación
    PENDING_ORDERS[order_id] = {
        "order_id": order_id,
        "numero_orden": numero_orden,
        "nombre_cliente": f"{nombre_cliente} {apellido_cliente}",
        "correo": correo,
        "telefono": telefono,
        "fecha_pedido": fecha_pedido,
        "total_precio": total_precio,
        "moneda": moneda,
        "metodo_pago": metodo_pago,
        "estado_financiero": estado_financiero,
        "productos": productos_detalles,
        "created_at": datetime.now().isoformat()
    }
    
    # Guardar pendientes en archivo
    try:
        with open(PENDING_FILE, 'w') as f:
            json.dump(PENDING_ORDERS, f)
    except Exception as e:
        print(f"Error guardando pendientes: {e}")
    
    # Crear el mensaje de notificación con enlace a la página de confirmación
    confirmation_url = f"{request.url_root}confirmar/{order_id}"
    
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
        f"🛒 Productos: {productos}\n\n"
        f"🔄 Para CONFIRMAR este pedido y enviar un correo al cliente, accede a:\n"
        f"{confirmation_url}"
    )
    
    # Enviar el mensaje a todos los números configurados
    resultados = {}
    exito = False
    
    for numero in NUMEROS_NOTIFICACION:
        resultado = enviar_whatsapp(numero, mensaje)
        resultados[numero] = resultado
        if resultado:
            exito = True
        time.sleep(1)
    
    return jsonify({"message": "Notificación enviada", "confirmacion_requerida": True}), 200

@app.route("/confirmar/<order_id>", methods=["GET"])
def pagina_confirmacion(order_id):
    """Página web para confirmar un pedido"""
    if order_id not in PENDING_ORDERS:
        return "Pedido no encontrado o ya procesado", 404
    
    pedido = PENDING_ORDERS[order_id]
    
    # Plantilla HTML para la página de confirmación
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirmar Pedido {{ pedido.numero_orden }}</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background-color: #f9f9f9;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .order-details {
                margin-bottom: 20px;
                padding: 15px;
                background-color: #f5f5f5;
                border-radius: 5px;
            }
            .product-list {
                list-style-type: none;
                padding: 0;
            }
            .product-item {
                padding: 8px 0;
                border-bottom: 1px solid #eee;
            }
            .btn {
                display: inline-block;
                padding: 10px 20px;
                background-color: #4CAF50;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-weight: bold;
                margin-right: 10px;
                text-align: center;
            }
            .btn-confirm {
                background-color: #4CAF50;
            }
            .buttons {
                margin-top: 20px;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Confirmar Pedido</h1>
            
            <div class="order-details">
                <p><strong>Número de Orden:</strong> {{ pedido.numero_orden }}</p>
                <p><strong>Cliente:</strong> {{ pedido.nombre_cliente }}</p>
                <p><strong>Correo:</strong> {{ pedido.correo }}</p>
                <p><strong>Teléfono:</strong> {{ pedido.telefono }}</p>
                <p><strong>Fecha:</strong> {{ pedido.fecha_pedido }}</p>
                <p><strong>Total:</strong> ${{ pedido.total_precio }} {{ pedido.moneda }}</p>
                <p><strong>Método de Pago:</strong> {{ pedido.metodo_pago }}</p>
                <p><strong>Estado:</strong> {{ pedido.estado_financiero }}</p>
                
                <h3>Productos:</h3>
                <ul class="product-list">
                    {% for producto in pedido.productos %}
                    <li class="product-item">{{ producto }}</li>
                    {% endfor %}
                </ul>
            </div>
            
            <div class="buttons">
                <a href="{{ url_root }}procesar-confirmacion/{{ order_id }}" class="btn btn-confirm">✅ Confirmar Pedido</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Renderizar la plantilla con los datos del pedido
    return render_template_string(
        template, 
        pedido=pedido, 
        order_id=order_id,
        url_root=request.url_root
    )

@app.route("/procesar-confirmacion/<order_id>", methods=["GET"])
def procesar_confirmacion(order_id):
    """Procesa la confirmación y envía el correo al cliente"""
    if order_id not in PENDING_ORDERS:
        return "Pedido no encontrado o ya procesado", 404
    
    pedido = PENDING_ORDERS[order_id]
    correo_cliente = pedido["correo"]
    
    if not correo_cliente or correo_cliente == "No disponible":
        return "No se puede procesar: el cliente no tiene correo electrónico", 400
    
    # Crear el mensaje HTML para el correo
    mensaje_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #f8f9fa; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .footer {{ background-color: #f8f9fa; padding: 10px; text-align: center; font-size: 12px; }}
            .important {{ font-weight: bold; color: #d9534f; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>¡Gracias por tu compra!</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{pedido['nombre_cliente']}</strong>,</p>
                <p>Hemos recibido tu pedido <strong>{pedido['numero_orden']}</strong> con éxito.</p>
                <p class="important">Para proceder con tu orden, necesitamos que nos envíes el comprobante de pago (boucher) vía WhatsApp al siguiente número:</p>
                <p style="font-size: 24px; text-align: center; margin: 20px 0;"><strong>{NUMERO_BOUCHER}</strong></p>
                <p>Por favor menciona tu número de orden <strong>{pedido['numero_orden']}</strong> al enviarnos el comprobante.</p>
                <p>Resumen de tu pedido:</p>
                <ul>
                    <li>Fecha: {pedido['fecha_pedido']}</li>
                    <li>Total: ${pedido['total_precio']} {pedido['moneda']}</li>
                    <li>Método de pago: {pedido['metodo_pago']}</li>
                </ul>
                <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
                <p>¡Gracias por tu preferencia!</p>
            </div>
            <div class="footer">
                <p>Este es un correo automático, por favor no respondas a este mensaje.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Enviar el correo
    exito_correo = enviar_correo(
        correo_cliente, 
        f"Confirmación de pedido {pedido['numero_orden']} - Envío de comprobante",
        mensaje_html
    )
    
    # Mover de pendientes a procesados
    if exito_correo:
        PROCESSED_ORDERS.add(order_id)
        if order_id in PENDING_ORDERS:
            del PENDING_ORDERS[order_id]
            
        # Guardar archivos actualizados
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(list(PROCESSED_ORDERS), f)
            with open(PENDING_FILE, 'w') as f:
                json.dump(PENDING_ORDERS, f)
        except Exception as e:
            print(f"Error guardando archivos: {e}")
        
        # Notificar a los administradores
        mensaje_confirmacion = (
            f"✅ PEDIDO CONFIRMADO ✅\n\n"
            f"Se ha enviado correo de confirmación al cliente para la orden {pedido['numero_orden']}.\n"
            f"Cliente: {pedido['nombre_cliente']}\n"
            f"Correo: {pedido['correo']}\n"
            f"Total: ${pedido['total_precio']} {pedido['moneda']}"
        )
        
        for numero in NUMEROS_NOTIFICACION:
            enviar_whatsapp(numero, mensaje_confirmacion)
            time.sleep(1)
        
        return """
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Pedido Confirmado</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f8f9fa;
                    text-align: center;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #4CAF50;
                }
                .icon {
                    font-size: 72px;
                    margin-bottom: 20px;
                }
                a {
                    display: inline-block;
                    margin-top: 20px;
                    color: #007bff;
                    text-decoration: none;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">✅</div>
                <h1>¡Pedido Confirmado!</h1>
                <p>Se ha enviado un correo electrónico al cliente solicitando el comprobante de pago.</p>
                <p>Los administradores han sido notificados.</p>
                <a href="/">Volver al inicio</a>
            </div>
        </body>
        </html>
        """
    else:
        return """
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Error al Confirmar</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f8f9fa;
                    text-align: center;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #dc3545;
                }
                .icon {
                    font-size: 72px;
                    margin-bottom: 20px;
                }
                a {
                    display: inline-block;
                    margin-top: 20px;
                    color: #007bff;
                    text-decoration: none;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">❌</div>
                <h1>Error al Confirmar</h1>
                <p>Hubo un problema al enviar el correo electrónico al cliente.</p>
                <p>Verifica la configuración de correo electrónico e intenta nuevamente.</p>
                <a href="/confirmar/{order_id}">Volver a intentar</a>
            </div>
        </body>
        </html>
        """

@app.route("/", methods=["GET"])
def health_check():
    """Endpoint de verificación de salud"""
    return jsonify({
        "status": "ok", 
        "message": "El servidor de notificaciones está funcionando correctamente",
        "numeros_configurados": NUMEROS_NOTIFICACION,
        "pendientes": len(PENDING_ORDERS),
        "procesados": len(PROCESSED_ORDERS)
    })

if __name__ == "__main__":
    # Usa el puerto asignado por Railway o 5000 por defecto
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)