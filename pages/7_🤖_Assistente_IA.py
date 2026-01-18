import streamlit as st
import pandas as pd
import utils_chamados
import utils
import google.generativeai as genai
from datetime import datetime, timedelta
import json
import re
import time

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

# --- 3. FUNÇÕES DE AÇÃO ---
def buscar_id_por_numero(numero_chamado_usuario):
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return None
    
    termo = str(numero_chamado_usuario).strip().upper()
    df['Chamado_Upper'] = df['Nº Chamado'].astype(str).str.strip().str.upper()
    
    # Busca Exata
    filtro = df[df['Chamado_Upper'] == termo]
    # Busca Contida
    if filtro.empty: filtro = df[df['Chamado_Upper'].str.contains(termo, regex=False)]
    
    if not filtro.empty: return filtro.iloc[0]['ID']
    return None

def executar_comando_ia(comando_json):
    try:
        dados = json.loads(comando_json)
        acao = dados.get("acao")
        num_chamado = dados.get("chamado")
        id_banco = buscar_id_por_numero(num_chamado)
        
        if not id_banco:
            return False, f"⚠️ Não encontrei o chamado **{num_chamado}**. Verifique o número."

        if acao == "atualizar_status":
            novo_status = dados.get("status")
            updates = {"Status": novo_status}
            if dados.get("observacao"): updates["Observação"] = dados.get("observacao")
            utils_chamados.atualizar_chamado_db(id_banco, updates)
            st.cache_data.clear()
            return True, f"✅ Status do chamado **{num_chamado}** alterado para **{novo_status}**."

        elif acao == "atualizar_tecnico":
            novo_tecnico = dados.get("tecnico")
            utils_chamados.atualizar_chamado_db(id_banco, {"Técnico": novo_tecnico})
            st.cache_data.clear()
            return True, f"✅ Técnico **{novo_tecnico}** atribuído ao chamado **{num_chamado}**."

        elif acao == "atualizar_agendamento":
            nova_data = dados.get("data")
            utils_chamados.atualizar_chamado_db(id_banco, {"Agendamento": nova_data, "Status": "AGENDADO"})
            st.cache_data.clear()
            return True, f"✅ Chamado **{num_chamado}** agendado para **{nova_data}**."

    except Exception as e:
        return False, f"Erro técnico: {e}"
    return False, "Comando desconhecido."

# --- 4. PREPARAR DADOS (FILTRO INTELIGENTE DE AGENDA) ---
@st.cache_data(ttl=300)
def preparar_dados_para_ia():
    df = utils_chamados.carregar_chamados_db()
    if df.empty: return "Base vazia."
    
    # 1. Garante que a coluna de data é data mesmo
    df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce')
    
    # 2. Define hoje (Brasil)
    hoje = datetime.utcnow() - timedelta(hours=3)
    hoje_date = hoje.date()

    cols = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Status', 'Técnico', 'Agendamento', 'Descrição']
    cols_finais = [c for c in cols if c in df.columns]
    
    # 3. CRIA DOIS GRUPOS DE DADOS PARA ENVIAR
    # Grupo A: Tudo que tem agendamento HOJE ou FUTURO (Prioridade Máxima)
    df_agenda_futura = df[df['Agendamento'].dt.date >= hoje_date].copy()
    
    # Grupo B: Os últimos chamados gerais (para contexto de status)
    # Pegamos os últimos 300, excluímos o que já está no Grupo A para não duplicar
    df_resto = df[~df.index.isin(df_agenda_futura.index)].tail(300)
    
    # Junta tudo (Agenda primeiro)
    df_contexto = pd.concat([df_agenda_futura, df_resto])
    
    # Converte data para string YYYY-MM-DD para a IA ler fácil
    df_contexto['Agendamento'] = df_contexto['Agendamento'].dt.strftime('%Y-%m-%d')
    
    return df_contexto[cols_finais].to_csv(index=False)

dados_csv = preparar_dados_para_ia()

# --- 5. INTERFACE ---
with st.sidebar:
    st.header("⚡ Comandos")
    st.markdown("""
    **Ordens:**
    - "Atribua técnico X ao chamado Y"
    - "Mude status do chamado Y para Concluído"
    - "Agende chamado Y para dia tal"
    """)
    if st.button("🗑️ Limpar"):
        st.session_state.messages = []
        st.rerun()

nome = st.session_state.get('usuario', 'User').split()[0].title()
st.markdown(f"""<div class="chat-header"><h2>🕵️ Agente IA: {nome}</h2><p>Gerenciamento inteligente.</p></div>""", unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🕵️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

prompt = st.chat_input("Ex: Qual a agenda para a próxima semana?")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): st.markdown(prompt)

    with st.chat_message("assistant", avatar="🕵️"):
        with st.spinner("Consultando agenda e dados..."):
            try:
                # DATA CORRETA BRASIL (UTC -3)
                agora_br = datetime.utcnow() - timedelta(hours=3)
                hoje_iso = agora_br.strftime("%Y-%m-%d")
                dia_semana = agora_br.strftime("%A")
                
                instrucao = f"""
                ATUE COMO: Um Agente de Gestão do sistema Allarmi.
                
                DATA DE HOJE (Referência Brasil): {hoje_iso} ({dia_semana}).
                
                DADOS DOS CHAMADOS:
                {dados_csv}
                
                SUA MISSÃO:
                1. Se perguntarem sobre AGENDA ou DATAS:
                   - Comece a resposta dizendo: "Considerando hoje, dia {hoje_iso}..."
                   - Liste os chamados com data igual ou maior que hoje.
                   - "Próxima semana" significa os próximos 7 dias a partir de {hoje_iso}.
                
                2. Se for ORDEM (Mudar/Atribuir/Agendar):
                   - Retorne APENAS JSON.
                
                FORMATOS JSON:
                {{ "acao": "atualizar_status", "chamado": "NUMERO", "status": "STATUS" }}
                {{ "acao": "atualizar_tecnico", "chamado": "NUMERO", "tecnico": "NOME" }}
                {{ "acao": "atualizar_agendamento", "chamado": "NUMERO", "data": "YYYY-MM-DD" }}
                
                USUÁRIO DISSE: {prompt}
                """
                
                response = model.generate_content(instrucao)
                texto_resp = response.text.strip()
                
                if "{" in texto_resp and '"acao":' in texto_resp:
                    match = re.search(r'\{.*\}', texto_resp, re.DOTALL)
                    if match:
                        json_limpo = match.group()
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







