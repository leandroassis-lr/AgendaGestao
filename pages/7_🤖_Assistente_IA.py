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
# Usando o modelo Flash que é rápido e aceita muito contexto (até 1 milhão de tokens)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 3. FUNÇÕES DE AÇÃO (BUSCA TURBO) ---
def buscar_id_por_numero(numero_chamado_usuario):
    """
    Tenta encontrar o ID do chamado de várias formas:
    1. Busca Exata
    2. Busca Parcial (ex: usuário digitou '756499' e achou 'GTS-756499')
    3. Busca Reversa (ex: usuário digitou 'GTS-756499/2025' e achou 'GTS-756499')
    """
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return None
    
    termo = str(numero_chamado_usuario).strip().upper()
    df['Chamado_Upper'] = df['Nº Chamado'].astype(str).str.strip().str.upper()
    
    # TENTATIVA 1: Exata
    filtro = df[df['Chamado_Upper'] == termo]
    
    # TENTATIVA 2: Termo do usuário está CONTIDO no banco (ex: User='123' -> DB='GTS-123')
    if filtro.empty:
        filtro = df[df['Chamado_Upper'].str.contains(termo, regex=False)]
        
    # TENTATIVA 3: O valor do banco está CONTIDO no termo do usuário (ex: User='GTS-123/2025' -> DB='GTS-123')
    if filtro.empty:
        # Verifica linha a linha (mais lento, mas infalível para casos complexos)
        for index, row in df.iterrows():
            if row['Chamado_Upper'] in termo and len(row['Chamado_Upper']) > 3: # >3 evita matches falsos curtos
                return row['ID']

    if not filtro.empty:
        return filtro.iloc[0]['ID']
        
    return None

def executar_comando_ia(comando_json):
    try:
        dados = json.loads(comando_json)
        acao = dados.get("acao")
        num_chamado = dados.get("chamado")
        
        # Usa a busca melhorada
        id_banco = buscar_id_por_numero(num_chamado)
        
        if not id_banco:
            return False, f"⚠️ Não encontrei o chamado **{num_chamado}** no banco de dados. Verifique se o número está correto."

        # --- AÇÃO 1: STATUS ---
        if acao == "atualizar_status":
            novo_status = dados.get("status")
            updates = {"Status": novo_status}
            if dados.get("observacao"): updates["Observação"] = dados.get("observacao")
            
            utils_chamados.atualizar_chamado_db(id_banco, updates)
            st.cache_data.clear()
            return True, f"✅ Status do chamado **{num_chamado}** alterado para **{novo_status}**."

        # --- AÇÃO 2: TÉCNICO ---
        elif acao == "atualizar_tecnico":
            novo_tecnico = dados.get("tecnico")
            utils_chamados.atualizar_chamado_db(id_banco, {"Técnico": novo_tecnico})
            st.cache_data.clear()
            return True, f"✅ Técnico **{novo_tecnico}** atribuído ao chamado **{num_chamado}**."

        # --- AÇÃO 3: AGENDAR ---
        elif acao == "atualizar_agendamento":
            nova_data = dados.get("data")
            utils_chamados.atualizar_chamado_db(id_banco, {"Agendamento": nova_data, "Status": "AGENDADO"})
            st.cache_data.clear()
            return True, f"✅ Chamado **{num_chamado}** agendado para **{nova_data}**."

    except Exception as e:
        return False, f"Erro técnico: {e}"
    
    return False, "Comando desconhecido."

# --- 4. PREPARAR DADOS (AUMENTADO PARA 500 LINHAS) ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return "Base vazia."
    
    cols = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Técnico', 'Agendamento']
    cols_finais = [c for c in cols if c in df.columns]
    
    # AUMENTAMOS DE 60 PARA 500 LINHAS.
    # O Gemini Flash aguenta isso tranquilamente.
    # Priorizamos os chamados que NÃO estão finalizados para aparecerem primeiro se cortar.
    df_ativos = df[df['Status'] != 'Finalizado']
    df_finalizados = df[df['Status'] == 'Finalizado'].tail(100)
    
    df_contexto = pd.concat([df_ativos, df_finalizados]).tail(500)
    
    return df_contexto[cols_finais].to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 5. INTERFACE ---
with st.sidebar:
    st.header("⚡ Comandos")
    st.markdown("""
    **Ordens que eu entendo:**
    - "Atribua o técnico X ao chamado Y"
    - "Mude o status do chamado Y para Concluído"
    - "Agende o chamado Y para dia tal"
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

prompt = st.chat_input("Ex: Chamado GTS-999 atribuir técnico João")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): st.markdown(prompt)

    with st.chat_message("assistant", avatar="🕵️"):
        with st.spinner("Processando..."):
            try:
                hoje_iso = datetime.now().strftime("%Y-%m-%d")
                
                instrucao = f"""
                ATUE COMO: Um Agente de Gestão do sistema Allarmi.
                HOJE: {hoje_iso}
                
                DADOS DISPONÍVEIS (Amostra):
                {dados_csv}
                
                IMPORTANTE: 
                Se o usuário citar um número de chamado que NÃO está na lista acima,
                AINDA ASSIM GERE O COMANDO JSON usando o número que ele forneceu. 
                Eu farei a busca completa no banco de dados depois.
                
                SUA MISSÃO:
                1. Se for PERGUNTA, responda texto.
                2. Se for ORDEM (Mudar/Atribuir/Agendar), retorne APENAS JSON.
                
                FORMATOS JSON:
                {{ "acao": "atualizar_status", "chamado": "NUMERO", "status": "STATUS" }}
                {{ "acao": "atualizar_tecnico", "chamado": "NUMERO", "tecnico": "NOME" }}
                {{ "acao": "atualizar_agendamento", "chamado": "NUMERO", "data": "YYYY-MM-DD" }}
                
                USUÁRIO DISSE: {prompt}
                """
                
                response = model.generate_content(instrucao)
                texto_resp = response.text.strip()
                
                if "{" in texto_resp and '"acao":' in texto_resp:
                    # Limpeza de JSON (caso venha com markdown ```json)
                    match = re.search(r'\{.*\}', texto_resp, re.DOTALL)
                    if match:
                        json_limpo = match.group()
                        sucesso, msg_retorno = executar_comando_ia(json_limpo)
                        st.markdown(msg_retorno)
                        st.session_state.messages.append({"role": "assistant", "content": msg_retorno})
                        if sucesso:
                            time.sleep(2); st.rerun()
                    else:
                        st.error("Erro ao ler comando da IA.")
                else:
                    st.markdown(texto_resp)
                    st.session_state.messages.append({"role": "assistant", "content": texto_resp})
                    
            except Exception as e:
                st.error(f"Erro: {e}")
                
# --- CONTROLE DE LOGIN ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Faça login na página principal.")
    st.stop()




