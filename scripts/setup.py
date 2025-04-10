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
import venv
from pathlib import Path

def create_venv():
    """Cria um ambiente virtual Python."""
    print("Criando ambiente virtual...")
    venv_path = Path("venv")
    if venv_path.exists():
        print("Ambiente virtual já existe.")
        return
    
    venv.create(venv_path, with_pip=True)
    print("Ambiente virtual criado com sucesso.")

def get_python_path():
    """Retorna o caminho do executável Python do ambiente virtual."""
    if sys.platform == "win32":
        return Path("venv/Scripts/python.exe")
    return Path("venv/bin/python")

def install_requirements():
    """Instala as dependências do projeto."""
    print("Instalando dependências...")
    python_path = get_python_path()
    subprocess.run([str(python_path), "-m", "pip", "install", "-r", "requirements.txt"])
    print("Dependências instaladas com sucesso.")

def setup_database():
    """Configura os bancos de dados de desenvolvimento e teste."""
    print("Configurando bancos de dados...")
    python_path = get_python_path()
    
    # Executa as migrações para o banco de desenvolvimento
    subprocess.run([
        str(python_path), 
        "scripts/run_migration.py",
        "--env", "dev"
    ])
    
    # Executa as migrações para o banco de teste
    subprocess.run([
        str(python_path),
        "scripts/run_migration.py",
        "--env", "test"
    ])
    
    print("Bancos de dados configurados com sucesso.")

def main():
    """Função principal."""
    try:
        create_venv()
        install_requirements()
        setup_database()
        print("\nSetup concluído com sucesso!")
        print("\nPara ativar o ambiente virtual:")
        if sys.platform == "win32":
            print("    .\\venv\\Scripts\\activate")
        else:
            print("    source venv/bin/activate")
            
    except Exception as e:
        print(f"Erro durante o setup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 