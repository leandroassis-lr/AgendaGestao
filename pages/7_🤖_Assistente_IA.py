import streamlit as st
import pandas as pd
import utils_chamados
import google.generativeai as genai
from datetime import datetime, timedelta
import json
import re
import time
from fpdf import FPDF
import io

st.set_page_config(page_title="Agente IA", page_icon="🕵️", layout="wide")

utils.load_css()

# --- 1. CSS ---
st.markdown("""
<style>
    .chat-header { padding: 1rem; background-color: #e8f5e9; border-radius: 10px; margin-bottom: 2rem; border-left: 5px solid #2E7D32; }
    .chat-header h2 { margin: 0; color: #1b5e20; font-size: 1.8rem; }
    .stChatMessage { padding: 1rem; border-radius: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIGURAÇÃO API ---
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key: st.error("🔑 Chave GOOGLE_API_KEY ausente."); st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 3. FUNÇÃO GERADORA DE PDF ---
def criar_pdf_chamado(id_chamado):
    df = utils_chamados.carregar_chamados_db()
    dados = df[df['ID'] == id_chamado].iloc[0]
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Cabeçalho
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"Relatório de Chamado: {dados['Nº Chamado']}", ln=True, align='C')
    pdf.ln(10)
    
    # Corpo
    pdf.set_font("Arial", size=12)
    campos_imprimir = {
        "Projeto": dados.get('Projeto', '-'),
        "Agência": dados.get('Nome Agência', '-'),
        "Status": dados.get('Status', '-'),
        "Técnico": dados.get('Técnico', '-'),
        "Data Agendamento": str(dados.get('Agendamento', '-')),
        "Descrição/Obs": dados.get('Observação', '-')
    }
    
    for campo, valor in campos_imprimir.items():
        # Encode latin-1 para aceitar acentos básicos
        texto = f"{campo}: {str(valor)}"
        try:
            pdf.cell(200, 10, txt=texto.encode('latin-1', 'replace').decode('latin-1'), ln=True)
        except:
            pdf.cell(200, 10, txt=f"{campo}: {str(valor)}", ln=True)
            
    # Retorna o binário do PDF
    return pdf.output(dest='S').encode('latin-1')

# --- 4. FUNÇÕES DE BUSCA E AÇÃO ---
def buscar_id_por_numero(numero_chamado_usuario):
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return None
    termo = str(numero_chamado_usuario).strip().upper()
    df['Chamado_Upper'] = df['Nº Chamado'].astype(str).str.strip().str.upper()
    
    filtro = df[df['Chamado_Upper'] == termo]
    if filtro.empty: filtro = df[df['Chamado_Upper'].str.contains(termo, regex=False)]
    if filtro.empty:
        for index, row in df.iterrows():
            if row['Chamado_Upper'] in termo and len(row['Chamado_Upper']) > 3:
                return int(row['ID'])
    if not filtro.empty: return int(filtro.iloc[0]['ID'])
    return None

def executar_comando_ia(comando_json):
    try:
        dados = json.loads(comando_json)
        acao = dados.get("acao")
        num_chamado = dados.get("chamado")
        id_banco = buscar_id_por_numero(num_chamado)
        
        if not id_banco: return False, f"⚠️ Chamado **{num_chamado}** não encontrado.", None

        # --- AÇÕES DE ATUALIZAÇÃO ---
        if acao == "atualizar_status":
            utils_chamados.atualizar_chamado_db(id_banco, {"Status": dados.get("status")})
            st.cache_data.clear()
            return True, f"✅ Status alterado para **{dados.get('status')}**.", None

        elif acao == "atualizar_tecnico":
            utils_chamados.atualizar_chamado_db(id_banco, {"Técnico": dados.get("tecnico")})
            st.cache_data.clear()
            return True, f"✅ Técnico definido: **{dados.get('tecnico')}**.", None
            
        elif acao == "atualizar_agendamento":
            utils_chamados.atualizar_chamado_db(id_banco, {"Agendamento": dados.get("data"), "Status": "AGENDADO"})
            st.cache_data.clear()
            return True, f"✅ Agendado para **{dados.get('data')}**.", None

        # --- AÇÃO DE PDF (NOVO!) ---
        elif acao == "gerar_pdf":
            try:
                pdf_bytes = criar_pdf_chamado(id_banco)
                return True, f"📄 Relatório do chamado **{num_chamado}** gerado com sucesso!", pdf_bytes
            except Exception as e:
                return False, f"Erro ao gerar PDF: {e}", None

    except Exception as e:
        return False, f"Erro técnico: {e}", None
    return False, "Comando desconhecido.", None

# --- 5. PREPARAR DADOS ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return "Base vazia."
    df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce')
    hoje_date = (datetime.utcnow() - timedelta(hours=3)).date()

    cols = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Técnico', 'Agendamento']
    cols_finais = [c for c in cols if c in df.columns]
    
    df_agenda = df[df['Agendamento'].dt.date >= hoje_date].copy()
    df_resto = df[~df.index.isin(df_agenda.index)].tail(300)
    
    df_final = pd.concat([df_agenda, df_resto])
    df_final['Agendamento'] = df_final['Agendamento'].dt.strftime('%Y-%m-%d')
    return df_final[cols_finais].to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 6. INTERFACE ---
with st.sidebar:
    st.header("⚡ Comandos")
    st.markdown("""
    **Novidade:**
    - "Gere um PDF do chamado X"
    
    **Outros:**
    - "Mude o status..."
    - "Atribua o técnico..."
    """)
    if st.button("🗑️ Limpar"): st.session_state.messages = []; st.rerun()

nome = st.session_state.get('usuario', 'User').split()[0].title()
st.markdown(f"""<div class="chat-header"><h2>🕵️ Agente IA: {nome}</h2><p>Gestão e Relatórios.</p></div>""", unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🕵️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        # Se tiver PDF nessa mensagem antiga, mostra botão (opcional, simplificado aqui)

prompt = st.chat_input("Ex: Gere o PDF do chamado GTS-756499")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): st.markdown(prompt)

    with st.chat_message("assistant", avatar="🕵️"):
        with st.spinner("Processando..."):
            try:
                hoje_iso = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d")
                
                instrucao = f"""
                ATUE COMO: Agente Allarmi. HOJE: {hoje_iso}.
                
                DADOS:
                {dados_csv}
                
                COMANDOS JSON VÁLIDOS:
                1. {{ "acao": "atualizar_status", "chamado": "ID", "status": "VALOR" }}
                2. {{ "acao": "atualizar_tecnico", "chamado": "ID", "tecnico": "VALOR" }}
                3. {{ "acao": "atualizar_agendamento", "chamado": "ID", "data": "YYYY-MM-DD" }}
                4. {{ "acao": "gerar_pdf", "chamado": "ID" }}  <-- USE ESTE SE PEDIREM RELATÓRIO/PDF
                
                USUÁRIO DISSE: {prompt}
                """
                
                response = model.generate_content(instrucao)
                texto_resp = response.text.strip()
                
                if "{" in texto_resp and '"acao":' in texto_resp:
                    match = re.search(r'\{.*\}', texto_resp, re.DOTALL)
                    if match:
                        json_limpo = match.group()
                        sucesso, msg_retorno, arquivo_pdf = executar_comando_ia(json_limpo)
                        
                        st.markdown(msg_retorno)
                        st.session_state.messages.append({"role": "assistant", "content": msg_retorno})
                        
                        # SE TIVER PDF, MOSTRA O BOTÃO
                        if arquivo_pdf:
                            nome_arquivo = f"Relatorio_{datetime.now().strftime('%H%M%S')}.pdf"
                            st.download_button(
                                label="📥 Baixar PDF do Chamado",
                                data=arquivo_pdf,
                                file_name=nome_arquivo,
                                mime="application/pdf"
                            )
                        elif sucesso and "PDF" not in msg_retorno:
                            time.sleep(2); st.rerun()
                else:
                    st.markdown(texto_resp)
                    st.session_state.messages.append({"role": "assistant", "content": texto_resp})
                    
            except Exception as e:
                st.error(f"Erro: {e}")
                
# --- CONTROLE DE LOGIN ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Faça login na página principal.")
    st.stop()
