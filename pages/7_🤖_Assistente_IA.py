import streamlit as st
import pandas as pd
import utils_chamados
import google.generativeai as genai

st.set_page_config(page_title="IA Analyst (Gemini)", page_icon="🤖")

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

# Configura o Gemini
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash') # Modelo rápido e grátis

# --- 2. CARREGAR DADOS (CONTEXTO) ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return "A base de dados está vazia."
    
    cols_uteis = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Sub-Status', 'Analista', 'Agendamento', 'Observação']
    cols_finais = [c for c in cols_uteis if c in df.columns]
    
    # Pega apenas os últimos 100 registros para não estourar o limite de texto se for muito grande
    # ou envie tudo se o volume for pequeno. O Gemini aguenta MUITO texto (1 milhão de tokens).
    df_resumo = df[cols_finais].copy()
    
    return df_resumo.to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 3. INICIALIZA HISTÓRICO ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # No Gemini, o contexto inicial enviamos junto com a primeira pergunta ou configuramos o chat
    # Vamos manter simples enviando o contexto na instrução oculta.

# --- 4. INTERFACE ---
st.title("🤖 Allarmi AI (Gemini Grátis)")
st.caption("Pergunte sobre atrasos, status por analista ou resumos.")

# Mostra histórico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. INTERAÇÃO ---
prompt = st.chat_input("Ex: Quais chamados estão atrasados?")

if prompt:
    # A. Mostra msg do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # B. Chama o Google Gemini
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                # Monta a instrução completa (Contexto + Pergunta)
                instrucao_sistema = f"""
                Você é um especialista em Gestão de Projetos.
                Analise os dados CSV abaixo e responda à pergunta do usuário.
                
                DADOS:
                {dados_csv}
                
                PERGUNTA DO USUÁRIO:
                {prompt}
                
                Responda em português, de forma direta e resumida.
                """
                
                response = model.generate_content(instrucao_sistema)
                texto_resposta = response.text
                
                st.markdown(texto_resposta)
                st.session_state.messages.append({"role": "assistant", "content": texto_resposta})
                
            except Exception as e:
                st.error(f"Erro na IA: {e}")