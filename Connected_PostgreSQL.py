import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class SQL:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                dbname=os.getenv("PG_DB"),
                user=os.getenv("PG_USER"),
                password=os.getenv("PG_PASS"),
                host=os.getenv("PG_HOST"),
                port=os.getenv("PG_PORT")
            )
            self._init_tables()
        except psycopg2.Error as e:
            print("Error al conectar a la base de datos:", e)
            self.conn = None

    def _init_tables(self):
        """Crea la tabla LogsESP si no existe."""
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public."LogsESP" (
                log_id        SERIAL PRIMARY KEY,
                esp_id        TEXT    NOT NULL,
                dato_temp     REAL    NOT NULL,
                dato_hum      REAL    NOT NULL,
                dato_button   INTEGER NOT NULL,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()
        cur.close()

    def insert(self, data):
        """Inserta un registro separando columnas."""
        if not self.conn:
            print("No hay conexión activa.")
            return

        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO public."LogsESP" (esp_id, dato_temp, dato_hum, dato_button)
                VALUES (%s, %s, %s, %s);
            """, (
                data["id"],
                data["dato_temp"],
                data["dato_hum"],
                data["dato_button"]
            ))
            self.conn.commit()
            cur.close()
        except psycopg2.Error as e:
            print("Error al insertar datos:", e)

    def close(self):
        if self.conn:
            self.conn.close()

    def reset_table(self):
        if self.conn is None:
            print("No hay conexión activa.")
            return
        try:
            cur = self.conn.cursor()
            cur.execute('DELETE FROM public."logsESP";')
            self.conn.commit()
            cur.close()
            print("Tabla reseteada con éxito.")
        except psycopg2.Error as e:
            print("Error al resetear la tabla:", e)