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

# --- CSS E LAYOUT ---
st.markdown("""
<style>
    .block-container { padding-top: 4rem !important; padding-bottom: 5rem; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stButton > button { width: 100%; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE TEMPLATES (GERADORES) ---
def criar_template_aceite():
    doc = Document()
    for s in doc.sections: s.top_margin = Cm(3); s.bottom_margin = Cm(2); s.left_margin = Cm(3); s.right_margin = Cm(2)
    doc.add_heading('PETIÇÃO DE ACEITE', 0)
    doc.add_paragraph('Excelentíssimo Senhor Doutor Juiz de Direito da {{vara}}')
    doc.add_paragraph('\nProcesso nº: {{numero_processo}}')
    doc.add_paragraph('Autor: {{autor}}')
    doc.add_paragraph('Réu: {{reu}}')
    doc.add_paragraph('\n{{ nome_perito }}, perito nomeado nos autos em epígrafe, vem, respeitosamente, perante Vossa Excelência, ACEITAR o honroso encargo para o qual foi designado.')
    doc.add_paragraph('\nRequer a juntada de seus dados bancários e contatos profissionais em anexo.')
    doc.add_paragraph('\nNestes termos,\nPede deferimento.')
    doc.add_paragraph('\nBelém, {{ data_atual }}.')
    doc.add_paragraph('\n___________________________\n{{ nome_perito }}\nPerito do Juízo')
    return doc

def criar_template_honorarios():
    doc = Document()
    doc.add_heading('PROPOSTA DE HONORÁRIOS', 0)
    doc.add_paragraph('Excelentíssimo Juiz da {{vara}}')
    doc.add_paragraph('Processo: {{numero_processo}}')
    doc.add_paragraph('\nO Perito vem apresentar sua estimativa de honorários baseada na complexidade do trabalho:')
    doc.add_paragraph('\n1. Vistoria Técnica: {{horas_vistoria}} horas')
    doc.add_paragraph('2. Análise Documental: {{horas_analise}} horas')
    doc.add_paragraph('3. Redação do Laudo: {{horas_redacao}} horas')
    doc.add_paragraph('TOTAL DE HORAS ESTIMADAS: {{total_horas}}h')
    doc.add_paragraph('\nValor da Hora Técnica: R$ {{valor_hora}}')
    doc.add_paragraph('VALOR TOTAL DOS HONORÁRIOS: R$ {{valor_total}}')
    doc.add_paragraph('\nNestes termos,\nPede deferimento.')
    doc.add_paragraph('\n{{ nome_perito }}')
    return doc

# --- FUNÇÃO DE DATA ---
def calcular_prazo_uteis(data_inicio, dias):
    dias_uteis = 0
    data_atual = data_inicio
    while dias_uteis < dias:
        data_atual += timedelta(days=1)
        if data_atual.weekday() < 5: 
            dias_uteis += 1
    return data_atual

# --- SETUP API ---
api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("⚠️ API Key não configurada.")
    st.stop()

# --- MENU ---
selected = option_menu(
    menu_title=None, 
    options=["Dashboard de Processos", "Ferramentas Manuais"], 
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
# DASHBOARD (O CÉREBRO)
# ==============================================================================
if selected == "Dashboard de Processos":
    st.markdown("### 🗂️ Análise de Autos")
    st.markdown("O sistema identificará **Nomeações**, **Quesitos** e **Intimações** e oferecerá a ferramenta certa.")
    
    uploaded_file_integral = st.file_uploader("📂 Suba o PDF Completo", type="pdf", key="pdf_integral")
    
    if uploaded_file_integral and st.button("🔍 Analisar Autos", type="primary"):
        with st.spinner("Lendo o processo inteiro (isso pode levar um minuto)..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                
                with pdfplumber.open(uploaded_file_integral) as pdf:
                    texto_paginado = ""
                    for i, page in enumerate(pdf.pages):
                        txt = page.extract_text()
                        if txt: texto_paginado += f"--- PÁGINA {i+1} ---\n{txt}\n"
                
                # Prompt que recupera a lógica de EXTRAÇÃO DE DADOS e EXTRAÇÃO ÍPSIS LITTERIS
                prompt = f"""
                Atue como Assistente Pericial. Analise o processo e identifique eventos chave.
                
                1. DADOS DO PROCESSO: Extraia Numero, Autor, Réu e Vara.
                2. EVENTOS:
                   - NOMEACAO: Se houve nomeação.
                   - QUESITOS: Se há perguntas das partes (copie-as ÍPSIS LITTERIS).
                   - INTIMACAO: Se há prazo para proposta de honorários ou laudo.
                
                Retorne JSON:
                {{
                    "metadados": {{ "numero": "...", "autor": "...", "reu": "...", "vara": "..." }},
                    "tarefas": [
                        {{
                            "tipo": "NOMEACAO",
                            "pagina": "45",
                            "descricao": "Nomeado para perícia médica."
                        }},
                        {{
                            "tipo": "QUESITOS",
                            "pagina": "52",
                            "descricao": "Quesitos do Autor",
                            "lista_quesitos": ["1. O periciando...", "2. Há nexo..."]
                        }},
                        {{
                            "tipo": "HONORARIOS",
                            "pagina": "60",
                            "descricao": "Intimado para apresentar proposta."
                        }}
                    ]
                }}
                TEXTO: {texto_paginado}
                """
                
                resp = model.generate_content(prompt)
                texto_limpo = resp.text.replace("```json", "").replace("```", "").strip()
                st.session_state.dashboard_dados = json.loads(texto_limpo)
                st.success("Análise concluída!")

            except Exception as e:
                st.error(f"Erro ao analisar: {e}")

    # --- RENDERIZAÇÃO DOS CARDS ---
    if 'dashboard_dados' in st.session_state:
        dados = st.session_state.dashboard_dados
        meta = dados.get("metadados", {})
        
        st.divider()
        # Barra de Status do Processo
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.caption(f"Processo: {meta.get('numero')}")
        col_m2.caption(f"Autor: {meta.get('autor')}")
        col_m3.caption(f"Réu: {meta.get('reu')}")
        
        tarefas = dados.get("tarefas", [])
        if not tarefas: st.warning("Nenhuma pendência encontrada.")
        
        for i, tarefa in enumerate(tarefas):
            with st.container():
                tipo = tarefa['tipo']
                
                # Configuração Visual do Card
                cor = "#ccc"; icon = "📌"; titulo = "Evento"
                if tipo == 'NOMEACAO': cor="#28a745"; icon="✅"; titulo="Nomeação Recebida"
                if tipo == 'QUESITOS': cor="#ffc107"; icon="❓"; titulo="Quesitos Apresentados"
                if tipo == 'HONORARIOS': cor="#17a2b8"; icon="💰"; titulo="Proposta de Honorários"
                
                st.markdown(f"""
                <div style="background-color: #262730; padding: 15px; border-radius: 8px; border-left: 6px solid {cor}; margin-bottom: 15px;">
                    <h4 style="color:white; margin:0;">{icon} {titulo} <span style="font-size:0.7em; opacity:0.8;">(Pág. {tarefa['pagina']})</span></h4>
                    <p style="color:#ddd; margin:5px 0;">{tarefa['descricao']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # --- BOTÕES DE AÇÃO ESPECÍFICOS ---
                col_btn, col_extra = st.columns([1, 2])
                
                # 1. FERRAMENTA: GERAR ACEITE
                if tipo == 'NOMEACAO':
                    if col_btn.button("📄 Gerar Petição de Aceite", key=f"btn_aceite_{i}"):
                        doc = criar_template_aceite() # Cria doc base
                        # Renderiza com dados reais do processo
                        ctx = {
                            "numero_processo": meta.get('numero'),
                            "vara": meta.get('vara'),
                            "autor": meta.get('autor'),
                            "reu": meta.get('reu'),
                            "data_atual": datetime.now().strftime("%d/%m/%Y"),
                            "nome_perito": "Dr. Perito"
                        }
                        
                        # Gambiarra técnica: salvar doc, reabrir com DocxTemplate para renderizar
                        bio_temp = io.BytesIO(); doc.save(bio_temp)
                        doc_tpl = DocxTemplate(bio_temp)
                        doc_tpl.render(ctx)
                        
                        bio_final = io.BytesIO(); doc_tpl.save(bio_final)
                        st.download_button("⬇️ Baixar Aceite.docx", bio_final.getvalue(), "Aceite.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_aceite_{i}")

                # 2. FERRAMENTA: EXTRAIR CADERNO DE QUESITOS (A QUE VOCÊ GOSTAVA)
                elif tipo == 'QUESITOS':
                    if col_btn.button("📝 Extrair Caderno de Quesitos", key=f"btn_quesitos_{i}"):
                        doc = Document()
                        doc.add_heading("CADERNO DE QUESITOS", 0)
                        doc.add_paragraph(f"Referência: Pág. {tarefa['pagina']}")
                        
                        lista = tarefa.get('lista_quesitos', [])
                        if isinstance(lista, list):
                            for q_item in lista:
                                p = doc.add_paragraph()
                                run = p.add_run(str(q_item))
                                run.bold = True
                                doc.add_paragraph("RESPOSTA: ___________________________________________________\n")
                        else:
                            doc.add_paragraph(str(lista))

                        bio = io.BytesIO(); doc.save(bio)
                        st.download_button("⬇️ Baixar Caderno de Quesitos.docx", bio.getvalue(), "Quesitos.docx", key=f"dl_quesitos_{i}")

                # 3. FERRAMENTA: PROPOSTA DE HONORÁRIOS (NOVA)
                elif tipo == 'HONORARIOS':
                    col_extra.caption("Calculadora Rápida:")
                    c1, c2 = col_extra.columns(2)
                    horas = c1.number_input("Total Horas", 10, key=f"hs_{i}")
                    valor = c2.number_input("Valor Hora", 300, key=f"vl_{i}")
                    total = horas * valor
                    c1.markdown(f"**Total: R$ {total:,.2f}**")
                    
                    if col_btn.button("💰 Gerar Proposta", key=f"btn_hon_{i}"):
                        doc = criar_template_honorarios()
                        ctx = {
                            "numero_processo": meta.get('numero'),
                            "vara": meta.get('vara'),
                            "nome_perito": "Dr. Perito",
                            "horas_vistoria": int(horas * 0.4), # Estimativa
                            "horas_analise": int(horas * 0.3),
                            "horas_redacao": int(horas * 0.3),
                            "total_horas": horas,
                            "valor_hora": f"{valor:,.2f}",
                            "valor_total": f"{total:,.2f}"
                        }
                        bio_temp = io.BytesIO(); doc.save(bio_temp)
                        doc_tpl = DocxTemplate(bio_temp)
                        doc_tpl.render(ctx)
                        bio_final = io.BytesIO(); doc_tpl.save(bio_final)
                        st.download_button("⬇️ Baixar Proposta.docx", bio_final.getvalue(), "Proposta_Honorarios.docx", key=f"dl_hon_{i}")

# ==============================================================================
# FERRAMENTAS MANUAIS (SE O DASHBOARD FALHAR OU USUÁRIO QUISER FAZER NA MÃO)
# ==============================================================================
if selected == "Ferramentas Manuais":
    st.subheader("🛠️ Ferramentas Avulsas")
    tab1, tab2 = st.tabs(["Extrair Quesitos (Manual)", "Calculadora Prazos"])
    
    with tab1:
        st.write("Use se quiser extrair quesitos de um arquivo pequeno específico.")
        f = st.file_uploader("PDF Quesitos", type="pdf", key="manual_q")
        if f and st.button("Extrair"):
            # (Código simplificado da versão 2 aqui se necessário)
            st.info("Funcionalidade disponível no Dashboard completo.")

    with tab2:
        d = st.date_input("Data Intimação")
        p = st.number_input("Dias Úteis", 15)
        if st.button("Calcular"):
            v = calcular_prazo_uteis(datetime.combine(d, datetime.min.time()), p)
            st.success(f"Vence em: {v.strftime('%d/%m/%Y')}")
