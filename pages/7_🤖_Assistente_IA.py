import streamlit as st
import pandas as pd
import utils_chamados
import google.generativeai as genai
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Assistente IA", page_icon="🤖", layout="wide")

# --- 1. CSS PARA VISUAL MODERNO ---
st.markdown("""
<style>
    /* Cabeçalho Personalizado */
    .chat-header {
        padding: 1rem;
        background-color: #f0f2f6;
        border-radius: 10px;
        margin-bottom: 2rem;
        border-left: 5px solid #4CAF50;
    }
    .chat-header h2 {
        margin: 0;
        color: #1f1f1f;
        font-size: 1.8rem;
    }
    .chat-header p {
        margin: 5px 0 0 0;
        color: #666;
    }
    
    /* Estilo das Mensagens */
    .stChatMessage {
        padding: 1rem;
        border-radius: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
    div[data-testid="stChatMessageContent"] {
        font-size: 1.05rem;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIGURAÇÃO API ---
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key:
    st.error("🔑 Chave GOOGLE_API_KEY não configurada.")
    st.stop()

genai.configure(api_key=api_key)
# Usando o modelo que funcionou para você (pode trocar se necessário)
model = genai.GenerativeModel('gemini-flash-latest')

# --- 3. CARREGAR DADOS COM INTELIGÊNCIA ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    
    if df.empty:
        return "A base de dados está vazia."
    
    # Seleção estratégica de colunas
    cols_uteis = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Sub-Status', 'Analista', 'Agendamento', 'Observação']
    cols_finais = [c for c in cols_uteis if c in df.columns]
    
    # Pega os 100 mais recentes para análise rápida
    df_resumo = df[cols_finais].tail(100).copy()
    
    return df_resumo.to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 4. SIDEBAR (SUGESTÕES) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712027.png", width=50)
    st.header("Dicas de Perguntas")
    st.markdown("""
    Tente perguntar algo como:
    
    - 🚩 *Quais chamados estão atrasados?*
    - 📊 *Faça um resumo dos status.*
    - 👤 *O que a Analista Giovana tem pendente?*
    - 🏢 *Como está a situação da Agência Centro?*
    - 📅 *O que temos agendado para esta semana?*
    """)
    st.divider()
    if st.button("🗑️ Limpar Conversa"):
        st.session_state.messages = []
        st.rerun()

# --- 5. CABEÇALHO PERSONALIZADO ---
nome_usuario = st.session_state.get('usuario', 'Colaborador').split()[0].title()

st.markdown(f"""
<div class="chat-header">
    <h2>🤖 Olá, {nome_usuario}!</h2>
    <p>Sou seu analista virtual. Em que posso ajudar na gestão hoje?</p>
</div>
""", unsafe_allow_html=True)

# --- 6. HISTÓRICO DE CHAT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe mensagens anteriores
for msg in st.session_state.messages:
    # Define avatares
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# --- 7. LÓGICA DE INTERAÇÃO ---
prompt = st.chat_input("Digite sua pergunta sobre os projetos...")

if prompt:
    # A. Exibe mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # B. Processa resposta da IA
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🔍 Analisando dados..."):
            try:
                # Dados contextuais importantes
                hoje = datetime.now().strftime("%d/%m/%Y")
                dia_semana = datetime.now().strftime("%A")
                
                instrucao_sistema = f"""
                ATUE COMO: Um Analista Sênior de Projetos do sistema Allarmi.
                
                CONTEXTO TEMPORAL:
                - Hoje é: {hoje} ({dia_semana}).
                - Use essa data para calcular atrasos (se Agendamento < Hoje).
                
                DADOS DOS CHAMADOS (CSV):
                {dados_csv}
                
                PERGUNTA DO USUÁRIO ({nome_usuario}):
                "{prompt}"
                
                DIRETRIZES DE RESPOSTA:
                1. Seja cordial, profissional e direto.
                2. Use formatação Markdown: **Negrito** para chamados/números, tabelas se necessário.
                3. Se encontrar problemas (atrasos, pendências), destaque com emojis (🚨, ⚠️).
                4. Responda APENAS com base nos dados fornecidos.
                """
                
                response = model.generate_content(instrucao_sistema)
                texto_resposta = response.text
                
                st.markdown(texto_resposta)
                st.session_state.messages.append({"role": "assistant", "content": texto_resposta})
                
            except Exception as e:
                msg_erro = f"Desculpe, tive um problema técnico: {e}"
                st.error(msg_erro)
