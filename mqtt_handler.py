import os
from dotenv import load_dotenv
import json
import threading
import paho.mqtt.client as mqtt
from Connected_PostgreSQL import SQL
from Crypto import Crypto
load_dotenv()

class MQTTClientHandler:
    def __init__(
        self,
        broker=os.getenv("broker"),
        topic_sub=os.getenv("topic_sub"),
        topic_pub=os.getenv("topic_pub"),
        passphrase=os.getenv("passphrase")
    ):
        self.broker = broker
        self.port = 1883
        self.topic_sub = topic_sub
        self.topic_pub = topic_pub
        self.last_message = None

        # instancia de BD y crea tabla
        self.db = SQL()

        # instancia de Crypto para encriptar/desencriptar
        self.crypto = Crypto(passphrase)

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_message = self.on_message
        self.connected = False

    def on_message(self, client, userdata, msg):
        try:
            raw = msg.payload  # bytes recibidos (IV + ciphertext)
            # Desencriptar antes de parsear
            texto = self.crypto.decrypt(raw)
            print(f"Mensaje desencriptado en {msg.topic}: {texto}")

            data = json.loads(texto)
            # esperamos claves: "id", "dato_temp", "dato_hum", "dato_button"
            self.db.insert(data)
            self.last_message = texto
        except Exception as e:
            print("Error procesando mensaje MQTT:", e)

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.subscribe(self.topic_sub)
            self.connected = True
            print(f"Conectado a {self.broker}:{self.port}")
            print(f"Suscrito a '{self.topic_sub}'")
        except Exception as e:
            print(f"Error de conexión: {e}")

    def start(self):
        self.connect()
        thread = threading.Thread(target=self.client.loop_forever)
        thread.daemon = True
        thread.start()

    def publish(self, message, topic=None):
        """
        Publica `message` (dict o str) en `topic` si se pasa,
        o en self.topic_pub por defecto. Se encripta automáticamente.
        """
        if not self.connected:
            print("No conectado al broker.")
            return

        destino = topic if topic is not None else self.topic_pub
        # Preparamos el payload: si es dict, lo convertimos a JSON
        if isinstance(message, dict):
            texto = json.dumps(message)
        else:
            texto = str(message)
        # Encriptar
        cifrado = self.crypto.encrypt(texto)
        # Publicar bytes encriptados
        self.client.publish(destino, cifrado)
        print(f"Publicado mensaje cifrado en '{destino}'")

    def get_last_message(self):
        return self.last_message