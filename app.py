import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta 
import random
import time
from PIL import Image
import re
import html
import utils 
import utils_chamados # <--- IMPORTANTE: Conexão com a base de chamados

# ----------------- Configuração da Página e CSS -----------------
st.set_page_config(page_title="Projetos - GESTÃO", page_icon="📋", layout="wide")
utils.load_css()

# ----------------- FUNÇÕES DE IMPORTAÇÃO -----------------

@st.dialog("📂 Importar Planilha Padrão", width="medium")
def run_importer_dialog():
    st.info("Faça upload do arquivo 'Template.xlsx' ou '.csv'.")
    uploaded_file = st.file_uploader("Arquivo", type=["xlsx", "csv"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8-sig')
                if len(df.columns) <= 1:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=',', dtype=str, encoding='utf-8-sig')
            else:
                df = pd.read_excel(uploaded_file, dtype=str)
            
            if st.button("Processar Importação"):
                with st.spinner("Importando..."):
                    sucesso, qtd = utils_chamados.bulk_insert_chamados_db(df)
                    if sucesso:
                        st.success(f"{qtd} registros importados!")
                        time.sleep(1)
                        st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

@st.dialog("🚚 Importar Pedidos", width="medium")
def run_pedido_importer_dialog():
    st.info("Atualize a coluna **Nº Pedido** usando uma planilha com: **CHAMADO** e **PEDIDO**.")
    uploaded_pedidos = st.file_uploader("Planilha de Pedidos (.xlsx/.csv)", type=["xlsx", "csv"])
    if uploaded_pedidos:
        try:
            if uploaded_pedidos.name.endswith('.csv'): 
                df_ped = pd.read_csv(uploaded_pedidos, sep=';', header=0, dtype=str)
            else: 
                df_ped = pd.read_excel(uploaded_pedidos, header=0, dtype=str)
            
            df_ped.columns = [str(c).strip().upper() for c in df_ped.columns]
            
            if 'CHAMADO' not in df_ped.columns or 'PEDIDO' not in df_ped.columns:
                st.error("Colunas 'CHAMADO' e 'PEDIDO' obrigatórias.")
            else:
                if st.button("🚀 Processar Pedidos"):
                    with st.spinner("Atualizando..."):
                        df_bd = utils_chamados.carregar_chamados_db()
                        id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                        count = 0
                        for i, row in df_ped.iterrows():
                            c_key = str(row['CHAMADO']).strip(); p_val = str(row['PEDIDO']).strip()
                            if c_key in id_map and p_val:
                                utils_chamados.atualizar_chamado_db(id_map[c_key], {'Nº Pedido': p_val})
                                count += 1
                        st.success(f"{count} pedidos atualizados!")
                        time.sleep(1); st.rerun()
        except Exception as e: st.error(f"Erro: {e}")

@st.dialog("🔗 Importar Links", width="medium")
def run_link_importer_dialog():
    st.info("Atualize Links com planilha: **CHAMADO** e **LINK**.")
    uploaded_links = st.file_uploader("Arquivo", type=["xlsx", "csv"])
    if uploaded_links:
        # (Lógica simplificada para caber aqui)
        try:
            if uploaded_links.name.endswith('.csv'): df_l = pd.read_csv(uploaded_links, sep=';', dtype=str)
            else: df_l = pd.read_excel(uploaded_links, dtype=str)
            df_l.columns = [str(c).strip().upper() for c in df_l.columns]
            if st.button("Processar Links"):
                 df_bd = utils_chamados.carregar_chamados_db()
                 id_map = df_bd.set_index('Nº Chamado')['ID'].to_dict()
                 c=0
                 for _, r in df_l.iterrows():
                     if r['CHAMADO'] in id_map: 
                         utils_chamados.atualizar_chamado_db(id_map[r['CHAMADO']], {'Link Externo': r['LINK']})
                         c+=1
                 st.success(f"{c} links atualizados!"); time.sleep(1); st.rerun()
        except: st.error("Erro no arquivo.")

# ----------------- Função: Tela de Login -----------------
def tela_login():
    
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stAppViewContainer"] { background: linear-gradient(90deg, #e8f5e9 0%, #e8f5e9 50%, #1b5e20 50%, #1b5e20 100%); }
    section.main > div { display: flex; align-items: stretch; justify-content: center; height: 100vh; }
    div[data-testid="stForm"] { background-color: rgba(255, 255, 255, 0.95); padding: 2.5rem; border-radius: 16px; box-shadow: 0 0 20px rgba(0,0,0,0.15); width: 380px; margin: auto; }
    .stButton > button { background-color: #43a047 !important; color: white !important; width: 100%; }
    .login-logo-container img { max-width:15%; border-radius: 30%; display: block; margin: auto; }
    </style>
    """, unsafe_allow_html=True)

    try: imagem_principal = Image.open("Foto 2.jpg")
    except: imagem_principal = None

    col1, col2 = st.columns([1, 1], gap="small") 
    with col1:
        st.subheader("Gestão de Projetos Allarmi")      
        st.write("") 
        with st.form("form_login"):
            nome = st.text_input("Nome", key="login_nome")
            email = st.text_input("E-mail", key="login_email")
            if st.form_submit_button("Entrar"):
                if utils.validar_usuario(nome.strip(), email.strip()):
                    st.session_state.update(usuario=nome.strip(), logado=True, boas_vindas=True, tela_principal=True)
                    time.sleep(1); st.rerun()
                else:
                    st.error("Acesso negado.")
    with col2:
        if imagem_principal: st.image(imagem_principal, use_container_width=True) 

# ----------------- Tela de Boas-Vindas -----------------
def tela_boas_vindas():
     [  "Que seu dia seja produtivo e cheio de conquistas!",
        "Acredite no seu potencial e siga firme rumo aos resultados!",
        "Grandes projetos nascem de pequenas ações consistentes!",
        "Transforme desafios em oportunidades hoje!",
        "Você é capaz de grandes resultados — confie no processo!",
        "Siga com foco, energia e propósito neste novo dia!"
    ]
    msg = random.choice(mensagens)
    st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stToolbar"] {
        display: none;
    }
    body, [data-testid="stAppViewContainer"], section.main, [data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"] > div {
        background-color: #e8f5e9 !important;
    }
    .welcome-screen-container { 
        display: flex;
        flex-direction: column; 
        align-items: center;
        justify-content: flex-start;
        padding-top: 35vh;
        height: 100vh; 
        text-align: center;
        animation: fadeIn 1s ease-in-out;
        color: #1b5e20; 
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    .welcome-screen-container h1 {
        font-size: 3rem;
        margin-bottom: 25px;
        color: #1b5e20; 
    }
    .welcome-screen-container p {
        font-size: 1.4rem;
        opacity: 0.9;
        color: #1b5e20; 
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f"""
        <div class="welcome-screen-container">
            <h1>Seja bem-vindo, {st.session_state.usuario} 👋</h1>
            <p>{msg}</p>
        </div>
    """, unsafe_allow_html=True)
    time.sleep(5)
    st.session_state.boas_vindas = False
    st.session_state.tela_principal = True
    st.rerun()

# ----------------- COCKPIT (Antiga Pág 7) -----------------
def tela_cockpit():
    # Sidebar de Ações
    st.sidebar.title(f"Olá, {st.session_state.get('usuario','User')}")
    st.sidebar.divider()
    st.sidebar.header("📥 Importações")
    if st.sidebar.button("📂 Planilha Padrão"): run_importer_dialog()
    if st.sidebar.button("🚚 Pedidos"): run_pedido_importer_dialog()
    if st.sidebar.button("🔗 Links"): run_link_importer_dialog()
    st.sidebar.divider()
    if st.sidebar.button("Logout", type="primary"): st.session_state.clear(); st.rerun()

    # Conteúdo Principal
    st.title("📌 Visão Geral (Cockpit)")
    
    df = utils_chamados.carregar_chamados_db()
    if df.empty:
        st.info("Nenhum dado encontrado. Use o menu lateral para importar.")
        return

    # Tratamento
    df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce')
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado', 'equipamento entregue']
    
    # KPIs
    pendentes = df[~df['Status'].str.lower().isin(status_fim)]
    hoje = pd.Timestamp.today().normalize()
    atrasados = pendentes[pendentes['Agendamento'] < hoje]
    prox = pendentes[(pendentes['Agendamento'] >= hoje) & (pendentes['Agendamento'] <= hoje + timedelta(days=5))]

    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Total de Chamados", len(df))
    m2.metric("🚨 Atrasados Geral", len(atrasados), delta_color="inverse")
    m3.metric("📅 Vencendo na Semana", len(prox))

    st.markdown("---")
    st.subheader("Meus Projetos")
    
    # Grid de Projetos
    lista_projetos = sorted(df['Projeto'].dropna().unique().tolist())
    cols = st.columns(3)
    
    for i, proj in enumerate(lista_projetos):
        df_p = df[df['Projeto'] == proj]
        total_p = len(df_p)
        concluidos = len(df_p[df_p['Status'].str.lower().isin(status_fim)])
        atrasados_p = len(df_p[(~df_p['Status'].str.lower().isin(status_fim)) & (df_p['Agendamento'] < hoje)])
        perc = int((concluidos / total_p) * 100) if total_p > 0 else 0
        
        # Cor
        cor = "#3498db"
        if atrasados_p > 0: cor = "#e74c3c"
        elif perc == 100: cor = "#2ecc71"

        with cols[i % 3]:
            # HTML Card
            st.markdown(f"""
            <div style="border-left: 5px solid {cor}; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px;">
                <h4 style="margin:0; color:#333; font-size:1.1em;">{proj}</h4>
                <div style="display:flex; justify-content:space-between; font-size:0.8em; color:#666; margin-top:5px;">
                    <span>Progresso</span><span>{perc}%</span>
                </div>
                <div style="background:#eee; height:6px; width:100%; margin:5px 0; border-radius:3px;">
                    <div style="background:{cor}; height:6px; width:{perc}%; border-radius:3px;"></div>
                </div>
                <div style="font-size:0.8em; color:#888;">📋 {concluidos}/{total_p} concluídos</div>
            </div>
            """, unsafe_allow_html=True)
            
            # BOTÃO DE AÇÃO
            if st.button(f"🔍 Ver Detalhes", key=f"btn_{i}", use_container_width=True):
                st.session_state["sel_projeto"] = proj
                st.switch_page("pages/1_🔧_Detalhes_Projetos.py")

# ----------------- MAIN -----------------
def main():
    if "logado" not in st.session_state: st.session_state.logado = False
    if "boas_vindas" not in st.session_state: st.session_state.boas_vindas = False 

    if not st.session_state.logado:
        tela_login()
    elif st.session_state.boas_vindas:
        tela_boas_vindas()
    else:
        tela_cockpit()

if __name__ == "__main__":
    utils.criar_tabelas_iniciais() 
    main()
