import streamlit as st
import pdfplumber
import google.generativeai as genai
import json
from docxtpl import DocxTemplate
from docx import Document
from docx.shared import Cm, Pt, RGBColor
import io
import os
from datetime import datetime, timedelta
import pandas as pd
from streamlit_option_menu import option_menu

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="PeritoSaaS Pro", page_icon="⚖️", layout="wide")

# --- CORREÇÃO VISUAL DO MENU E ESTILOS ---
st.markdown("""
<style>
    /* Empurra o conteúdo para baixo para não cortar o menu */
    .block-container {
        padding-top: 4rem !important;
        padding-bottom: 5rem;
    }
    /* Esconde o menu 'hambúrguer' e rodapé padrão do Streamlit para limpar a tela */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Estilo dos Cards do Dashboard */
    .stButton > button {
        width: 100%;
        border-radius: 5px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def calcular_prazo_uteis(data_inicio, dias):
    dias_uteis = 0
    data_atual = data_inicio
    while dias_uteis < dias:
        data_atual += timedelta(days=1)
        if data_atual.weekday() < 5: # 0-4 é seg-sex
            dias_uteis += 1
    return data_atual

# --- CABEÇALHO ---
api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("⚠️ API Key não configurada.")
    st.stop()

# --- MENU PRINCIPAL ---
selected = option_menu(
    menu_title=None, 
    options=["Dashboard de Processos", "Ferramentas Rápidas"], 
    icons=["kanban", "tools"], 
    default_index=0, 
    orientation="horizontal",
    styles={
        "container": {"padding": "5px", "background-color": "#262730"},
        "icon": {"color": "#ffffff", "font-size": "20px"}, 
        "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "color": "#ffffff"},
        "nav-link-selected": {"background-color": "#4e91d6"}, 
    }
)

# ==============================================================================
# ABA 1: DASHBOARD (A NOVA CENTRAL DE COMANDO)
# ==============================================================================
if selected == "Dashboard de Processos":
    st.markdown("### 🗂️ Central de Gestão do Processo")
    st.markdown("Suba o PDF integral dos autos. A IA identificará pendências e gerará os documentos necessários.")
    
    uploaded_file_integral = st.file_uploader("📂 Arraste os autos aqui (PDF)", type="pdf", key="pdf_integral")
    
    # --- ÁREA DE ANÁLISE ---
    if uploaded_file_integral and st.button("🔍 Analisar Autos e Gerar Tarefas", type="primary"):
        with st.spinner("Lendo o processo, identificando prazos, quesitos e nomeações..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                
                with pdfplumber.open(uploaded_file_integral) as pdf:
                    texto_paginado = ""
                    # Lendo páginas (limitando visualização no prompt para economizar tokens se for gigante, 
                    # mas o Flash 1.5 aguenta muito)
                    for i, page in enumerate(pdf.pages):
                        txt = page.extract_text()
                        if txt: texto_paginado += f"--- PÁGINA {i+1} ---\n{txt}\n"
                
                # PROMPT DE DASHBOARD
                prompt = f"""
                Atue como um Assistente Jurídico Sênior. Analise o processo e crie uma LISTA DE TAREFAS para o perito.
                
                Identifique APENAS eventos que exigem ação ativa:
                1. NOMEACAO: O juiz nomeou o perito? (Ação: Aceitar)
                2. QUESITOS: Existem perguntas a responder? (Ação: Laudo)
                3. INTIMACAO: Existe prazo correndo ou ordem para iniciar? (Ação: Agendar/Calcular Prazo)
                
                Retorne JSON estrito:
                {{
                    "resumo_caso": "Resumo de 1 linha (ex: Ação Indenizatória - Erro Médico)",
                    "tarefas": [
                        {{
                            "tipo": "NOMEACAO",
                            "titulo": "Nomeação do Perito",
                            "pagina": "45",
                            "data_evento": "dd/mm/aaaa",
                            "descricao": "Juiz nomeou e fixou honorários provisórios.",
                            "dados_para_doc": "Texto da decisão para citar no aceite..."
                        }},
                        {{
                            "tipo": "QUESITOS",
                            "titulo": "Quesitos do Autor",
                            "pagina": "52",
                            "data_evento": "dd/mm/aaaa",
                            "descricao": "Autor apresentou 10 quesitos técnicos.",
                            "dados_para_doc": "Lista exata dos quesitos..."
                        }}
                    ]
                }}
                TEXTO: {texto_paginado}
                """
                
                resp = model.generate_content(prompt)
                texto_limpo = resp.text.replace("```json", "").replace("```", "").strip()
                st.session_state.dashboard_dados = json.loads(texto_limpo)
                st.success("Análise concluída! Veja o Painel de Ações abaixo.")

            except Exception as e:
                st.error(f"Erro ao analisar: {e}")

    # --- RENDERIZAÇÃO DOS CARDS (Painel de Controle) ---
    if 'dashboard_dados' in st.session_state:
        dados = st.session_state.dashboard_dados
        
        st.divider()
        st.info(f"📄 **Resumo do Processo:** {dados.get('resumo_caso', 'Sem resumo')}")
        
        tarefas = dados.get("tarefas", [])
        if not tarefas:
            st.warning("✅ Nenhuma pendência encontrada nestes autos.")
        
        for i, tarefa in enumerate(tarefas):
            # Layout do Card
            with st.container():
                tipo = tarefa['tipo']
                
                # Cores e Ícones semânticos
                cor_borda = "#ccc"
                icon = "📌"
                titulo_doc = "Documento"
                
                if tipo == 'NOMEACAO': 
                    cor_borda = "#28a745" # Verde
                    icon = "✅"
                    titulo_doc = "Aceite do Encargo"
                elif tipo == 'QUESITOS': 
                    cor_borda = "#ffc107" # Amarelo/Laranja
                    icon = "❓"
                    titulo_doc = "Resposta aos Quesitos"
                elif tipo == 'INTIMACAO': 
                    cor_borda = "#dc3545" # Vermelho
                    icon = "⏰"
                    titulo_doc = "Petição de Manifestação"
                
                # Card Visual (HTML/CSS Injetado)
                st.markdown(f"""
                <div style="background-color: #262730; padding: 15px; border-radius: 8px; border-left: 6px solid {cor_borda}; margin-bottom: 10px;">
                    <h4 style="color:white; margin:0;">{icon} {tarefa['titulo']} <span style="font-size:0.7em; opacity:0.8;">(Pág. {tarefa['pagina']})</span></h4>
                    <p style="color:#ddd; margin:5px 0;">{tarefa['descricao']}</p>
                    <small style="color:#aaa;">Data Ref: {tarefa['data_evento']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                # AÇÕES DO CARD
                col_btn, col_extra = st.columns([1, 2])
                
                # Botão de Gerar Documento (Dinâmico conforme o tipo)
                if tipo == 'NOMEACAO':
                    doc = Document()
                    doc.add_heading("PETIÇÃO DE ACEITE", 0)
                    doc.add_paragraph(f"Referência: Decisão da página {tarefa['pagina']}")
                    doc.add_paragraph(f"Resumo da Decisão: {tarefa['descricao']}")
                    doc.add_paragraph("\nExcelentíssimo Senhor Juiz,\n\nO Perito nomeado vem, respeitosamente, ACEITAR o honroso encargo...")
                    doc.add_paragraph("\nNestes termos,\nPede deferimento.")
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    
                    col_btn.download_button(
                        label=f"⬇️ Baixar {titulo_doc}",
                        data=bio.getvalue(),
                        file_name=f"Aceite_Pag_{tarefa['pagina']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_{i}"
                    )
                    
                elif tipo == 'QUESITOS':
                    doc = Document()
                    doc.add_heading("RESPOSTA AOS QUESITOS", 0)
                    doc.add_paragraph(f"Quesitos extraídos da página {tarefa['pagina']}")
                    doc.add_paragraph("-" * 30)
                    # Tenta limpar o texto para não ficar bagunçado
                    texto_quesitos = tarefa.get('dados_para_doc', '').replace("[", "").replace("]", "").replace("', '", "\n")
                    doc.add_paragraph(texto_quesitos)
                    doc.add_paragraph("-" * 30)
                    doc.add_paragraph("\nRESPOSTAS DO PERITO:\n\n(Digite suas respostas aqui...)")
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    
                    col_btn.download_button(
                        label=f"⬇️ Baixar {titulo_doc}",
                        data=bio.getvalue(),
                        file_name=f"Laudo_Quesitos_Pag_{tarefa['pagina']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_{i}"
                    )
                
                elif tipo == 'INTIMACAO':
                    # Para intimações, o perito precisa calcular o prazo ali mesmo
                    dias = col_extra.number_input(f"Prazo (Dias Úteis)", value=15, key=f"prazo_{i}", label_visibility="collapsed")
                    if col_btn.button("Calcular Prazo Fatal", key=f"calc_{i}"):
                        hoje = datetime.now()
                        venc = calcular_prazo_uteis(hoje, dias)
                        col_extra.success(f"Vence em: **{venc.strftime('%d/%m/%Y')}** ({venc.strftime('%A')})")

# ==============================================================================
# ABA 2: FERRAMENTAS RÁPIDAS (AVULSAS)
# ==============================================================================
if selected == "Ferramentas Rápidas":
    st.subheader("🛠️ Utilitários Avulsos")
    
    tab_calc, tab_extra = st.tabs(["🗓️ Calculadora de Prazos", "📝 Extrator Simples"])
    
    with tab_calc:
        col1, col2 = st.columns(2)
        dt_ini = col1.date_input("Data da Intimação")
        dias = col2.number_input("Prazo em Dias Úteis", 15)
        
        if st.button("Calcular Vencimento", key="btn_calc_avulso"):
            dt_full = datetime.combine(dt_ini, datetime.min.time())
            res = calcular_prazo_uteis(dt_full, dias)
            st.success(f"Vencimento: {res.strftime('%d/%m/%Y')}")

    with tab_extra:
        st.write("Use isso se quiser extrair texto de um arquivo pequeno sem rodar o Dashboard completo.")
        file_simple = st.file_uploader("PDF Pequeno", type="pdf")
        if file_simple and st.button("Extrair Texto"):
            with pdfplumber.open(file_simple) as pdf:
                txt = "\n".join([p.extract_text() for p in pdf.pages])
                st.text_area("Texto", txt, height=200)
