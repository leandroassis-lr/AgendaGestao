import streamlit as st
import pandas as pd
from datetime import date, datetime
import random
import time
from PIL import Image
import re
import html

# Importa TODAS as nossas funções do arquivo utils.py
import utils 

# ----------------- Helpers -----------------
def _to_date_safe(val):
    """Converte várias representações (str, pd.Timestamp, datetime, date) para datetime.date ou None."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    try:
        ts = pd.to_datetime(val, errors='coerce')
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None


# ----------------- Configuração da Página e CSS -----------------
st.set_page_config(page_title="Projetos - GESTÃO", page_icon="📋", layout="wide")
utils.load_css() # Carrega o CSS do arquivo utils (Certifique-se que seu CSS está atualizado)


# ----------------- Função: Tela de Login (Versão Funcional do Usuário) -----------------
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

    /* Estilo do formulário (IMPORTANTE: Mantenha esta regra sem o '.main' na frente, 
       pois ela é específica para o CSS injetado aqui na tela_login) */
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
        height: 65vh !important; 
        width: 110%;
        text-align: center;
    }

    .login-logo-container img {
        max-width:100%; /* Mantido */
        height: auto;
        border-radius: 50%;
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

# ----------------- Função: Tela de Cadastro de Usuário (Sem alterações) -----------------#
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

# ----------------- Função: Tela de Configurações (Sem alterações) -----------------
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
        
# ----------------- Função: Tela de Boas-Vindas (Sem alterações) -----------------
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

# --- FUNÇÃO TELA_CADASTRO_PROJETO (ATUALIZADA com Selectbox) ---
# (Substituindo a versão original do usuário por esta)
def tela_cadastro_projeto():
    if st.button("⬅️ Voltar para Projetos"):
        st.session_state.tela_cadastro_proj = False
        st.rerun()
    st.subheader("Cadastrar Novo Projeto")
    
    # --- 1. CARREGAR LISTAS DE OPÇÕES ---
    perguntas_customizadas = utils.carregar_config_db("perguntas") 
    
    agencias_cfg = utils.carregar_config_db("agencias")
    tecnicos_cfg = utils.carregar_config_db("tecnicos")
    
    # (Usando o nome da tabela que você confirmou: "projetos_nomes")
    projetos_cfg = utils.carregar_config_db("projetos_nomes") 

    # Prepara as listas de opções
    agencia_options = ["N/A"] + (agencias_cfg.iloc[:, 0].tolist() if not agencias_cfg.empty and len(agencias_cfg.columns) > 0 else [])
    tecnico_options = ["N/A"] + (tecnicos_cfg.iloc[:, 0].tolist() if not tecnicos_cfg.empty and len(tecnicos_cfg.columns) > 0 else [])
    projeto_options = ["N/A"] + (projetos_cfg.iloc[:, 0].tolist() if not projetos_cfg.empty and len(projetos_cfg.columns) > 0 else [])
    
    # ----------------------------------------
    
    if perguntas_customizadas.empty or 'Pergunta' not in perguntas_customizadas.columns:
        st.info("🚨 Nenhuma pergunta customizada configurada. (Vá para Configurações > Gerenciar Listas)")
        return

    with st.form("form_cadastro_projeto"):
        respostas_customizadas = {}
        
        for index, row in perguntas_customizadas.iterrows():
            pergunta = row['Pergunta']
            tipo = row.get('Tipo (texto, numero, data)', 'texto')
            key = utils.clean_key(pergunta)
            
            # Normaliza o nome da pergunta para verificação
            pergunta_norm = pergunta.lower().strip() 

            # --- 2. LÓGICA DE INTERCEPTAÇÃO ---
            
            if pergunta_norm == 'agência':
                respostas_customizadas[pergunta] = st.selectbox(
                    pergunta, 
                    options=agencia_options, 
                    key=f"custom_{key}",
                    help="Selecione a agência da lista."
                )
            
            elif pergunta_norm == 'técnico':
                respostas_customizadas[pergunta] = st.selectbox(
                    pergunta, 
                    options=tecnico_options, 
                    key=f"custom_{key}",
                    help="Selecione o técnico da lista."
                )
            
            # Verifica por "projeto" ou "nome do projeto"
            elif pergunta_norm == 'projeto' or pergunta_norm == 'nome do projeto':
                respostas_customizadas[pergunta] = st.selectbox(
                    pergunta, 
                    options=projeto_options, 
                    key=f"custom_{key}",
                    help="Selecione o tipo de projeto da lista."
                )
            
            # --- FIM DA LÓGICA ---
            
            # Lógica original para outros tipos de pergunta
            elif tipo == 'data': 
                respostas_customizadas[pergunta] = st.date_input(pergunta, value=None, key=f"custom_{key}", format="DD/MM/YYYY")
            elif tipo == 'numero': 
                respostas_customizadas[pergunta] = st.number_input(pergunta, key=f"custom_{key}", step=1)
            else: 
                # O padrão para qualquer outra pergunta de texto
                respostas_customizadas[pergunta] = st.text_input(pergunta, key=f"custom_{key}")
                
        btn_cadastrar = st.form_submit_button("Cadastrar Projeto")
    
    if btn_cadastrar:
        
        # --- 3. LÓGICA DE SALVAMENTO ATUALIZADA ---
        
        projeto_nome_key = next((p for p in respostas_customizadas if p.lower().strip() in ['nome do projeto', 'projeto']), None)
        agencia_key = next((p for p in respostas_customizadas if p.lower().strip() == 'agência'), None)
        tecnico_key = next((p for p in respostas_customizadas if p.lower().strip() == 'técnico'), None)

        # Validação
        projeto_nome = respostas_customizadas.get(projeto_nome_key) if projeto_nome_key else "N/A"
        agencia_nome = respostas_customizadas.get(agencia_key) if agencia_key else "N/A"
        tecnico_nome = respostas_customizadas.get(tecnico_key) if tecnico_key else "N/A"
        
        # Verifica se alguma das chaves não foi encontrada E se o valor é N/A
        if (not projeto_nome_key or projeto_nome == "N/A") or \
           (not agencia_key or agencia_nome == "N/A") or \
           (not tecnico_key or tecnico_nome == "N/A"):
             st.error("ERRO: 'Projeto', 'Agência' e 'Técnico' são campos obrigatórios e devem estar configurados nas perguntas. Selecione uma opção válida.")
             st.stop() # Impede o cadastro
        
        # Se passou na validação, continua o cadastro
        nova_linha_data = {
            "Status": "NÃO INICIADA",
            "Data de Abertura": date.today(),
            "Analista": st.session_state.get('usuario', 'N/A'),
            "Projeto": projeto_nome  # Usa o nome do projeto selecionado
        }
        
        # Adiciona todas as outras respostas do formulário
        nova_linha_data.update(respostas_customizadas)

        if utils.adicionar_projeto_db(nova_linha_data):
            st.success(f"Projeto '{projeto_nome}' cadastrado!")
            st.session_state["tela_cadastro_proj"] = False
            st.rerun()

# ----------------- FUNÇÃO TELA_PROJETOS (Original do usuário) ----------------- 
# (Mantendo a versão original que estava funcionando para o usuário)
def tela_projetos():
    st.markdown("<div class='section-title-center'>PROJETOS</div>", unsafe_allow_html=True)
    
    df = utils.carregar_projetos_db()
    
    df_sla = utils.carregar_config_db("sla") 
    df_etapas_config = utils.carregar_config_db("etapas_evolucao") 
    
    if df.empty:
        st.info("Nenhum projeto cadastrado ainda.")
        return

    # --- Conversão de Datas ---
    df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce')
    df['Agendamento_str'] = df['Agendamento'].dt.strftime("%d/%m/%y").fillna('N/A')

    # --- Início dos Filtros ---
    st.markdown("#### 🔍 Filtros e Busca")
    termo_busca = st.text_input("Buscar", key="termo_busca", placeholder="Digite um termo para buscar...")

    filtros = {} # Inicializa o dicionário de filtros

    # --- Linha 1 de Filtros: Status, Analista, Agência, Gestor ---
    col1, col2, col3, col4 = st.columns(4)
    campos_linha_1 = {"Status": col1, "Analista": col2, "Agência": col3, "Gestor": col4}
    
    for campo, col in campos_linha_1.items():
        with col:
            if campo in df.columns: 
                # Tratamento para evitar erro se a coluna tiver apenas NaN ou None
                unique_values = df[campo].dropna().astype(str).unique()
                opcoes = ["Todos"] + sorted(unique_values.tolist())
                filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")
            else:
                st.empty() # Ocupa o espaço se a coluna não existir no DB

    # --- Linha 2 de Filtros: Projeto, Técnico, Data Início, Data Fim ---
    col5, col6, col7, col8 = st.columns(4) # Nova linha de colunas
    
    # Filtro Projeto (col5)
    with col5:
        campo = "Projeto"
        if campo in df.columns:
            unique_values = df[campo].dropna().astype(str).unique()
            opcoes = ["Todos"] + sorted(unique_values.tolist())
            filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")
        else:
            st.empty()

    # Filtro Técnico (col6)
    with col6:
        campo = "Técnico"
        if campo in df.columns:
            unique_values = df[campo].dropna().astype(str).unique()
            opcoes = ["Todos"] + sorted(unique_values.tolist())
            filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")
        else:
            st.empty()
            
    # Filtros de Data (col7 e col8)
    with col7:
        data_inicio = st.date_input(
            "Agendamento (de)", 
            value=None, 
            key="data_inicio_filtro", 
            format="DD/MM/YYYY"
        )
        
    with col8:
        data_fim = st.date_input(
            "Agendamento (até)", 
            value=None, 
            key="data_fim_filtro", 
            format="DD/MM/YYYY"
        )

    # --- Lógica de Aplicação dos Filtros ---
    df_filtrado = df.copy()
    
    # 1. Aplica filtros de selectbox (Status, Analista, etc.)
    for campo, valor in filtros.items():
        if valor != "Todos" and campo in df_filtrado.columns:
            # Garante comparação como string e lida com possíveis NaNs
            df_filtrado = df_filtrado[df_filtrado[campo].astype(str) == str(valor)]

    # 2. Aplica filtro de Data de Início
    if data_inicio:
        df_filtrado = df_filtrado[
            (df_filtrado['Agendamento'].notna()) & 
            (df_filtrado['Agendamento'] >= pd.to_datetime(data_inicio))
        ]
    # 3. Aplica filtro de Data de Fim
    if data_fim:
        df_filtrado = df_filtrado[
            (df_filtrado['Agendamento'].notna()) & 
            (df_filtrado['Agendamento'] <= pd.to_datetime(data_fim).replace(hour=23, minute=59, second=59))
        ]

    # 4. Aplica filtro de texto (busca)
    if termo_busca:
        termo = termo_busca.lower().strip()
        # Aplica a busca em todas as colunas convertidas para string
        mask_busca = df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(termo, na=False, regex=False).any(), axis=1)
        df_filtrado = df_filtrado[mask_busca]
    
    st.divider()
    col_info_export, col_export_btn = st.columns([4, 1.2])
    total_items = len(df_filtrado)
    with col_info_export:
        st.info(f"Projetos encontrados: {total_items}")
    with col_export_btn:
        excel_bytes = utils.dataframe_to_excel_bytes(df_filtrado)
        st.download_button(
            label="📥 Exportar para Excel",
            data=excel_bytes,
            file_name=f"projetos_{date.today().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    st.divider()
    
    items_per_page = 10
    if 'page_number' not in st.session_state:
        st.session_state.page_number = 0
    
    total_pages = (total_items // items_per_page) + (1 if total_items % items_per_page > 0 else 0)
    if total_pages == 0: total_pages = 1
    
    # Corrige a página se os filtros mudarem e a página atual ficar inválida
    if st.session_state.page_number >= total_pages:
        st.session_state.page_number = 0

    start_idx = st.session_state.page_number * items_per_page
    end_idx = start_idx + items_per_page
    
    df_paginado = df_filtrado.iloc[start_idx:end_idx]
    
    # Carrega opções para os dropdowns de edição DENTRO do loop (ou aqui, se forem fixas)
    agencias_cfg = utils.carregar_config_db("agencias")
    tecnicos_cfg = utils.carregar_config_db("tecnicos")
    status_options_df = utils.carregar_config_db("status")
    
    agencia_options = ["N/A"] + (agencias_cfg.iloc[:, 0].tolist() if not agencias_cfg.empty and len(agencias_cfg.columns) > 0 else [])
    tecnico_options = ["N/A"] + (tecnicos_cfg.iloc[:, 0].tolist() if not tecnicos_cfg.empty and len(tecnicos_cfg.columns) > 0 else [])
    status_options = status_options_df.iloc[:, 0].tolist() if not status_options_df.empty and len(status_options_df.columns) > 0 else []

    # --- Loop para exibir os cards ---
    for _, row in df_paginado.iterrows():
        project_id = row['ID']
        
        # Sanitiza os dados para exibição segura
        status_raw = row.get('Status', 'N/A')
        status_text = html.escape(str(status_raw))
        analista_text = html.escape(str(row.get('Analista', 'N/A')))
        agencia_text = html.escape(str(row.get("Agência", "N/A")))
        projeto_text = html.escape(str(row.get("Projeto", "N/A")))
        
        status_color_name = utils.get_status_color(str(status_raw))
        sla_text, sla_color = utils.calcular_sla(row, df_sla)

        # --- Cabeçalho do Card ---
        st.markdown("<div class='project-card'>", unsafe_allow_html=True)
        col_info_card, col_analista_card, col_agencia_card, col_status_card = st.columns([3, 2, 2, 1.5])
        with col_info_card:
            # Usa Agendamento_str que já tratou NaT/None
            st.markdown(f"<h6>📅 {row.get('Agendamento_str', 'N/A')}</h6>", unsafe_allow_html=True) 
            st.markdown(f"<h5 style='margin:2px 0'>{projeto_text.upper()}</h5>", unsafe_allow_html=True)
            
        with col_analista_card:
            st.markdown(f"**Analista:** {analista_text}")
            st.markdown(f"<p style='color:{sla_color}; font-weight:bold;'>{sla_text}</p>", unsafe_allow_html=True)
            
        with col_agencia_card:
            st.markdown(f"**Agência:** {agencia_text}") 
            
        with col_status_card:
            # Botão de Status
            st.markdown(
                f"""<div style="height:100%;display:flex;align-items:center;justify-content:flex-end;">
                <span style="background-color:{status_color_name};color:black;padding:8px 15px;border-radius:5px;font-weight:bold;font-size:0.9em;">{status_text}</span>
                </div>""",
                unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True) # Fecha o div 'project-card'

        # --- Expander com Formulário de Edição ---
        with st.expander(f"Ver/Editar Detalhes - ID: {project_id}"):
            with st.form(f"form_edicao_card_{project_id}"):
                
                # --- Seção de Evolução ---
                st.markdown("#### Evolução da Demanda")
                # Lógica para buscar etapas específicas do projeto
                etapas_do_projeto = df_etapas_config[df_etapas_config["Nome do Projeto"] == row.get("Projeto", "")] if "Nome do Projeto" in df_etapas_config.columns else pd.DataFrame()
                
                # Trata 'Etapas Concluidas' que podem ser NaN ou None
                etapas_concluidas_str = row.get("Etapas Concluidas", "")
                etapas_concluidas_lista = []
                if pd.notna(etapas_concluidas_str) and isinstance(etapas_concluidas_str, str) and etapas_concluidas_str.strip():
                     etapas_concluidas_lista = [e.strip() for e in etapas_concluidas_str.split(',') if e.strip()]

                novas_etapas_marcadas = []
                if not etapas_do_projeto.empty and "Etapa" in etapas_do_projeto.columns:
                    total_etapas = len(etapas_do_projeto)
                    num_etapas_concluidas = len(etapas_concluidas_lista)
                    progresso = num_etapas_concluidas / total_etapas if total_etapas > 0 else 0
                    st.progress(progresso)
                    st.caption(f"{num_etapas_concluidas} de {total_etapas} etapas concluídas ({progresso:.0%})")
                    
                    # Gera os checkboxes
                    for etapa in etapas_do_projeto["Etapa"]:
                        etapa_str = str(etapa).strip() # Garante que é string
                        marcado = st.checkbox(
                            etapa_str, 
                            value=(etapa_str in etapas_concluidas_lista), 
                            key=f"chk_{project_id}_{utils.clean_key(etapa_str)}"
                        )
                        if marcado: 
                            novas_etapas_marcadas.append(etapa_str)
                else:
                    st.caption("Nenhuma etapa de evolução configurada para este tipo de projeto.")

                # --- Seção de Informações e Prazos ---
                st.markdown("#### Informações e Prazos")
                c1,c2,c3,c4 = st.columns(4)
                with c1:
                    status_selecionaveis = status_options[:] # Cria cópia
                    status_atual = row.get('Status')
                    # Lógica para permitir voltar status (opcional, remova se não quiser)
                    # if status_atual != 'NÃO INICIADA':
                    #     if 'NÃO INICIADA' in status_selecionaveis: 
                    #         status_selecionaveis.remove('NÃO INICIADA')
                    
                    # Encontra o índice do status atual, tratando caso não exista
                    try:
                        idx_status = status_selecionaveis.index(status_atual) if status_atual in status_selecionaveis else 0
                    except ValueError:
                        idx_status = 0 # Padrão se o status atual não estiver na lista
                        
                    novo_status_selecionado = st.selectbox("Status", status_selecionaveis, index=idx_status, key=f"status_{project_id}")
                with c2:
                    abertura_default = _to_date_safe(row.get('Data de Abertura'))
                    nova_data_abertura = st.date_input("Data Abertura", value=abertura_default, key=f"abertura_{project_id}", format="DD/MM/YYYY")
                with c3:
                    agendamento_default = _to_date_safe(row.get('Agendamento')) 
                    novo_agendamento = st.date_input("Agendamento", value=agendamento_default, key=f"agend_{project_id}", format="DD/MM/YYYY")
                with c4:
                    finalizacao_default = _to_date_safe(row.get('Data de Finalização'))
                    nova_data_finalizacao = st.date_input("Data Finalização", value=finalizacao_default, key=f"final_{project_id}", format="DD/MM/YYYY")

                # --- Seção de Detalhes do Projeto ---
                st.markdown("#### Detalhes do Projeto")
                c5,c6,c7 = st.columns(3)
                with c5: novo_projeto = st.text_input("Projeto", value=row.get('Projeto', ''), key=f"proj_{project_id}")
                with c6: novo_analista = st.text_input("Analista", value=row.get('Analista', ''), key=f"analista_{project_id}")
                with c7: novo_gestor = st.text_input("Gestor", value=row.get('Gestor', ''), key=f"gestor_{project_id}")
                c8,c9 = st.columns(2)
                with c8: 
                    agencia_val = row.get('Agência', '')
                    idx_ag = agencia_options.index(agencia_val) if agencia_val in agencia_options else 0
                    nova_agencia = st.selectbox("Agência", agencia_options, index=idx_ag, key=f"agencia_{project_id}")
                with c9:
                    tecnico_val = row.get('Técnico', '')
                    idx_tec = tecnico_options.index(tecnico_val) if tecnico_val in tecnico_options else 0
                    novo_tecnico = st.selectbox("Técnico", tecnico_options, index=idx_tec, key=f"tecnico_{project_id}")

                # --- Campos de Texto Longo ---
                nova_demanda = st.text_input("Demanda", value=row.get('Demanda', ''), key=f"demanda_{project_id}")
                nova_descricao = st.text_area("Descrição", value=row.get('Descrição', ''), key=f"desc_{project_id}")
                nova_observacao = st.text_area("Observação / Pendências", value=row.get('Observação', ''), key=f"obs_{project_id}")
                
                # Log de Agendamento (Apenas exibição)
                log_agendamento_existente = row.get("Log Agendamento", "") if pd.notna(row.get("Log Agendamento")) else ""
                st.text_area("Histórico de Agendamento", value=log_agendamento_existente, height=100, disabled=True, key=f"log_{project_id}")

                # --- Botões Salvar e Excluir ---
                _, col_save, col_delete = st.columns([3, 1.5, 1]) 
                with col_save:
                    btn_salvar_card = st.form_submit_button("💾 Salvar", use_container_width=True)
                with col_delete:
                    btn_excluir_card = st.form_submit_button("🗑️ Excluir", use_container_width=True, type="primary")

                # --- Lógica de Ação dos Botões ---
                if btn_excluir_card:
                    if utils.excluir_projeto_db(project_id):
                        st.success(f"Projeto ID {project_id} excluído.") # Feedback
                        st.rerun()
                
                if btn_salvar_card:
                    # Lógica de atualização de Status
                    status_final = novo_status_selecionado
                    if row.get('Status') == 'NÃO INICIADA' and len(novas_etapas_marcadas) > 0 and status_final == 'NÃO INICIADA':
                        status_final = 'EM ANDAMENTO' # Muda automaticamente se marcar etapa
                        st.info("Status alterado para 'EM ANDAMENTO' pois uma etapa foi marcada.")
                    
                    # Converte datas para objetos date ou None
                    nova_data_abertura_date = _to_date_safe(nova_data_abertura)
                    nova_data_finalizacao_date = _to_date_safe(nova_data_finalizacao)
                    novo_agendamento_date = _to_date_safe(novo_agendamento)

                    # Validações ao finalizar
                    if 'finalizad' in status_final.lower():
                        total_etapas_config = len(etapas_do_projeto)
                        if total_etapas_config > 0 and len(novas_etapas_marcadas) < total_etapas_config:
                            st.error(f"ERRO: Para finalizar, todas as {total_etapas_config} etapas devem ser marcadas.", icon="🚨")
                            st.stop() # Interrompe salvamento
                        if not nova_data_finalizacao_date:
                            st.error("ERRO: Se o status é 'Finalizada', a Data de Finalização é obrigatória.", icon="🚨")
                            st.stop() # Interrompe salvamento
                    
                    # Atualiza Log de Agendamento
                    log_final = row.get("Log Agendamento", "") if pd.notna(row.get("Log Agendamento")) else ""
                    agendamento_antigo_date = _to_date_safe(row.get('Agendamento'))

                    # Compara datas corretamente (ambas como date ou None)
                    if novo_agendamento_date != agendamento_antigo_date:
                        data_antiga_str = agendamento_antigo_date.strftime('%d/%m/%Y') if agendamento_antigo_date else "N/A"
                        data_nova_str = novo_agendamento_date.strftime('%d/%m/%Y') if novo_agendamento_date else "N/A"
                        hoje_str = date.today().strftime('%d/%m/%Y')
                        usuario_logado = st.session_state.get('usuario', 'Sistema') # Pega o usuário logado
                        nova_entrada_log = f"Em {hoje_str} por {usuario_logado}: alterado de '{data_antiga_str}' para '{data_nova_str}'."
                        log_final = f"{log_final}\n{nova_entrada_log}".strip()

                    # Monta o dicionário de atualizações
                    updates = {
                        "Status": status_final, 
                        "Agendamento": novo_agendamento_date, # Salva como date ou None
                        "Analista": novo_analista,
                        "Agência": nova_agencia if nova_agencia != "N/A" else None, # Salva None se for N/A
                        "Gestor": novo_gestor, 
                        "Projeto": novo_projeto,
                        "Técnico": novo_tecnico if novo_tecnico != "N/A" else None, # Salva None se for N/A
                        "Demanda": nova_demanda, 
                        "Descrição": nova_descricao,
                        "Observação": nova_observacao, 
                        "Data de Abertura": nova_data_abertura_date, # Salva como date ou None
                        "Data de Finalização": nova_data_finalizacao_date, # Salva como date ou None
                        "Etapas Concluidas": ",".join(novas_etapas_marcadas) if novas_etapas_marcadas else None, # Salva None se vazio
                        "Log Agendamento": log_final if log_final else None # Salva None se vazio
                    }

                    # Chama a função de atualização no utils
                    if utils.atualizar_projeto_db(project_id, updates):
                        st.success(f"Projeto '{novo_projeto}' (ID: {project_id}) atualizado.")
                        st.rerun()
                    # else: (O erro já é mostrado pelo utils.atualizar_projeto_db)

    # --- Paginação ---
    st.divider()
    if total_pages > 1:
        col_info_pag, col_prev_pag, col_next_pag = st.columns([5, 1.5, 1.5]) 
        with col_info_pag:
            st.markdown(f"<div style='text-align: left; margin-top: 10px;'>Página <b>{st.session_state.page_number + 1}</b> de <b>{total_pages}</b></div>", unsafe_allow_html=True)
        with col_prev_pag:
            if st.button("⬅️ Anterior", use_container_width=True, disabled=(st.session_state.page_number == 0)):
                st.session_state.page_number -= 1
                st.rerun()
        with col_next_pag:
            if st.button("Próxima ➡️", use_container_width=True, disabled=(st.session_state.page_number >= total_pages - 1)):
                st.session_state.page_number += 1
                st.rerun()
                
# ----------------- FUNÇÃO MAIN (ATUALIZADA) -----------------
# (Com roteamento corrigido e botão "Usuários")

def main():
    # Inicializa os estados da sessão (é bom ter todos aqui)
    if "logado" not in st.session_state: st.session_state.logado = False
    if "cadastro" not in st.session_state: st.session_state.cadastro = False # Embora não usado, mantém por segurança
    if "boas_vindas" not in st.session_state: st.session_state.boas_vindas = False 
    if "tela_principal" not in st.session_state: st.session_state.tela_principal = False
    if "tela_cadastro_proj" not in st.session_state: st.session_state.tela_cadastro_proj = False
    if "tela_configuracoes" not in st.session_state: st.session_state.tela_configuracoes = False
    if "usuario" not in st.session_state: st.session_state.usuario = None # Inicializa usuário

    # --- LÓGICA PRINCIPAL DE ROTEAMENTO (CORRIGIDA) ---
    
    if not st.session_state.logado:
        # ROTA 1: Não logado -> Tela de Login
        tela_login()

    elif st.session_state.boas_vindas:
        # ROTA 2: Logado + Boas Vindas -> Tela de Boas Vindas
        tela_boas_vindas()

    elif st.session_state.tela_principal:
        # ROTA 3: Logado + Principal -> App Principal (com Sidebar)
        
        # --- Sidebar ---
        st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}")
        st.sidebar.divider()
        
        st.sidebar.title("Ações")
        
        if st.sidebar.button("➕ Novo Projeto", use_container_width=True):
            st.session_state.tela_cadastro_proj = True
            st.session_state.tela_configuracoes = False 
            st.rerun()
            
        st.sidebar.divider() # Adicionei um divider para separar melhor
        st.sidebar.title("Sistema")
        
        # Botão renomeado:
        if st.sidebar.button("➕ Usuários", use_container_width=True):
            st.session_state.tela_configuracoes = True
            st.session_state.tela_cadastro_proj = False 
            st.rerun()
            
        # O botão de Configurações foi removido pois virou "Usuários"
        # Se precisar de um botão separado para outras configs, adicione aqui.
            
        if st.sidebar.button("Logout", use_container_width=True, type="primary"):
            st.session_state.clear() # Limpa TUDO
            st.rerun()
    
        # --- Lógica de Exibição da Página (dentro da ROTA 3) ---
        if st.session_state.get("tela_configuracoes"):
            tela_configuracoes() 
        elif st.session_state.get("tela_cadastro_proj"):
            tela_cadastro_projeto() 
        else:
            # Tela Padrão se nenhuma outra estiver ativa
            tela_projetos() 
            
    else:
        # ROTA 4 (Segurança): Se logado=True mas nenhum outro estado, força logout/login
        st.session_state.clear() # Limpa para evitar loops
        st.session_state.logado = False
        st.rerun()

# --- PONTO DE ENTRADA DO APP ---
if __name__ == "__main__":
    main()












