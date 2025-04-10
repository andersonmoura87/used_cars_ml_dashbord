from fpdf import FPDF
import os
from pathlib import Path

class PDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Analise do Mercado de Carros Usados', 0, 1, 'C')
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def create_presentation_materials():
    """
    Cria materiais para apresentação do projeto de análise do mercado de carros usados
    """
    # Criar diretório para apresentação
    presentation_dir = Path("presentation")
    presentation_dir.mkdir(exist_ok=True)
    
    # Criar PDF
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Capa
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 24)
    pdf.cell(0, 20, 'Analise do Mercado de Carros Usados', ln=True, align='C')
    pdf.set_font('Helvetica', '', 14)
    pdf.cell(0, 10, 'Uma Abordagem Completa: Da Preparacao dos Dados a Visualizacao', ln=True, align='C')
    
    # Sumário
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Sumario', ln=True)
    pdf.set_font('Helvetica', '', 12)
    sections = [
        "1. Introducao (5 minutos)",
        "2. Preparacao e Limpeza dos Dados (10 minutos)",
        "3. Analise SQL e Insights Iniciais (10 minutos)",
        "4. Analise Estatistica Descritiva (10 minutos)",
        "5. Visualizacoes e Dashboard (8 minutos)",
        "6. Demonstracao do Streamlit (2 minutos)",
        "7. Perguntas e Respostas"
    ]
    for section in sections:
        pdf.cell(0, 10, section, ln=True)
    
    # Seção 1: Introdução
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, '1. Introducao', ln=True)
    pdf.set_font('Helvetica', '', 12)
    intro_points = [
        "* Contextualizacao do Projeto",
        "  - Mercado de carros usados em crescimento",
        "  - Importancia da analise de dados para decisoes",
        "  - Objetivos do projeto",
        "",
        "* Visao Geral dos Dados",
        "  - Fonte dos dados",
        "  - Estrutura inicial",
        "  - Desafios identificados",
        "",
        "* Metodologia",
        "  - Abordagem ETL",
        "  - Ferramentas utilizadas",
        "  - Pipeline de analise"
    ]
    for point in intro_points:
        pdf.cell(0, 8, point, ln=True)
    
    # Seção 2: Preparação dos Dados
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, '2. Preparacao e Limpeza dos Dados', ln=True)
    pdf.set_font('Helvetica', '', 12)
    prep_points = [
        "* Analise Exploratoria Inicial",
        "  - Identificacao de valores ausentes",
        "  - Deteccao de anomalias",
        "  - Consistencia dos dados",
        "",
        "* Processo de Limpeza",
        "  - Tratamento de valores nulos",
        "  - Padronizacao de formatos",
        "  - Remocao de duplicatas",
        "",
        "* Criacao da ABT (Analytical Base Table)",
        "  - Estrutura final dos dados",
        "  - Features criadas",
        "  - Validacoes realizadas"
    ]
    for point in prep_points:
        pdf.cell(0, 8, point, ln=True)
    
    # Seção 3: Análise SQL
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, '3. Analise SQL e Insights Iniciais', ln=True)
    pdf.set_font('Helvetica', '', 12)
    sql_points = [
        "* Consultas Desenvolvidas",
        "  - Preco medio por fabricante",
        "  - Modelos mais anunciados",
        "  - Analise de combustiveis",
        "  - Analise regional",
        "  - Analise de transmissao",
        "",
        "* Insights Principais",
        "  - Padroes de preco",
        "  - Preferencias de mercado",
        "  - Distribuicao geografica",
        "",
        "* Otimizacao das Consultas",
        "  - Indices utilizados",
        "  - Performance"
    ]
    for point in sql_points:
        pdf.cell(0, 8, point, ln=True)
    
    # Seção 4: Análise Estatística
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, '4. Analise Estatistica Descritiva', ln=True)
    pdf.set_font('Helvetica', '', 12)
    stats_points = [
        "* Distribuicao de Precos",
        "  - Medidas de tendencia central",
        "  - Medidas de dispersao",
        "  - Analise de assimetria",
        "",
        "* Analises Bivariadas",
        "  - Correlacao preco x quilometragem",
        "  - Relacao ano x preco",
        "  - Variacao por combustivel",
        "",
        "* Identificacao de Outliers",
        "  - Metodo IQR",
        "  - Impacto nas analises",
        "  - Tratamento aplicado"
    ]
    for point in stats_points:
        pdf.cell(0, 8, point, ln=True)
    
    # Seção 5: Visualizações
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, '5. Visualizacoes e Dashboard', ln=True)
    pdf.set_font('Helvetica', '', 12)
    viz_points = [
        "* Power BI Dashboard",
        "  - Estrutura do dashboard",
        "  - Medidas DAX criadas",
        "  - Interatividade",
        "",
        "* Principais Visualizacoes",
        "  - Box plot de precos",
        "  - Mapa interativo",
        "  - Top fabricantes",
        "  - Analise de combustivel",
        "  - Grafico de dispersao",
        "",
        "* Insights Visuais",
        "  - Padroes identificados",
        "  - Descobertas importantes"
    ]
    for point in viz_points:
        pdf.cell(0, 8, point, ln=True)
    
    # Seção 6: Streamlit
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, '6. Demonstracao do Streamlit', ln=True)
    pdf.set_font('Helvetica', '', 12)
    stream_points = [
        "* Aplicacao Web",
        "  - Estrutura da aplicacao",
        "  - Funcionalidades",
        "  - Interatividade",
        "",
        "* Diferencial do Projeto",
        "  - Acessibilidade dos dados",
        "  - Analises em tempo real",
        "  - Facilidade de uso"
    ]
    for point in stream_points:
        pdf.cell(0, 8, point, ln=True)
    
    # Perguntas e Respostas
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Perguntas Frequentes e Respostas', ln=True)
    pdf.set_font('Helvetica', '', 12)
    qa_points = [
        "1. Por que escolher SQL para as analises iniciais?",
        "R: SQL oferece eficiencia em grandes volumes de dados, facilidade de manipulacao",
        "   e e amplamente utilizado no mercado.",
        "",
        "2. Como foi feita a escolha das visualizacoes no Power BI?",
        "R: As visualizacoes foram selecionadas para maximizar a compreensao dos dados,",
        "   seguindo principios de design de informacao e melhores praticas.",
        "",
        "3. Qual o criterio para identificacao de outliers?",
        "R: Utilizamos o metodo IQR por ser robusto e menos sensivel a extremos,",
        "   alem de ser amplamente aceito na estatistica.",
        "",
        "4. Por que implementar uma aplicacao Streamlit?",
        "R: O Streamlit permite democratizar o acesso aos dados e analises,",
        "   oferecendo interatividade e atualizacoes em tempo real.",
        "",
        "5. Como garantir a qualidade dos dados?",
        "R: Implementamos um pipeline robusto de validacao e limpeza,",
        "   com multiplas camadas de verificacao e documentacao clara."
    ]
    for point in qa_points:
        pdf.cell(0, 8, point, ln=True)
    
    # Salvar PDF
    pdf.output(presentation_dir / "roteiro_apresentacao.pdf", 'F')
    
    print("Materiais de apresentacao gerados com sucesso!")

if __name__ == "__main__":
    create_presentation_materials() 