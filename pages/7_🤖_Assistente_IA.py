import streamlit as st
import pandas as pd
import utils_chamados
import utils
import google.generativeai as genai
from datetime import datetime
import json
import re

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
if not api_key:
    st.error("🔑 Chave GOOGLE_API_KEY não configurada."); st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-flash-latest')

# --- 3. FUNÇÕES DE AÇÃO (CÉREBRO DO CÓDIGO) ---
def buscar_id_por_numero(numero_chamado):
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return None
    # Remove espaços e tenta achar exato ou parcial
    num_clean = str(numero_chamado).strip().upper()
    
    # Tenta busca exata primeiro
    filtro = df[df['Nº Chamado'].astype(str).str.strip().str.upper() == num_clean]
    
    # Se não achar, tenta busca parcial (ex: "756499" dentro de "GTS-756499/2025")
    if filtro.empty:
        filtro = df[df['Nº Chamado'].astype(str).str.contains(num_clean, case=False, na=False)]
        
    if not filtro.empty:
        return filtro.iloc[0]['ID']
    return None

def executar_comando_ia(comando_json):
    """Executa a ação que a IA pediu"""
    try:
        dados = json.loads(comando_json)
        acao = dados.get("acao")
        num_chamado = dados.get("chamado")
        id_banco = buscar_id_por_numero(num_chamado)
        
        if not id_banco:
            return False, f"⚠️ Não encontrei o chamado **{num_chamado}** na base."

        # --- AÇÃO 1: MUDAR STATUS ---
        if acao == "atualizar_status":
            novo_status = dados.get("status")
            obs = dados.get("observacao", "")
            updates = {"Status": novo_status}
            if obs: updates["Observação"] = obs
            
            utils_chamados.atualizar_chamado_db(id_banco, updates)
            st.cache_data.clear()
            return True, f"✅ Status do chamado **{num_chamado}** alterado para **{novo_status}**."

        # --- AÇÃO 2: MUDAR TÉCNICO (NOVO!) ---
        elif acao == "atualizar_tecnico":
            novo_tecnico = dados.get("tecnico")
            utils_chamados.atualizar_chamado_db(id_banco, {"Técnico": novo_tecnico})
            st.cache_data.clear()
            return True, f"✅ Técnico **{novo_tecnico}** atribuído ao chamado **{num_chamado}**."

        # --- AÇÃO 3: AGENDAR (NOVO!) ---
        elif acao == "atualizar_agendamento":
            nova_data = dados.get("data") # Formato YYYY-MM-DD
            try:
                # Converte string YYYY-MM-DD para objeto date
                data_obj = datetime.strptime(nova_data, "%Y-%m-%d").date()
                utils_chamados.atualizar_chamado_db(id_banco, {"Agendamento": data_obj, "Status": "AGENDADO"})
                st.cache_data.clear()
                return True, f"✅ Chamado **{num_chamado}** agendado para **{data_obj.strftime('%d/%m/%Y')}**."
            except:
                return False, "❌ Erro ao processar a data. O formato deve ser YYYY-MM-DD."

    except Exception as e:
        return False, f"Erro técnico: {e}"
    
    return False, "Comando não reconhecido."

# --- 4. PREPARAR DADOS ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return "Base vazia."
    # Adicionamos a coluna Técnico para a IA ler quem está alocado hoje
    cols = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Técnico', 'Analista', 'Agendamento']
    cols_finais = [c for c in cols if c in df.columns]
    return df[cols_finais].tail(60).to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 5. INTERFACE ---
with st.sidebar:
    st.header("⚡ Comandos de Agente")
    st.markdown("""
    **A IA agora sabe:**
    1. 🔄 Mudar Status
    2. 👷 Atribuir Técnico
    3. 📅 Agendar Data
    
    **Exemplos:**
    - *"Atribua o técnico Flavio ao chamado GTS-999"*
    - *"Agende o chamado X para o dia 25/10"*
    """)
    if st.button("🗑️ Limpar"):
        st.session_state.messages = []
        st.rerun()

nome = st.session_state.get('usuario', 'User').split()[0].title()
st.markdown(f"""<div class="chat-header"><h2>🕵️ Agente IA: {nome}</h2><p>Gerenciamento inteligente de chamados.</p></div>""", unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🕵️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

prompt = st.chat_input("Dê uma ordem ou faça uma pergunta...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): st.markdown(prompt)

    with st.chat_message("assistant", avatar="🕵️"):
        with st.spinner("Processando..."):
            try:
                # --- O CÉREBRO NOVO ---
                hoje_iso = datetime.now().strftime("%Y-%m-%d")
                
                instrucao = f"""
                ATUE COMO: Um Agente de Gestão do sistema Allarmi.
                HOJE: {hoje_iso}
                
                DADOS:
                {dados_csv}
                
                SUA MISSÃO:
                1. Se for APENAS PERGUNTA, responda texto.
                2. Se for ORDEM DE AÇÃO, retorne APENAS JSON.
                
                FORMATOS DE JSON ACEITOS (Escolha o adequado):
                
                A) Mudar Status:
                {{ "acao": "atualizar_status", "chamado": "ID_NUMERO", "status": "NOVO_STATUS" }}
                
                B) Mudar Técnico:
                {{ "acao": "atualizar_tecnico", "chamado": "ID_NUMERO", "tecnico": "NOME_COMPLETO_CORRIGIDO" }}
                
                C) Agendar:
                {{ "acao": "atualizar_agendamento", "chamado": "ID_NUMERO", "data": "YYYY-MM-DD" }}
                
                REGRAS:
                - Corrija nomes de técnicos baseado no contexto se possível.
                - Para datas, converta "amanhã" ou "segunda" para YYYY-MM-DD usando a data de hoje ({hoje_iso}) como base.
                - Identifique o chamado mesmo se o usuário digitar apenas o número (ex: "756499" vira o chamado correspondente no CSV).
                
                USUÁRIO DISSE: {prompt}
                """
                
                response = model.generate_content(instrucao)
                texto_resp = response.text.strip()
                
                # Detecta JSON
                if "{" in texto_resp and '"acao":' in texto_resp:
                    json_limpo = re.search(r'\{.*\}', texto_resp, re.DOTALL).group()
                    sucesso, msg_retorno = executar_comando_ia(json_limpo)
                    st.markdown(msg_retorno)
                    st.session_state.messages.append({"role": "assistant", "content": msg_retorno})
                    if sucesso:
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



