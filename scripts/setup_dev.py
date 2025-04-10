#!/usr/bin/env python
"""
Script para configurar o ambiente de desenvolvimento do projeto Mobato.
Este script:
1. Cria um ambiente virtual Python
2. Instala as dependências necessárias
3. Configura os bancos de dados de desenvolvimento e teste
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_command(command, cwd=None):
    """Executa um comando e retorna o resultado."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            check=True,
            text=True,
            capture_output=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro ao executar comando: {command}")
        logger.error(f"Erro: {e.stderr}")
        sys.exit(1)

def create_venv():
    """Cria um ambiente virtual Python."""
    logger.info("Criando ambiente virtual...")
    venv_path = Path("venv")
    if venv_path.exists():
        logger.info("Ambiente virtual já existe.")
        return
    
    run_command("python -m venv venv")
    logger.info("Ambiente virtual criado com sucesso.")

def install_dependencies():
    """Instala as dependências do projeto."""
    logger.info("Instalando dependências...")
    
    # Determina o comando pip correto baseado no SO
    pip_cmd = "venv\\Scripts\\pip" if sys.platform == "win32" else "venv/bin/pip"
    
    # Atualiza pip
    run_command(f"{pip_cmd} install --upgrade pip")
    
    # Instala dependências
    run_command(f"{pip_cmd} install -r requirements.txt")
    logger.info("Dependências instaladas com sucesso.")

def setup_database():
    """Configura os bancos de dados de desenvolvimento e teste."""
    logger.info("Configurando bancos de dados...")
    
    # Carrega variáveis de ambiente
    load_dotenv()
    
    # Verifica se as variáveis necessárias estão definidas
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Variáveis de ambiente faltando: {', '.join(missing_vars)}")
        logger.error("Por favor, configure o arquivo .env com as variáveis necessárias.")
        sys.exit(1)
    
    # Cria os bancos de dados
    db_name = os.getenv('DB_NAME', 'mobato_dev')
    test_db_name = f"{db_name}_test"
    
    # Comando para criar os bancos (ajuste conforme necessário)
    create_db_cmd = f"psql -h {os.getenv('DB_HOST')} -p {os.getenv('DB_PORT')} -U {os.getenv('DB_USER')} -c"
    
    # Cria banco de desenvolvimento
    run_command(f'{create_db_cmd} "CREATE DATABASE {db_name};"')
    logger.info(f"Banco de dados {db_name} criado.")
    
    # Cria banco de teste
    run_command(f'{create_db_cmd} "CREATE DATABASE {test_db_name};"')
    logger.info(f"Banco de dados {test_db_name} criado.")
    
    # Executa as migrações
    logger.info("Executando migrações...")
    run_command("python scripts/run_migration.py")
    logger.info("Migrações executadas com sucesso.")

def main():
    """Função principal."""
    logger.info("Iniciando setup do ambiente de desenvolvimento...")
    
    # Cria ambiente virtual
    create_venv()
    
    # Instala dependências
    install_dependencies()
    
    # Configura bancos de dados
    setup_database()
    
    logger.info("Setup concluído com sucesso!")
    logger.info("Para ativar o ambiente virtual:")
    if sys.platform == "win32":
        logger.info("    venv\\Scripts\\activate")
    else:
        logger.info("    source venv/bin/activate")

if __name__ == "__main__":
    main() 