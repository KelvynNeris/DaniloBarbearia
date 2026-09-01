import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


class Conexao:
    @staticmethod
    def conectar():
        required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise RuntimeError(
                "Variáveis de ambiente do banco ausentes: " + ", ".join(missing)
            )

        mydb = mysql.connector.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            port=int(os.getenv("DB_PORT", "3306")),
        )

        return mydb