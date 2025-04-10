import os
import subprocess
from pathlib import Path

def main():
    """Função principal para executar o dashboard"""
    try:
        # Criar diretório de logs se não existir
        Path("logs").mkdir(exist_ok=True)
        
        # Criar diretório de dados processados se não existir
        Path("data/processed").mkdir(parents=True, exist_ok=True)
        
        # Executar o dashboard
        subprocess.run(["streamlit", "run", "scripts/market_dashboard.py"], check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar o dashboard: {e}")
    except Exception as e:
        print(f"Erro inesperado: {e}")

if __name__ == "__main__":
    main() 