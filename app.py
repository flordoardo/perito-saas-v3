import streamlit as st
import pdfplumber
import google.generativeai as genai
import json
from docxtpl import DocxTemplate, InlineImage
from docx import Document
from docx.shared import Cm, Pt, RGBColor
import io
import os
from datetime import datetime, timedelta
import pandas as pd
from streamlit_option_menu import option_menu

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="PeritoSaaS Pro", page_icon="⚖️", layout="wide")

# --- ESTILOS CSS (DARK PROFESSIONAL) ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; }
    /* Ajuste para os cards do Dashboard ficarem bonitos */
    div.stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def garantir_template_padrao():
    if not os.path.exists("template_padrao.docx"):
        doc = Document()
        for section in doc.sections:
            section.top_margin = Cm(3); section.bottom_margin = Cm(2)
            section.left_margin = Cm(3); section.right_margin = Cm(2)
        doc.add_paragraph('{{ cabecalho_imagem }}')
        doc.add_heading('PETIÇÃO', 0)
        doc.add_paragraph('Exmo. Juiz da {{vara}}')
        doc.add_paragraph('Proc. {{numero_processo}}')
        doc.add_paragraph('Autor: {{autor}} | Réu: {{reu}}')
        doc.add_paragraph('\n{{ corpo_peticao }}')
        doc.add_paragraph('\nBelém, {{ data_atual }}.')
        doc.add_paragraph('\n___________________________\n{{ nome_perito }}\nPerito')
        doc.save("template_padrao.docx")

def calcular_prazo_uteis(data_inicio, dias):
    dias_uteis = 0
    data_atual = data_inicio
    while dias_uteis < dias:
        data_atual += timedelta(days=1)
        if data_atual.weekday() < 5: 
            dias_uteis += 1
    return data_atual

# --- CABEÇALHO ---
api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("⚠️ API Key não configurada. Configure no Railway.")
    st.stop()

# --- MENU DE NAVEGAÇÃO ---
selected = option_menu(
    menu_title=None, 
    options=["Gerador de Aceite", "Extrator de Quesitos", "Calculadora de Prazos", "Dashboard de Gestão"], 
    icons=["file-text", "list-check", "calendar-event", "kanban"], 
    default_index=0, 
    orientation="horizontal",
    styles={
        "container": {"padding": "5px", "background-color": "#262730"},
        "icon": {"color": "#ffffff", "font-size": "20px"}, 
        "nav-link": {"font-size": "15px", "text-align": "center", "margin": "0px", "color": "#ffffff"},
        "nav-link-selected": {"background-color": "#4e91d6"}, 
    }
)
st.markdown("---")

# ==============================================================================
# OPÇÃO 1: GERADOR DE ACEITE
# ==============================================================================
if selected == "Gerador de Aceite":
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📄 Gerar Petição de Aceite")
        uploaded_file_aceite = st.file_uploader("PDF da Nomeação", type="pdf", key="pdf_aceite")
    
    with col2:
        st.info("Configuração")
        tipo_modelo = st.radio("Modelo:", ("Padrão do Sistema", "Meu Modelo (.docx)"))
        arquivo_modelo = None
        if tipo_modelo == "Meu Modelo (.docx)":
            arquivo_modelo = st.file_uploader("Seu Modelo .docx", type="docx", key="modelo_docx")
    
    if uploaded_file_aceite and st.button("🚀 Processar Documento", type="primary"):
        with st.spinner("Lendo processo..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                with pdfplumber.open(uploaded_file_aceite) as pdf:
                    texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                
                prompt = f"""
                Extraia do texto jurídico abaixo em JSON:
                {{
                    "numero_processo": "...", "autor": "...", "reu": "...", "vara": "...",
                    "texto_aceite": "Escreva um parágrafo formal de aceitação."
                }}
                Texto: {texto[:10000]}
                """
                resp = model.generate_content(prompt)
                texto_limpo = resp.text.replace("```json", "").replace("```", "").strip()
                st.session_state.dados_aceite = json.loads(texto_limpo)
                st.success("Leitura Concluída!")
            except Exception as e:
                st.error(f"Erro: {e}")

    if 'dados_aceite' in st.session_state:
        st.divider()
        d = st.session_state.dados_aceite
        col1, col2 = st.columns(2)
        proc = col1.text_input("Processo", d.get("numero_processo"), key="p1")
        vara = col2.text_input("Vara", d.get("vara"), key="v1")
        texto = st.text_area("Texto do Aceite", d.get("texto_aceite"), height=100)
        
        if st.button("💾 Baixar Documento Final (.docx)"):
            garantir_template_padrao()
            template_final = arquivo_modelo if arquivo_modelo else "template_padrao.docx"
            doc = DocxTemplate(template_final)
            ctx = {"numero_processo": proc, "vara": vara, "corpo_peticao": texto, "data_atual": datetime.now().strftime("%d/%m/%Y"), "nome_perito": "Dr. Perito"}
            doc.render(ctx)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("Clique para Download", bio.getvalue(), "Aceite.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="primary")

# ==============================================================================
# OPÇÃO 2: EXTRATOR DE QUESITOS (MODO CIRÚRGICO)
# ==============================================================================
if selected == "Extrator de Quesitos":
    st.subheader("❓ Extrair Quesitos das Partes")
    st.info("Leitura integral do arquivo. Pode levar alguns segundos.")
    
    uploaded_file_quesitos = st.file_uploader("PDF com os Quesitos", type="pdf", key="pdf_quesitos")
    
    if uploaded_
