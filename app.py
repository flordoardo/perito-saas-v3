import streamlit as st
import pdfplumber
import google.generativeai as genai
import json
from docxtpl import DocxTemplate, InlineImage
from docx import Document
from docx.shared import Cm
import io
import os
from datetime import datetime, timedelta
import pandas as pd
from streamlit_option_menu import option_menu

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="PeritoSaaS Pro", page_icon="⚖️", layout="wide")

# --- CSS PARA REMOVER ESPAÇOS BRANCOS EXTRAS E AJUSTAR CORES ---
st.markdown("""
<style>
    /* Remove o espaço branco excessivo no topo */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    /* Ajuste de fontes para parecer mais profissional */
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; }
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
    st.error("⚠️ API Key não configurada.")
    st.stop()

# --- MENU DE NAVEGAÇÃO "DARK PROFESSIONAL" ---
# Este estilo garante contraste: Fundo Escuro + Letra Clara
selected = option_menu(
    menu_title=None, 
    options=["Gerador de Aceite", "Extrator de Quesitos", "Calculadora de Prazos"], 
    icons=["file-text", "list-check", "calendar-event", "search"], 
    default_index=0, 
    orientation="horizontal",
    styles={
        # Fundo do menu: Cinza Escuro (Quase preto) - Sóbrio e legível
        "container": {"padding": "5px", "background-color": "#262730"},
        
        # Ícones: Brancos para contraste
        "icon": {"color": "#ffffff", "font-size": "20px"}, 
        
        # Texto dos links: Branco
        "nav-link": {
            "font-size": "16px", 
            "text-align": "center", 
            "margin": "0px", 
            "color": "#ffffff", 
            "--hover-color": "#3E3F4B" # Um cinza um pouco mais claro ao passar o mouse
        },
        
        # Item Selecionado: Azul Aço (Profissional, nada de vermelho ou laranja)
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

    # Edição e Download
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
    st.info("Dica: A IA agora vai ler o arquivo INTEIRO para buscar cada detalhe. Pode levar alguns segundos a mais.")
    
    uploaded_file_quesitos = st.file_uploader("PDF com os Quesitos", type="pdf", key="pdf_quesitos")
    
    if uploaded_file_quesitos and st.button("🔍 Localizar e Transcrever"):
        with st.spinner("Lendo o processo inteiro (isso pode demorar um pouquinho)..."):
            try:
                genai.configure(api_key=api_key)
                # Flash 1.5 aguenta textos enormes, ideal para ler processos inteiros
                model = genai.GenerativeModel('models/gemini-flash-latest')
                
                with pdfplumber.open(uploaded_file_quesitos) as pdf:
                    # Extração completa sem cortes
                    texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                
                # PROMPT AGRESSIVO NA PRECISÃO
                prompt = f"""
                Atue como um Assistente Técnico Pericial extremamente minucioso.
                
                SUA MISSÃO: Localizar e transcrever ÍPSIS LITTERIS (exatamente como está escrito, palavra por palavra) todos os quesitos (perguntas) formulados pelas partes no texto.
                
                REGRAS OBRIGATÓRIAS:
                1. NÃO RESUMA NADA. Copie a pergunta inteira, mesmo que seja longa.
                2. Se houver quesitos "Iniciais" e "Suplementares", capture todos.
                3. Procure por padrões numéricos (1, 2, 3... ou a, b, c...) após títulos como "Dos Quesitos", "Das Perguntas".
                4. Ignore argumentos jurídicos, foque apenas nas PERGUNTAS numeradas.
                
                Saída estritamente em JSON:
                {{
                    "quesitos_autor": ["1. Texto exato da pergunta 1...", "2. Texto exato da pergunta 2..."],
                    "quesitos_reu": ["1. Texto exato da pergunta 1..."],
                    "quesitos_juizo": []
                }}
                
                TEXTO DO PROCESSO:
                {texto}
                """
                
                resp = model.generate_content(prompt)
                texto_limpo = resp.text.replace("```json", "").replace("```", "").strip()
                q_dados = json.loads(texto_limpo)
                
                st.session_state.quesitos = q_dados
                st.success("Varredura completa! Veja os resultados abaixo.")
                
            except Exception as e:
                st.error(f"Erro na leitura: {e}")

    if 'quesitos' in st.session_state:
        q = st.session_state.quesitos
        
        # Mostra contagem para validar
        qtd_autor = len(q.get("quesitos_autor", []))
        qtd_reu = len(q.get("quesitos_reu", []))
        st.caption(f"Encontrados: {qtd_autor} do Autor | {qtd_reu} do Réu")

        col_q1, col_q2 = st.columns(2)
        with col_q1:
            st.markdown("### 🧑‍⚖️ Autor")
            # Join com duas quebras de linha para ficar mais fácil de ler
            texto_autor = "\n\n".join(q.get("quesitos_autor", []))
            st.text_area("Cópia Fiel", texto_autor, height=400)
            
        with col_q2:
            st.markdown("### 🏢 Réu")
            texto_reu = "\n\n".join(q.get("quesitos_reu", []))
            st.text_area("Cópia Fiel", texto_reu, height=400)
            
        st.divider()
        if st.button("💾 Baixar Laudo Pré-Preenchido (.docx)", type="primary"):
            doc = Document()
            # Estilo básico
            style = doc.styles['Normal']
            font = style.font
            font.name = 'Arial'
            font.size = os.environ.get('DOCX_FONT_SIZE', Cm(0.35)) # Tamanho aprox 12
            
            doc.add_heading("LAUDO PERICIAL", 0)
            
            doc.add_heading("1. QUESITOS DO AUTOR", level=1)
            if not q.get("quesitos_autor"):
                doc.add_paragraph("[Nenhum quesito do autor encontrado]")
            for item in q.get("quesitos_autor", []):
                p = doc.add_paragraph()
                runner = p.add_run(item)
                runner.bold = True
                doc.add_paragraph("RESPOSTA: _______________________________________________________________________\n")
            
            doc.add_heading("2. QUESITOS DO RÉU", level=1)
            if not q.get("quesitos_reu"):
                doc.add_paragraph("[Nenhum quesito do réu encontrado]")
            for item in q.get("quesitos_reu", []):
                p = doc.add_paragraph()
                runner = p.add_run(item)
                runner.bold = True
                doc.add_paragraph("RESPOSTA: _______________________________________________________________________\n")
            
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("Clique para Download", bio.getvalue(), "Laudo_Quesitos.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

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
    
    st.markdown("###") # Espaço
    if st.button("Calcular Vencimento", type="primary"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        vencimento = calcular_prazo_uteis(dt_inicio, dias_prazo)
        
        st.success(f"O prazo vence em:")
        st.markdown(f"<h2 style='color: #4e91d6'>{vencimento.strftime('%d/%m/%Y')}</h2>", unsafe_allow_html=True)
        st.write(f"({vencimento.strftime('%A')})")

# ==============================================================================
# OPÇÃO 4: DASHBOARD DE GESTÃO (ANTIGO RAIO-X)
# ==============================================================================
if selected == "Raio-X Completo":
    st.subheader("🔍 Dashboard de Gestão do Processo")
    st.info("Suba os autos completos. A IA vai identificar as pendências e criar os documentos para cada uma.")
    
    uploaded_file_integral = st.file_uploader("Suba o PDF Completo dos Autos", type="pdf", key="pdf_integral")
    
    # --- PASSO 1: INGESTÃO E ANÁLISE ---
    if uploaded_file_integral and st.button("🚀 Analisar e Montar Dashboard", type="primary"):
        with st.spinner("A IA está lendo o processo e identificando tarefas..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-flash-latest')
                
                with pdfplumber.open(uploaded_file_integral) as pdf:
                    texto_paginado = ""
                    for i, page in enumerate(pdf.pages):
                        texto_extraido = page.extract_text()
                        if texto_extraido:
                            texto_paginado += f"--- PÁGINA {i+1} ---\n{texto_extraido}\n"
                
                # Prompt focado em CLASSIFICAÇÃO para gerar ações
                prompt = f"""
                Analise os autos e identifique eventos que exigem ação do perito.
                Classifique cada evento em uma destas categorias:
                - NOMEACAO (Quando o perito é nomeado)
                - QUESITOS (Quando uma parte apresenta perguntas)
                - INTIMACAO (Quando há uma ordem judicial com prazo)
                - HONORARIOS (Discussão ou depósito de valores)
                
                Retorne JSON:
                {{
                    "resumo": "Resumo do caso...",
                    "tarefas": [
                        {{
                            "tipo": "NOMEACAO",
                            "titulo": "Nomeação do Perito",
                            "data": "dd/mm/aaaa",
                            "pagina": "45",
                            "descricao": "Juiz nomeou e pediu aceite em 5 dias.",
                            "conteudo_relevante": "Copie aqui o trecho da decisão..."
                        }},
                        {{
                            "tipo": "QUESITOS",
                            "titulo": "Quesitos do Autor",
                            "data": "dd/mm/aaaa",
                            "pagina": "52",
                            "descricao": "Autor apresentou 5 perguntas.",
                            "conteudo_relevante": "Copie aqui as perguntas na íntegra..."
                        }}
                    ]
                }}
                TEXTO: {texto_paginado}
                """
                
                resp = model.generate_content(prompt)
                dados = json.loads(resp.text.replace("```json", "").replace("```", "").strip())
                st.session_state.dashboard_dados = dados
                st.success("Análise concluída! Veja suas tarefas abaixo.")

            except Exception as e:
                st.error(f"Erro na análise: {e}")

    # --- PASSO 2: DASHBOARD DE AÇÕES ---
    if 'dashboard_dados' in st.session_state:
        dados = st.session_state.dashboard_dados
        
        st.divider()
        st.markdown(f"**Resumo do Caso:** {dados.get('resumo', 'Sem resumo')}")
        st.markdown("### 📋 Suas Tarefas Identificadas")
        
        # Loop para criar os CARDS (Cartões de Tarefa)
        tarefas = dados.get("tarefas", [])
        
        if not tarefas:
            st.warning("Nenhuma tarefa pericial encontrada nestes autos.")
            
        for i, tarefa in enumerate(tarefas):
            # Cria um container visual (Card) para cada tarefa
            with st.container():
                # Define cor e ícone baseados no tipo
                icon = "📌"
                cor_titulo = "blue"
                if tarefa['tipo'] == 'NOMEACAO': icon = "📄"; cor_titulo="green"
                if tarefa['tipo'] == 'QUESITOS': icon = "❓"; cor_titulo="orange"
                if tarefa['tipo'] == 'INTIMACAO': icon = "⏰"; cor_titulo="red"
                
                st.markdown(f"""
                <div style="background-color: #262730; padding: 15px; border-radius: 10px; border-left: 5px solid {cor_titulo}; margin-bottom: 10px;">
                    <h4 style="color: white; margin:0;">{icon} {tarefa['titulo']} (Pág. {tarefa['pagina']})</h4>
                    <p style="color: #ccc; margin:0;">Data aprox: {tarefa['data']} | {tarefa['descricao']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # --- BOTÕES DE AÇÃO ESPECÍFICOS ---
                col_acoes = st.columns([1, 1, 3])
                
                # AÇÃO 1: NOMEAÇÃO -> GERAR ACEITE
                if tarefa['tipo'] == 'NOMEACAO':
                    if col_acoes[0].button(f"Gerar Petição de Aceite", key=f"btn_aceite_{i}"):
                        doc = Document()
                        doc.add_heading("PETIÇÃO DE ACEITE", 0)
                        doc.add_paragraph(f"Ref. Evento na Pág. {tarefa['pagina']}")
                        doc.add_paragraph("Excelentíssimo Juiz,\n\nVenho aceitar o encargo...\n\n(Texto gerado automaticamente com base na análise)")
                        bio = io.BytesIO()
                        doc.save(bio)
                        st.download_button(
                            label="⬇️ Baixar Aceite.docx",
                            data=bio.getvalue(),
                            file_name=f"Aceite_Pag_{tarefa['pagina']}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"down_aceite_{i}"
                        )

                # AÇÃO 2: QUESITOS -> GERAR LAUDO RESPOSTA
                elif tarefa['tipo'] == 'QUESITOS':
                    if col_acoes[0].button(f"Gerar Resposta (Laudo)", key=f"btn_quesito_{i}"):
                        doc = Document()
                        doc.add_heading("RESPOSTA AOS QUESITOS", 0)
                        doc.add_paragraph(f"Quesitos identificados na Pág. {tarefa['pagina']}")
                        doc.add_paragraph("-" * 20)
                        doc.add_paragraph(tarefa.get('conteudo_relevante', ''))
                        doc.add_paragraph("-" * 20)
                        doc.add_paragraph("\nRESPOSTA DO PERITO:\n_____________________")
                        bio = io.BytesIO()
                        doc.save(bio)
                        st.download_button(
                            label="⬇️ Baixar Resposta.docx",
                            data=bio.getvalue(),
                            file_name=f"Resposta_Quesitos_Pag_{tarefa['pagina']}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"down_quesito_{i}"
                        )
                
                # AÇÃO 3: INTIMAÇÃO -> CALCULAR PRAZO
                elif tarefa['tipo'] == 'INTIMACAO':
                    dias = col_acoes[0].number_input("Prazo (dias úteis)", value=15, key=f"input_dias_{i}")
                    if col_acoes[1].button("Calcular Vencimento", key=f"btn_prazo_{i}"):
                        # Tenta converter a data da IA, se falhar usa hoje
                        try:
                            dt_base = datetime.strptime(tarefa['data'], "%d/%m/%Y")
                        except:
                            dt_base = datetime.now()
                        
                        vencimento = calcular_prazo_uteis(dt_base, dias)
                        st.success(f"Vencimento estimado: {vencimento.strftime('%d/%m/%Y')}")

                st.markdown("---") # Separador visual entre cards
