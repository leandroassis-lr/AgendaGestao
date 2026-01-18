import streamlit as st
import pandas as pd
import utils_chamados
import google.generativeai as genai
from datetime import datetime
import json
import re

# Configuração da Página
st.set_page_config(page_title="Agente IA", page_icon="🕵️", layout="wide")

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
model = genai.GenerativeModel('gemini-flash-latest') # Modelo rápido

# --- 3. FUNÇÕES DE AÇÃO (BRAÇOS DO ROBÔ) ---
def buscar_id_por_numero(numero_chamado):
    """Encontra o ID interno do banco baseado no texto do chamado (ex: GTS-123)"""
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return None
    # Tenta limpar espaços
    filtro = df[df['Nº Chamado'].astype(str).str.strip() == str(numero_chamado).strip()]
    if not filtro.empty:
        return filtro.iloc[0]['ID']
    return None

def executar_comando_ia(comando_json):
    """Recebe o JSON da IA e executa a atualização no banco"""
    try:
        dados = json.loads(comando_json)
        acao = dados.get("acao")
        
        if acao == "atualizar_status":
            num_chamado = dados.get("chamado")
            novo_status = dados.get("status")
            obs = dados.get("observacao", "")
            
            id_banco = buscar_id_por_numero(num_chamado)
            
            if id_banco:
                updates = {"Status": novo_status}
                if obs: updates["Observação"] = obs
                
                # Executa no banco
                utils_chamados.atualizar_chamado_db(id_banco, updates)
                st.cache_data.clear() # Limpa cache para ver a mudança
                return True, f"✅ Feito! O chamado **{num_chamado}** foi atualizado para **{novo_status}**."
            else:
                return False, f"⚠️ Não encontrei o chamado **{num_chamado}** no banco de dados."
                
    except Exception as e:
        return False, f"Erro ao processar comando: {e}"
    
    return False, "Comando não reconhecido."

# --- 4. PREPARAR DADOS ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return "Base vazia."
    # Envia colunas essenciais
    cols = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Analista', 'Agendamento']
    cols_finais = [c for c in cols if c in df.columns]
    return df[cols_finais].tail(100).to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("⚡ Comandos Disponíveis")
    st.info("Agora eu posso atualizar o sistema!")
    st.markdown("""
    **Tente:**
    - "Mude o status do GTS-XXXX para Concluído"
    - "Coloque o chamado YYYY em Andamento"
    """)
    if st.button("🗑️ Limpar Conversa"):
        st.session_state.messages = []
        st.rerun()

# --- 6. CABEÇALHO ---
nome = st.session_state.get('usuario', 'User').split()[0].title()
st.markdown(f"""<div class="chat-header"><h2>🕵️ Agente IA: {nome}</h2><p>Analiso dados e executo atualizações nos chamados.</p></div>""", unsafe_allow_html=True)

# --- 7. CHAT ---
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🕵️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

prompt = st.chat_input("Digite uma análise ou uma ordem de atualização...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): st.markdown(prompt)

    with st.chat_message("assistant", avatar="🕵️"):
        with st.spinner("Processando..."):
            try:
                # --- O SEGREDO: INSTRUÇÃO DE COMANDO ---
                instrucao = f"""
                ATUE COMO: Um Agente de Gestão do sistema Allarmi.
                
                SEUS DADOS:
                {dados_csv}
                
                SUA MISSÃO:
                1. Se o usuário pedir apenas INFORMAÇÃO, responda normalmente em texto.
                2. Se o usuário pedir para ALTERAR/ATUALIZAR/MUDAR um status, NÃO RESPONDA TEXTO.
                   Retorne APENAS um JSON estrito neste formato:
                   
                   {{
                     "acao": "atualizar_status",
                     "chamado": "NUMERO_EXATO_DO_CHAMADO",
                     "status": "NOVO_STATUS_NORMALIZADO",
                     "observacao": "Resumo do motivo se houver"
                   }}
                   
                Status Válidos: AGENDADO, EM ANDAMENTO, CONCLUÍDO, FINALIZADO, PENDÊNCIA, CANCELADO.
                Se o usuário falar "Terminado", use "CONCLUÍDO". Se falar "Ok", use "FINALIZADO".
                
                PERGUNTA: {prompt}
                """
                
                response = model.generate_content(instrucao)
                texto_resp = response.text.strip()
                
                # Tenta detectar se é um JSON (Comando)
                if "{" in texto_resp and "atualizar_status" in texto_resp:
                    # Limpa o texto caso a IA tenha colocado ```json ... ```
                    json_limpo = re.search(r'\{.*\}', texto_resp, re.DOTALL).group()
                    
                    sucesso, msg_retorno = executar_comando_ia(json_limpo)
                    st.markdown(msg_retorno)
                    st.session_state.messages.append({"role": "assistant", "content": msg_retorno})
                    
                    if sucesso:
                        time.sleep(2)
                        st.rerun() # Recarrega para atualizar os dados
                        
                else:
                    # Resposta Normal
                    st.markdown(texto_resp)
                    st.session_state.messages.append({"role": "assistant", "content": texto_resp})
                    
            except Exception as e:
                st.error(f"Erro: {e}")
