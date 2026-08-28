import mysql.connector

class Conexao:

    def conectar():
        mydb = mysql.connector.connect(
            user="root",
            password="988430466",
            host="localhost",
            database="bd_barbearia"
        )
        
        return mydb