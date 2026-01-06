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
    # --- CSS exclusivo da tela de login ---
    st.markdown("""
    <style>
    /* ... (Todo o seu CSS da tela_login fica aqui) ... */
    
    /* Remove a sidebar SÓ na tela de login */
    [data-testid="stSidebar"] {
        display: none;
    }

    /* Fundo dividido para a tela de login */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(90deg, #e8f5e9 0%, #e8f5e9 50%, #1b5e20 50%, #1b5e20 100%);
    }

    section.main > div {
        display: flex; 
        align-items: stretch;
        justify-content: center;
        height: 100vh;
    }

    div[data-testid="stHorizontalBlock"] > div[data-testid^="stVerticalBlock"] {
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100vh;
    }

    div[data-testid="stForm"] {
        background-color: rgba(255, 255, 255, 0.95);
        padding: 2.5rem;
        border-radius: 16px;
        box-shadow: 0 0 20px rgba(0,0,0,0.15);
        width: 380px;
        margin: auto;
    }

    .stButton > button {
        background-color: #43a047 !important;
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 0.6rem;
        font-weight: bold;
    }

    .stButton > button:hover {
        background-color: #2e7d32 !important;
    }

    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #ccc;
    }

    /* Títulos */
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) h1, 
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) h2,
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) h3,
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) .stSubheader {
        color: #1b5e20 !important;
        text-align: center;
    }

    /* Centraliza o logotipo na direita */
    .login-logo-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height:0vh !important; 
        width: 300%;
        text-align: center;
    }

    .login-logo-container img {
        max-width:15%; /* Mantido */
        height: auto;
        border-radius: 30%;
        -webkit-mask-image: -webkit-radial-gradient(white, black);
        mask-image: radial-gradient(white, black);
        filter: brightness(1.2) contrast(1.1);
        box-shadow: 0 0 15px rgba(0,0,0,0.3);
        display: block; /* Adicionado para garantir centralização */
        margin: auto; /* Adicionado para garantir centralização */
    }
    </style>
    """, unsafe_allow_html=True)

    # --- IMAGEM PRINCIPAL ---
    try:
        imagem_principal = Image.open("Foto 2.jpg")
    except Exception:
        st.error("Não foi possível carregar 'Foto 2.jpg'.")
        imagem_principal = None

    # --- Layout (duas colunas) ---
    col1, col2 = st.columns([1, 1], gap="small") 

    # --- Coluna esquerda (Login) ---
    with col1:
        st.subheader("Seja bem vindo à plataforma de gestão de projetos Allarmi")     
        st.subheader("Acesse sua conta")
        st.write("") 

        with st.form("form_login"):
            nome = st.text_input("Nome", key="login_nome")
            email = st.text_input("E-mail", key="login_email")
            
            # Lógica de validação simples (funcional do usuário)
            if st.form_submit_button("Entrar"):
                # Validação usando a função utils
                if utils.validar_usuario(nome.strip(), email.strip()):
                    st.session_state["autenticado"] = True # Pode remover se não usar em outro lugar
                    st.success(f"Acesso liberado! Bem-vindo, {nome.strip()} 👋")
                    
                    # Define os estados para a próxima tela
                    st.session_state.update(
                        usuario=nome.strip(), 
                        logado=True, 
                        boas_vindas=True, 
                        tela_principal=False
                    )
                    # Adiciona a pausa antes do rerun (importante!)
                    time.sleep(1) 
                    st.rerun()
                else:
                    st.error("Acesso negado, tente novamente")
                
    # --- Coluna direita (Logo) ---
    with col2:
        # Envolve a imagem no div para aplicar o CSS
        st.markdown('<div class="login-logo-container">', unsafe_allow_html=True)
        if imagem_principal:
            # st.image agora dentro do div
            st.image(imagem_principal, use_container_width=True) 
        else:
             st.warning("Não foi possível carregar a imagem do logo.")
        st.markdown('</div>', unsafe_allow_html=True) # Fecha o div

