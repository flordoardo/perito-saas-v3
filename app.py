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
    
    if uploaded_file_quesitos and st.button("🔍 Localizar e Transcrever"):
        with st.spinner("Lendo documento inteiro..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                
                with pdfplumber.open(uploaded_file_quesitos) as pdf:
                    texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                
                prompt = f"""
                Atue como Assistente Técnico. Transcreva ÍPSIS LITTERIS (exatamente como está) os quesitos.
                JSON:
                {{
                    "quesitos_autor": ["1. ..."],
                    "quesitos_reu": ["1. ..."],
                    "quesitos_juizo": ["1. ..."]
                }}
                TEXTO: {texto}
                """
                resp = model.generate_content(prompt)
                texto_limpo = resp.text.replace("```json", "").replace("```", "").strip()
                st.session_state.quesitos = json.loads(texto_limpo)
                st.success("Quesitos localizados!")
            except Exception as e:
                st.error(f"Erro: {e}")

    if 'quesitos' in st.session_state:
        q = st.session_state.quesitos
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            st.markdown("### Do Autor")
            st.text_area("Quesitos Autor", "\n\n".join(q.get("quesitos_autor", [])), height=300)
        with col_q2:
            st.markdown("### Do Réu")
            st.text_area("Quesitos Réu", "\n\n".join(q.get("quesitos_reu", [])), height=300)
            
        if st.button("💾 Baixar Laudo Pré-Preenchido"):
            doc = Document()
            doc.add_heading("LAUDO PERICIAL", 0)
            doc.add_heading("1. QUESITOS DO AUTOR", level=1)
            for item in q.get("quesitos_autor", []):
                doc.add_paragraph(item)
                doc.add_paragraph("RESPOSTA: _______________________")
            doc.add_heading("2. QUESITOS DO RÉU", level=1)
            for item in q.get("quesitos_reu", []):
                doc.add_paragraph(item)
                doc.add_paragraph("RESPOSTA: _______________________")
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("Download Laudo", bio.getvalue(), "Laudo_Quesitos.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="primary")

# ==============================================================================
# OPÇÃO 3: CALCULADORA DE PRAZOS
# ==============================================================================
if selected == "Calculadora de Prazos":
    st.subheader("🗓️ Calculadora de Prazos")
    col1, col2, col3 = st.columns([1,1,2])
    with col1:
        data_inicio = st.date_input("Data da Intimação")
    with col2:
        dias_prazo = st.number_input("Dias Úteis", value=15, step=5)
    
    st.markdown("###")
    if st.button("Calcular Vencimento", type="primary"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        vencimento = calcular_prazo_uteis(dt_inicio, dias_prazo)
        st.success(f"Prazo vence em: {vencimento.strftime('%d/%m/%Y')} ({vencimento.strftime('%A')})")

# ==============================================================================
# OPÇÃO 4: DASHBOARD DE GESTÃO (RAIO-X TURBINADO)
# ==============================================================================
if selected == "Dashboard de Gestão":
    st.subheader("🔍 Dashboard de Gestão do Processo")
    st.info("Suba os autos completos. A IA vai identificar NOMEAÇÕES, QUESITOS e INTIMAÇÕES e criar tarefas.")
    
    uploaded_file_integral = st.file_uploader("Suba o PDF Completo dos Autos", type="pdf", key="pdf_integral")
    
    if uploaded_file_integral and st.button("🚀 Analisar Autos", type="primary"):
        with st.spinner("Analisando todas as páginas..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                
                with pdfplumber.open(uploaded_file_integral) as pdf:
                    texto_paginado = ""
                    for i, page in enumerate(pdf.pages):
                        txt = page.extract_text()
                        if txt: texto_paginado += f"--- PAGINA {i+1} ---\n{txt}\n"
                
                # Prompt Específico para gerar a Lista de Tarefas
                prompt = f"""
                Analise os autos e identifique eventos que exigem ação do perito.
                Classifique cada evento em uma destas categorias:
                - NOMEACAO (Quando o perito é nomeado)
                - QUESITOS (Quando uma parte apresenta perguntas)
                - INTIMACAO (Quando há uma ordem judicial com prazo)
                
                Retorne JSON:
                {{
                    "resumo": "Resumo do caso...",
                    "tarefas": [
                        {{
                            "tipo": "NOMEACAO",
                            "titulo": "Nomeação do Perito",
                            "data": "dd/mm/aaaa",
                            "pagina": "45",
                            "descricao": "Juiz nomeou e pediu aceite.",
                            "conteudo_relevante": "Copie o texto da decisão..."
                        }},
                        {{
                            "tipo": "QUESITOS",
                            "titulo": "Quesitos do Autor",
                            "data": "dd/mm/aaaa",
                            "pagina": "52",
                            "descricao": "Autor apresentou perguntas.",
                            "conteudo_relevante": "Copie as perguntas..."
                        }}
                    ]
                }}
                TEXTO: {texto_paginado}
                """
                
                resp = model.generate_content(prompt)
                texto_limpo = resp.text.replace("```json", "").replace("```", "").strip()
                st.session_state.dashboard_dados = json.loads(texto_limpo)
                st.success("Análise completa!")

            except Exception as e:
                st.error(f"Erro: {e}")

    # --- RENDERIZAÇÃO DOS CARDS ---
    if 'dashboard_dados' in st.session_state:
        dados = st.session_state.dashboard_dados
        st.divider()
        st.markdown(f"**Resumo:** {dados.get('resumo', 'N/D')}")
        
        tarefas = dados.get("tarefas", [])
        if not tarefas:
            st.warning("Nenhuma tarefa encontrada.")
        
        for i, tarefa in enumerate(tarefas):
            with st.container():
                # Cores e Ícones
                cor = "#4e91d6" # Azul padrão
                icon = "📌"
                if tarefa['tipo'] == 'NOMEACAO': cor="#28a745"; icon="📄"
                if tarefa['tipo'] == 'QUESITOS': cor="#ffc107"; icon="❓"
                if tarefa['tipo'] == 'INTIMACAO': cor="#dc3545"; icon="⏰"
                
                # HTML do Card
                st.markdown(f"""
                <div style="background-color: #262730; padding: 15px; border-radius: 8px; border-left: 5px solid {cor}; margin-bottom: 15px;">
                    <h4 style="color:white; margin:0;">{icon} {tarefa['titulo']} <span style="font-size:0.8em; opacity:0.7;">(Pág. {tarefa['pagina']})</span></h4>
                    <p style="color:#ddd; margin:5px 0 0 0;">{tarefa['descricao']}</p>
                    <p style="color:#aaa; font-size:0.8em; margin:0;">Data Ref: {tarefa['data']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Botões de Ação para cada Card
                col_btn, col_vazio = st.columns([1, 3])
                
                if tarefa['tipo'] == 'NOMEACAO':
                    doc = Document()
                    doc.add_heading("PETIÇÃO DE ACEITE", 0)
                    doc.add_paragraph(f"Ref. Decisão da Pág. {tarefa['pagina']}")
                    doc.add_paragraph("Excelentíssimo Juiz,\n\nVenho aceitar o encargo...")
                    bio = io.BytesIO(); doc.save(bio)
                    col_btn.download_button(f"⬇️ Baixar Aceite", bio.getvalue(), f"Aceite_{i}.docx", key=f"dl_{i}")

                elif tarefa['tipo'] == 'QUESITOS':
                    doc = Document()
                    doc.add_heading("RESPOSTA AOS QUESITOS", 0)
                    doc.add_paragraph(tarefa.get('conteudo_relevante', ''))
                    doc.add_paragraph("\nRESPOSTA:\n__________________")
                    bio = io.BytesIO(); doc.save(bio)
                    col_btn.download_button(f"⬇️ Baixar Resposta", bio.getvalue(), f"Quesitos_{i}.docx", key=f"dl_{i}")

                elif tarefa['tipo'] == 'INTIMACAO':
                    dias = col_btn.number_input("Prazo (dias úteis)", value=15, key=f"prazo_{i}")
                    if col_btn.button("Calcular Vencimento", key=f"calc_{i}"):
                        hoje = datetime.now()
                        venc = calcular_prazo_uteis(hoje, dias)
                        st.toast(f"Vencimento: {venc.strftime('%d/%m/%Y')}", icon="📅")
