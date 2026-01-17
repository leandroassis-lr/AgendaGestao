import streamlit as st
import pandas as pd
import utils_chamados
import google.generativeai as genai

st.set_page_config(page_title="IA Analyst", page_icon="🤖")

# --- CSS CHAT ---
st.markdown("""
<style>
    .stChatMessage { padding: 1rem; border-radius: 10px; margin-bottom: 10px; }
    div[data-testid="stChatMessageContent"] { font-size: 1rem; }
</style>
""", unsafe_allow_html=True)

# --- 1. CONFIGURAÇÃO API GOOGLE ---
# Busca a chave no arquivo secrets.toml
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("🔑 Chave GOOGLE_API_KEY não configurada no secrets.toml")
    st.stop()

# Configura o Gemini com o modelo que você tem acesso
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- 2. CARREGAR DADOS (CONTEXTO) ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    
    if df.empty:
        return "A base de dados está vazia."
    
    # Seleciona as colunas mais importantes para a IA entender
    cols_uteis = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Sub-Status', 'Analista', 'Agendamento', 'Observação']
    cols_finais = [c for c in cols_uteis if c in df.columns]
    
    # Pega os dados mais recentes (ex: últimos 200) para garantir que cabe no contexto
    # O Gemini 2.0 aguenta muito texto, mas é bom ser eficiente
    df_resumo = df[cols_finais].tail(200).copy()
    
    # Converte para texto (CSV)
    return df_resumo.to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 3. INICIALIZA HISTÓRICO ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 4. INTERFACE ---
st.title("🤖 Allarmi AI (Gemini 2.0)")
st.caption("Pergunte sobre atrasos, status por analista ou resumos dos seus projetos.")

# Mostra histórico de mensagens na tela
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. INTERAÇÃO (CHAT) ---
prompt = st.chat_input("Ex: Quais chamados estão atrasados?")

if prompt:
    # A. Mostra msg do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # B. Chama o Google Gemini
    with st.chat_message("assistant"):
        with st.spinner("Analisando dados..."):
            try:
                # Monta a instrução completa (Contexto + Pergunta)
                instrucao_sistema = f"""
                Você é um especialista em Gestão de Projetos e Financeiro.
                Analise os dados CSV abaixo e responda à pergunta do usuário.
                
                DADOS DOS CHAMADOS (CSV):
                {dados_csv}
                
                PERGUNTA DO USUÁRIO:
                {prompt}
                
                DIRETRIZES:
                1. Responda em português.
                2. Seja direto e use negrito para destacar números ou chamados (ex: **GTS-123**).
                3. Se a resposta envolver listas, use tópicos (bullet points).
                4. Se não encontrar a informação, diga que não consta na base fornecida.
                """
                
                # Gera a resposta
                response = model.generate_content(instrucao_sistema)
                texto_resposta = response.text
                
                # Exibe e salva
                st.markdown(texto_resposta)
                st.session_state.messages.append({"role": "assistant", "content": texto_resposta})
                
            except Exception as e:
                st.error(f"Erro na IA: {e}")