# ----------------- Função: Tela de Cadastro de Usuário -----------------#
def tela_cadastro_usuario():
    st.subheader("Cadastrar Novo Usuário")

    # Usar colunas para limitar a largura do formulário
    col1, col2 = st.columns([1, 2]) 
    with col1:
        # Adicionado clear_on_submit=True para limpar o form após o cadastro
        with st.form("form_cadastro_usuario", clear_on_submit=True): 
            nome = st.text_input("Nome", key="cad_nome")
            email = st.text_input("Email", key="cad_email")
            senha = st.text_input("Senha (opcional)", type="password", key="cad_senha")
            
            if st.form_submit_button("Cadastrar"):
                if not nome or not email:
                    st.error("Preencha Nome e Email.")
                    return
                
                df = utils.carregar_usuarios_db() 

                # Padroniza os nomes das colunas para "Capitalized" (ex: "email" -> "Email")
                if not df.empty:
                    df.columns = [col.capitalize() for col in df.columns]

                # Agora verificamos se o email existe na coluna padronizada "Email"
                email_check_list = []
                if not df.empty and "Email" in df.columns:
                    email_check_list = df["Email"].astype(str).str.lower().values

                if email.lower() in email_check_list:
                
                    st.error("Email já cadastrado!")
                else:
                    nova_linha = pd.DataFrame([[nome, email, senha]], columns=["Nome", "Email", "Senha"]) 
                    df_novo = pd.concat([df, nova_linha], ignore_index=True)

                    if utils.salvar_usuario_db(df_novo): 
                        st.success("Usuário cadastrado com sucesso!")
                        st.rerun() # Adicionado para atualizar a lista de usuários abaixo
                    else:
                        st.error("Erro ao salvar usuário no banco de dados.")
    with col2:
        st.empty()

# ----------------- Função: Tela de Configurações -----------------
def tela_configuracoes():
    
    if st.button("⬅️ Voltar para Projetos"):
        st.session_state.tela_configuracoes = False
        st.rerun()
        
    st.title("Configurações do Sistema")
        
    tela_cadastro_usuario() 
    
    st.divider()
    
    # 2. Adicionar a visualização de usuários
    st.subheader("Visualizar Usuários Cadastrados")
    try:
        df_users = utils.carregar_usuarios_db()
        if not df_users.empty:
            
            # Padroniza as colunas (ex: "nome" -> "Nome", "email" -> "Email")
            df_users.columns = [col.capitalize() for col in df_users.columns]
            
            # Colunas que queremos mostrar (ignora "Senha" e outras)
            cols_to_show = [col for col in ["Nome", "Email"] if col in df_users.columns]
            
            if not cols_to_show:
                st.warning("O arquivo de usuários existe, mas não contém as colunas 'Nome' ou 'Email'.")
            else:
                st.dataframe(df_users[cols_to_show], use_container_width=True)
            
        else:
            st.info("Nenhum usuário cadastrado ainda.")
    except Exception as e:
        st.error(f"Não foi possível carregar usuários: {e}")
        
