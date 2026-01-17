import streamlit as st
import pandas as pd
import utils_chamados
import google.generativeai as genai
import time

st.set_page_config(page_title="IA Analyst", page_icon="🤖")

# --- CSS CHAT ---
st.markdown("""
<style>
    .stChatMessage { padding: 1rem; border-radius: 10px; margin-bottom: 10px; }
    div[data-testid="stChatMessageContent"] { font-size: 1rem; }
</style>
""", unsafe_allow_html=True)

# --- 1. CONFIGURAÇÃO API GOOGLE ---
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("🔑 Chave GOOGLE_API_KEY não configurada no secrets.toml")
    st.stop()

# Configura o Gemini (Usando a versão 1.5 Flash que é a estável e grátis)
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-flash-latest')

# --- 2. CARREGAR DADOS (CONTEXTO) ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    
    if df.empty:
        return "A base de dados está vazia."
    
    cols_uteis = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Sub-Status', 'Analista', 'Agendamento', 'Observação']
    cols_finais = [c for c in cols_uteis if c in df.columns]
    
    # Reduzido para 50 para economizar cota e ser mais rápido
    df_resumo = df[cols_finais].tail(50).copy()
    
    return df_resumo.to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 3. INICIALIZA HISTÓRICO ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 4. INTERFACE ---
st.title("🤖 Allarmi AI Analyst")
st.caption("Pergunte sobre atrasos, status por analista ou resumos (Base: Últimos 50 chamados).")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. INTERAÇÃO ---
prompt = st.chat_input("Ex: Quais chamados estão atrasados?")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analisando..."):
            try:
                instrucao_sistema = f"""
                Você é um especialista em Gestão de Projetos.
                Use os dados CSV abaixo para responder.
                
                DADOS:
                {dados_csv}
                
                PERGUNTA:
                {prompt}
                
                Responda em português, curto e direto.
                """
                
                response = model.generate_content(instrucao_sistema)
                texto_resposta = response.text
                
                st.markdown(texto_resposta)
                st.session_state.messages.append({"role": "assistant", "content": texto_resposta})
                
            except Exception as e:
                # Se der erro de cota de novo, avisamos de forma amigável
                if "429" in str(e):
                    msg_erro = "⏳ **Muitas perguntas seguidas!** O plano gratuito tem um limite de velocidade. Aguarde 30 segundos e tente novamente."
                    st.warning(msg_erro)
                else:
                    st.error(f"Erro na IA: {e}")

