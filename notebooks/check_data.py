import psycopg2
from dotenv import load_dotenv
import os
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_database():
    """Verifica os dados carregados no banco de dados."""
    logger.info("Iniciando verificação do banco de dados...")
    load_dotenv()
    
    try:
        # Conectar ao banco
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        conn.set_client_encoding('UTF8')
        
        # Criar cursor
        cur = conn.cursor()
        
        # Verificar tabelas
        logger.info("Verificando tabelas...")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = cur.fetchall()
        logger.info(f"Tabelas encontradas: {[table[0] for table in tables]}")
        
        # Verificar contagem de registros
        logger.info("Verificando contagem de registros...")
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cur.fetchone()[0]
            logger.info(f"Tabela {table[0]}: {count} registros")
        
        # Verificar top 5 fabricantes
        logger.info("Verificando top 5 fabricantes...")
        cur.execute("""
            SELECT manufacturer, COUNT(*) as total 
            FROM cars 
            GROUP BY manufacturer 
            ORDER BY total DESC 
            LIMIT 5
        """)
        top_manufacturers = cur.fetchall()
        logger.info("Top 5 fabricantes:")
        for manufacturer, count in top_manufacturers:
            logger.info(f"  {manufacturer}: {count}")
        
        # Verificar estatísticas básicas
        logger.info("Verificando estatísticas básicas...")
        cur.execute("""
            SELECT 
                COUNT(*) as total_cars,
                AVG(price) as avg_price,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(year) as avg_year,
                AVG(odometer) as avg_odometer
            FROM cars
        """)
        stats = cur.fetchone()
        logger.info(f"Estatísticas gerais:")
        logger.info(f"  Total de carros: {stats[0]}")
        logger.info(f"  Preço médio: {stats[1]:.2f}")
        logger.info(f"  Preço mínimo: {stats[2]}")
        logger.info(f"  Preço máximo: {stats[3]}")
        logger.info(f"  Ano médio: {stats[4]:.1f}")
        logger.info(f"  Quilometragem média: {stats[5]:.1f}")
        
        # Fechar conexão
        cur.close()
        conn.close()
        
        logger.info("Verificação concluída com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao verificar banco de dados: {str(e)}")
        return False

if __name__ == "__main__":
    check_database() 