# ----------------- Função: Tela de Boas-Vindas -----------------
def tela_boas_vindas():
    mensagens = [
        "Que seu dia seja produtivo e cheio de conquistas!",
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

# ----------------- COCKPIT -----------------
def tela_cockpit():
    # Sidebar de Ações
    st.sidebar.title(f"Olá, {st.session_state.get('usuario','User')}")
    st.sidebar.divider()
    st.sidebar.header("📥 Importações")
    if st.sidebar.button("📂 Chamados"): run_importer_dialog()
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
                st.switch_page("pages/1_📊_Gestao_Projetos.py")

# --- FUNÇÃO TELA DE CADASTRO DE PROJETOS ---
def tela_cadastro_projeto():
    st.markdown("### ➕ Novo Chamado")
    
    # Botão de Voltar
    if st.button("⬅️ Cancelar / Voltar"):
        st.session_state.tela_cadastro_proj = False
        st.rerun()

    with st.form("form_novo_chamado"):
        c1, c2 = st.columns(2)
        with c1:
            novo_chamado = st.text_input("Nº Chamado *", placeholder="Ex: GTS-123456")
            novo_projeto = st.text_input("Nome do Projeto *", placeholder="Ex: MODERNIZAÇÃO CFTV")
            nova_agencia_cod = st.text_input("Cód. Agência *", placeholder="Ex: 1234")
            nova_agencia_nome = st.text_input("Nome Agência", placeholder="Ex: AGENCIA CENTRO")
            novo_analista = st.text_input("Analista Responsável", value=st.session_state.get('usuario', ''))
        
        with c2:
            novo_servico = st.text_input("Tipo de Serviço", placeholder="Ex: Instalação, Vistoria...")
            novo_sistema = st.text_input("Sistema", placeholder="Ex: CFTV, Alarme...")
            nova_data_abertura = st.date_input("Data de Abertura", value=date.today())
            novo_agendamento = st.date_input("Data Agendamento (Opcional)", value=None)
            novo_link = st.text_input("Link Externo (Monday/Trello)", placeholder="https://...")

        st.markdown("---")
        st.markdown("**Detalhes do Equipamento (Opcional)**")
        c3, c4, c5 = st.columns([1, 3, 1])
        with c3: qtd_eq = st.number_input("Qtd", min_value=1, value=1)
        with c4: desc_eq = st.text_input("Descrição Equipamento / Item")
        with c5: cod_eq = st.text_input("Cód. Item")

        observacao = st.text_area("Observações Iniciais", height=80)

        submitted = st.form_submit_button("💾 Salvar Chamado", use_container_width=True, type="primary")

        if submitted:
            # Validação Básica
            if not novo_chamado or not novo_projeto or not nova_agencia_cod:
                st.error("Campos obrigatórios: Nº Chamado, Projeto e Cód. Agência.")
                return

            # Monta o dicionário de dados
            dados_novo = {
                "Nº Chamado": novo_chamado,
                "Projeto": novo_projeto,
                "Cód. Agência": nova_agencia_cod,
                "Nome Agência": nova_agencia_nome,
                "Analista": novo_analista,
                "Serviço": novo_servico,
                "Sistema": novo_sistema,
                "Data Abertura": nova_data_abertura,
                "Agendamento": novo_agendamento,
                "Link Externo": novo_link,
                "Qtd.": str(qtd_eq),
                "Equipamento": desc_eq,
                "Descrição": f"{qtd_eq} - {desc_eq}" if desc_eq else "",
                "Cód. Equip.": cod_eq,
                "Observação": observacao,
                "Status": "AGENDADO" if novo_agendamento else "PENDÊNCIA", # Define status inicial
                "Sub-Status": "Aguardando início"
            }
            
            df_salvar = pd.DataFrame([dados_novo])
            
            # Adiciona colunas faltantes vazias para não quebrar o bulk_insert
            sucesso, qtd = utils_chamados.bulk_insert_chamados_db(df_salvar)
            
            if sucesso:
                st.success(f"Chamado {novo_chamado} cadastrado com sucesso!")
                time.sleep(1.5)
                st.session_state.tela_cadastro_proj = False
                st.rerun()
            else:
                st.error("Erro ao salvar no banco de dados.")

# ----------------- MAIN (CORRIGIDO) -----------------
def main():
    if "logado" not in st.session_state: st.session_state.logado = False
    if "boas_vindas" not in st.session_state: st.session_state.boas_vindas = False
    if "tela_cadastro_proj" not in st.session_state: st.session_state.tela_cadastro_proj = False
        
    if not st.session_state.logado:
        tela_login()
        
    elif st.session_state.boas_vindas:
        tela_boas_vindas()
        
    else:
        with st.sidebar:
            st.title(f"Olá, {st.session_state.get('usuario','User')}")
            st.sidebar.divider()
            st.header("📥 Importações")
            if st.button("📂 Planilha Padrão", use_container_width=True): run_importer_dialog()
            if st.button("🚚 Pedidos", use_container_width=True): run_pedido_importer_dialog()
            if st.button("🔗 Links", use_container_width=True): run_link_importer_dialog()
            st.divider()
            st.header("📝 Cadastros")
            # Botão que ativa a tela de cadastro manual
            if st.button("➕ Novo Chamado Manual", use_container_width=True):
                st.session_state.tela_cadastro_proj = True
                st.rerun()
             st.sidebar.divider() 
             st.sidebar.title("Sistema")
             if st.sidebar.button("➕ Usuários", use_container_width=True):
                 st.session_state.tela_configuracoes = True
                 st.session_state.tela_cadastro_proj = False 
                 st.rerun()               
            st.divider()
            if st.button("Logout", type="primary", use_container_width=True):
                st.session_state.clear()
                st.rerun()

        if st.session_state.get("tela_cadastro_proj"):
            tela_cadastro_projeto()
        else:
            tela_cockpit()

if __name__ == "__main__":
    utils.criar_tabelas_iniciais() 
    main()
