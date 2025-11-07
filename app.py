import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta 
import random
import time
from PIL import Image
import re
import html
import utils 

# ----------------- Helpers -----------------
def _to_date_safe(val):
    if val is None or pd.isna(val): return None
    if isinstance(val, date) and not isinstance(val, datetime): return val
    try:
        ts = pd.to_datetime(val, errors='coerce')
        if pd.isna(ts): return None
        return ts.date()
    except Exception: return None

# ----------------- Configuração da Página e CSS -----------------
st.set_page_config(page_title="Projetos - GESTÃO", page_icon="📋", layout="wide")
utils.load_css() 

# ----------------- Função Helper (KPIs) -----------------
def get_next_stage(row, etapas_config_df):
    projeto_nome = row.get("Projeto")
    if pd.isna(projeto_nome): return "Ignorado"
    if 'finalizad' in str(row.get('Status','')).lower() or 'cancelad' in str(row.get('Status','')).lower(): return "Ignorado"
    etapas_possiveis_df = etapas_config_df[etapas_config_df["Nome do Projeto"] == projeto_nome]
    if etapas_possiveis_df.empty or "Etapa" not in etapas_possiveis_df.columns: return "Sem Etapas" 
    todas_etapas_lista = etapas_possiveis_df["Etapa"].astype(str).str.strip().tolist()
    etapas_concluidas_str = row.get("Etapas Concluidas", ""); etapas_concluidas_set = set()
    if pd.notna(etapas_concluidas_str) and isinstance(etapas_concluidas_str, str) and etapas_concluidas_str.strip():
         etapas_concluidas_set = set(e.strip() for e in etapas_concluidas_str.split(',') if e.strip())
    proxima_etapa = next((etapa for etapa in todas_etapas_lista if etapa not in etapas_concluidas_set), None)
    if proxima_etapa: return proxima_etapa 
    elif len(todas_etapas_lista) > 0: return "Concluído" 
    else: return "Sem Etapas" 

# ----------------- Função: Tela de Login (ATUALIZADA) -----------------
def tela_login():
    # --- CSS (Ocultado por brevidade) ---
    st.markdown("""<style> ... (seu CSS de login aqui) ... </style>""", unsafe_allow_html=True) 
    try: imagem_principal = Image.open("Foto 2.jpg")
    except Exception: st.error("Não foi possível carregar 'Foto 2.jpg'."); imagem_principal = None
    col1, col2 = st.columns([1, 1], gap="small") 
    with col1:
        st.subheader("Seja bem vindo à plataforma de gestão de projetos Allarmi")     
        st.subheader("Acesse sua conta"); st.write("") 
        with st.form("form_login"):
            nome = st.text_input("Nome", key="login_nome")
            email = st.text_input("E-mail", key="login_email")
            if st.form_submit_button("Entrar"):
                # --- LÓGICA DE LOGIN ATUALIZADA ---
                sucesso, permissao = utils.validar_usuario(nome.strip(), email.strip())
                if sucesso:
                    st.success(f"Acesso liberado! Bem-vindo, {nome.strip()} 👋")
                    st.session_state.update(
                        usuario=nome.strip(), 
                        email_usuario=email.strip(), # Salva o email para uso futuro
                        logado=True, 
                        boas_vindas=True, 
                        tela_principal=False,
                        permissao=permissao  # <<< SALVA A PERMISSÃO
                    )
                    time.sleep(1); st.rerun()
                else:
                    st.error("Acesso negado, tente novamente")
    with col2:
        st.markdown('<div class="login-logo-container">', unsafe_allow_html=True)
        if imagem_principal: st.image(imagem_principal, use_container_width=True) 
        else: st.warning("Não foi possível carregar a imagem do logo.")
        st.markdown('</div>', unsafe_allow_html=True) 

# ----------------- Função: Tela de Cadastro de Usuário (ATUALIZADA) -----------------#
def tela_cadastro_usuario():
    st.subheader("Cadastrar Novo Usuário")
    col1, col2 = st.columns([1, 2]) 
    with col1:
        with st.form("form_cadastro_usuario", clear_on_submit=True): 
            nome = st.text_input("Nome", key="cad_nome")
            email = st.text_input("Email", key="cad_email")
            senha = st.text_input("Senha (opcional)", type="password", key="cad_senha")
            # --- Adicionado campo de Permissão ---
            permissao = st.selectbox("Permissão", options=["Usuario", "Admin"], key="cad_permissao", index=0)
            if st.form_submit_button("Cadastrar"):
                if not nome or not email: st.error("Preencha Nome e Email."); return
                df = utils.carregar_usuarios_db() 
                if not df.empty: df.columns = [col.capitalize() for col in df.columns]
                email_check_list = []
                if not df.empty and "Email" in df.columns: email_check_list = df["Email"].astype(str).str.lower().values
                if email.lower() in email_check_list: st.error("Email já cadastrado!")
                else:
                    # --- Salva com Permissão ---
                    nova_linha = pd.DataFrame([[nome, email, senha, permissao]], columns=["Nome", "Email", "Senha", "Permissao"]) 
                    df_novo = pd.concat([df.rename(columns={'Permissao':'Permissao'}), nova_linha], ignore_index=True) # Garante match de colunas
                    if utils.salvar_usuario_db(df_novo): 
                        st.success("Usuário cadastrado com sucesso!"); st.rerun() 
                    else: st.error("Erro ao salvar usuário no banco de dados.")
    with col2: st.empty()

# ----------------- Função: Tela de Configurações (ATUALIZADA) -----------------
def tela_configuracoes():
    if st.button("⬅️ Voltar para Projetos"):
        st.session_state.tela_configuracoes = False; st.rerun()
    st.title("Administração de Usuários")
    
    # 1. Cadastro de Novo Usuário (agora com permissão)
    tela_cadastro_usuario() 
    st.divider()
    
    # 2. Visualização/Edição de Usuários
    st.subheader("Visualizar e Editar Usuários Cadastrados")
    try:
        df_users_raw = utils.carregar_usuarios_db()
        if not df_users_raw.empty:
            df_users = df_users_raw.rename(columns={'nome': 'Nome', 'email': 'Email', 'senha': 'Senha', 'permissao': 'Permissao'})
            cols_to_show = ['Nome', 'Email', 'Permissao'] # Esconde a senha por padrão
            
            col_config = {
                "Nome": st.column_config.TextColumn("Nome", required=True),
                "Email": st.column_config.TextColumn("Email", required=True),
                "Permissao": st.column_config.SelectboxColumn("Permissão", options=["Usuario", "Admin"], required=True),
                # "Senha": st.column_config.TextColumn("Senha (Opcional)", help="Deixe em branco para não alterar") # Opcional
            }
            
            df_editado = st.data_editor(
                df_users[cols_to_show], column_config=col_config, 
                hide_index=True, num_rows="dynamic", key="editor_usuarios",
                use_container_width=True
            )
            
            if st.button("💾 Salvar Alterações de Usuários", key="btn_salvar_usuarios"):
                # Como a senha não foi editada, precisamos buscá-la antes de salvar
                df_final = df_editado.copy()
                # Adiciona a coluna Senha de volta, pegando do original
                df_final = df_final.merge(df_users[['Email', 'Senha']], on='Email', how='left')
                
                if utils.salvar_usuario_db(df_final):
                    st.success("Usuários salvos com sucesso!"); st.rerun()
                else: st.error("Falha ao salvar usuários.")
        else: st.info("Nenhum usuário cadastrado ainda.")
    except Exception as e: st.error(f"Não foi possível carregar usuários: {e}")
        
# ----------------- Função: Tela de Boas-Vindas (Sem alterações) -----------------
def tela_boas_vindas():
    # ... (seu código de boas_vindas - sem alterações) ...
    mensagens = ["Que seu dia seja produtivo..."] # Ocultado
    msg = random.choice(mensagens)
    st.markdown("""<style> ... (css boas vindas) ... </style>""", unsafe_allow_html=True) # Ocultado
    st.markdown(f"""<div class="welcome-screen-container"><h1>Seja bem-vindo, {st.session_state.usuario} 👋</h1><p>{msg}</p></div>""", unsafe_allow_html=True)
    time.sleep(5); st.session_state.boas_vindas = False; st.session_state.tela_principal = True; st.rerun()

# ----------------- Função: Tela de Cadastro de Projetos (Sem alterações) -----------------
def tela_cadastro_projeto():
    # ... (seu código de cadastro de projeto, com verificação de backlog e prioridade - sem alterações) ...
    # (Ocultado por brevidade, pois já está correto)
    if st.session_state.get("confirmar_duplicado_backlog", False):
        id_existente = st.session_state.get("id_projeto_backlog_existente"); dados_pendentes = st.session_state.get("dados_novo_projeto_pendente", {})
        st.warning(f"⚠️ **Atenção:** Já existe um projeto similar (ID {id_existente}) no backlog. O que deseja fazer?", icon="⚠️")
        col1_conf, col2_conf = st.columns(2)
        with col1_conf:
            if st.button(f"🔄 Atualizar Projeto Existente (ID: {id_existente})", use_container_width=True):
                dados_atualizar = {}; dados_atualizar.update(dados_pendentes); 
                if "Analista" not in dados_atualizar: dados_atualizar["Analista"] = st.session_state.get('usuario', 'N/A')
                if "Status" in dados_atualizar: del dados_atualizar["Status"] 
                if "Agendamento" in dados_atualizar: del dados_atualizar["Agendamento"]
                if "agendamento" in dados_atualizar: del dados_atualizar["agendamento"]
                if utils.atualizar_projeto_db(id_existente, dados_atualizar): st.success(f"Projeto ID {id_existente} atualizado!"); st.session_state.confirmar_duplicado_backlog = False; st.session_state.pop("id_projeto_backlog_existente", None); st.session_state.pop("dados_novo_projeto_pendente", None); st.session_state.tela_cadastro_proj = False; time.sleep(1); st.rerun()
        with col2_conf:
            if st.button("➕ Criar Novo Projeto Mesmo Assim", use_container_width=True, type="primary"):
                dados_adicionar = {"Status": "NÃO INICIADA", "Data de Abertura": date.today(), "Analista": st.session_state.get('usuario', 'N/A'),}
                dados_adicionar.update(dados_pendentes) 
                if utils.adicionar_projeto_db(dados_adicionar):
                    novo_projeto_nome = dados_adicionar.get("Projeto", "Novo Projeto"); st.success(f"Novo projeto '{novo_projeto_nome}' criado!")
                    st.session_state.confirmar_duplicado_backlog = False; st.session_state.pop("id_projeto_backlog_existente", None); st.session_state.pop("dados_novo_projeto_pendente", None); st.session_state.tela_cadastro_proj = False; time.sleep(1); st.rerun()
        st.divider(); 
        if st.button("Cancelar Cadastro"): st.session_state.confirmar_duplicado_backlog = False; st.session_state.pop("id_projeto_backlog_existente", None); st.session_state.pop("dados_novo_projeto_pendente", None); st.rerun()
    else: 
        if st.button("⬅️ Voltar para Projetos"): st.session_state.tela_cadastro_proj = False; st.session_state.pop("confirmar_duplicado_backlog", None); st.session_state.pop("id_projeto_backlog_existente", None); st.session_state.pop("dados_novo_projeto_pendente", None); st.rerun()
        st.subheader("Cadastrar Novo Projeto")
        perguntas_customizadas = utils.carregar_config_db("perguntas") 
        agencias_cfg = utils.carregar_config_db("agencias"); agencia_options = ["N/A"] + (agencias_cfg.iloc[:, 0].tolist() if not agencias_cfg.empty and len(agencias_cfg.columns) > 0 else [])
        tecnicos_cfg = utils.carregar_config_db("tecnicos"); tecnico_options = ["N/A"] + (tecnicos_cfg.iloc[:, 0].tolist() if not tecnicos_cfg.empty and len(tecnicos_cfg.columns) > 0 else [])
        projetos_cfg = utils.carregar_config_db("projetos_nomes"); projeto_options = ["N/A"] + (projetos_cfg.iloc[:, 0].tolist() if not projetos_cfg.empty and len(projetos_cfg.columns) > 0 else [])
        if perguntas_customizadas.empty or 'Pergunta' not in perguntas_customizadas.columns: st.info("🚨 Nenhuma pergunta customizada configurada."); return
        with st.form("form_cadastro_projeto"):
            respostas_customizadas = {}
            prioridade_selecionada = st.selectbox("Prioridade", options=["Baixa", "Média", "Alta"], index=1, key="nova_prioridade_cadastro")
            links_referencia = st.text_area("Links de Referência", placeholder="Cole links aqui, um por linha...", height=100)
            st.divider() 
            for index, row in perguntas_customizadas.iterrows():
                pergunta = row['Pergunta']; tipo = row.get('Tipo (texto, numero, data)', 'texto'); key = utils.clean_key(pergunta)
                pergunta_norm = pergunta.lower().strip() 
                if pergunta_norm == 'agência': respostas_customizadas[pergunta] = st.selectbox(pergunta, options=agencia_options, key=f"custom_{key}", help="Selecione a agência.")
                elif pergunta_norm == 'técnico': respostas_customizadas[pergunta] = st.selectbox(pergunta, options=tecnico_options, key=f"custom_{key}", help="Selecione o técnico.")
                elif pergunta_norm == 'projeto' or pergunta_norm == 'nome do projeto': respostas_customizadas[pergunta] = st.selectbox(pergunta, options=projeto_options, key=f"custom_{key}", help="Selecione o projeto.")
                elif tipo == 'data': respostas_customizadas[pergunta] = st.date_input(pergunta, value=None, key=f"custom_{key}", format="DD/MM/YYYY")
                elif tipo == 'numero': respostas_customizadas[pergunta] = st.number_input(pergunta, key=f"custom_{key}", step=1)
                else: respostas_customizadas[pergunta] = st.text_input(pergunta, key=f"custom_{key}")
            btn_cadastrar = st.form_submit_button("Cadastrar Projeto")
        if btn_cadastrar:
            projeto_nome_key = next((p for p in respostas_customizadas if p.lower().strip() in ['nome do projeto', 'projeto']), None)
            agencia_key = next((p for p in respostas_customizadas if p.lower().strip() == 'agência'), None)
            novo_projeto_nome = respostas_customizadas.get(projeto_nome_key) if projeto_nome_key else "N/A"
            nova_agencia = respostas_customizadas.get(agencia_key) if agencia_key else "N/A"
            if (not projeto_nome_key or novo_projeto_nome == "N/A") or (not agencia_key or nova_agencia == "N/A"): st.error("ERRO: 'Projeto' e 'Agência' são campos obrigatórios."); st.stop() 
            respostas_customizadas["Prioridade"] = prioridade_selecionada; respostas_customizadas["Links de Referência"] = links_referencia 
            df_backlog = utils.carregar_projetos_sem_agendamento_db(st.session_state.get("usuario"), st.session_state.get("permissao")) # Passa permissão
            projeto_existente = pd.DataFrame() 
            if not df_backlog.empty and "Agência" in df_backlog.columns and "Projeto" in df_backlog.columns:
                 projeto_existente = df_backlog[(df_backlog["Agência"].astype(str).str.lower() == nova_agencia.lower()) & (df_backlog["Projeto"].astype(str).str.lower() == novo_projeto_nome.lower())]
            if not projeto_existente.empty:
                id_existente = projeto_existente.iloc[0]['ID']; st.session_state.dados_novo_projeto_pendente = respostas_customizadas
                st.session_state.id_projeto_backlog_existente = id_existente; st.session_state.confirmar_duplicado_backlog = True
            else: 
                dados_adicionar = {"Status": "NÃO INICIADA", "Data de Abertura": date.today(), "Analista": st.session_state.get('usuario', 'N/A'),}
                dados_adicionar.update(respostas_customizadas) 
                if utils.adicionar_projeto_db(dados_adicionar): st.success(f"Projeto '{novo_projeto_nome}' cadastrado!"); st.session_state["tela_cadastro_proj"] = False; time.sleep(1); st.rerun() 

# ----------------- Função: Tela de Projetos (ATUALIZADA) -----------------
def tela_projetos():
    st.markdown("<div class='section-title-center'>PROJETOS</div>", unsafe_allow_html=True)
    
    # --- ATUALIZADO: Passa permissão para carregar dados ---
    usuario_nome = st.session_state.get("usuario", "N/A")
    usuario_permissao = st.session_state.get("permissao", "Usuario")
    df = utils.carregar_projetos_db(usuario_nome, usuario_permissao)
    # --- FIM ---
    
    df_sla = utils.carregar_config_db("sla") 
    df_etapas_config = utils.carregar_config_db("etapas_evolucao") 
    
    if df.empty: 
        if usuario_permissao == 'Usuario': st.info(f"Nenhum projeto encontrado atribuído a você ({usuario_nome})."); return
        else: st.info("Nenhum projeto cadastrado ainda."); return
        
    df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce') 
    df['Agendamento_str'] = df['Agendamento'].dt.strftime("%d/%m/%y").fillna('N/A')
    
    # (Filtros e Ordenação)
    st.markdown("#### 🔍 Busca e Ordenação")
    col_busca, col_ordem = st.columns([3, 2])
    with col_busca: termo_busca = st.text_input("Buscar", key="termo_busca", placeholder="Digite um termo para buscar...", label_visibility="collapsed")
    with col_ordem:
        opcoes_ordenacao = ["Data Agendamento (Mais Recente)", "Data Agendamento (Mais Antigo)", "Prioridade (Alta > Baixa)", "SLA Restante (Menor > Maior)"]
        ordem_selecionada = st.selectbox("Ordenar por:", options=opcoes_ordenacao, key="ordem_projetos", label_visibility="collapsed")
    st.markdown("#### 🎛️ Filtros")
    filtros = {} 
    col1, col2, col3, col4 = st.columns(4); campos_linha_1 = {"Status": col1, "Analista": col2, "Agência": col3, "Gestor": col4}
    for campo, col in campos_linha_1.items():
        with col:
            if campo in df.columns: unique_values = df[campo].dropna().astype(str).unique(); opcoes = ["Todos"] + sorted(unique_values.tolist()); filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")
            else: st.empty()
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        campo = "Projeto"; 
        if campo in df.columns: unique_values = df[campo].dropna().astype(str).unique(); opcoes = ["Todos"] + sorted(unique_values.tolist()); filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")
        else: st.empty()
    with col6:
        campo = "Técnico"; 
        if campo in df.columns: unique_values = df[campo].dropna().astype(str).unique(); opcoes = ["Todos"] + sorted(unique_values.tolist()); filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")
        else: st.empty()
    with col7: data_inicio = st.date_input("Agendamento (de)", value=None, key="data_inicio_filtro", format="DD/MM/YYYY")
    with col8: data_fim = st.date_input("Agendamento (até)", value=None, key="data_fim_filtro", format="DD/MM/YYYY")
    df_filtrado = df.copy()
    for campo, valor in filtros.items():
        if valor != "Todos" and campo in df_filtrado.columns: df_filtrado = df_filtrado[df_filtrado[campo].astype(str) == str(valor)]
    if data_inicio: df_filtrado = df_filtrado[(df_filtrado['Agendamento'].notna()) & (df_filtrado['Agendamento'] >= pd.to_datetime(data_inicio))]
    if data_fim: df_filtrado = df_filtrado[(df_filtrado['Agendamento'].notna()) & (df_filtrado['Agendamento'] <= pd.to_datetime(data_fim).replace(hour=23, minute=59, second=59))]
    if termo_busca: termo = termo_busca.lower().strip(); mask_busca = df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(termo, na=False, regex=False).any(), axis=1); df_filtrado = df_filtrado[mask_busca]
    st.divider()
    st.markdown("#### 📈 Indicadores da Visão Atual")
    hoje = date.today()
    df_nao_finalizados = df_filtrado[~df_filtrado['Status'].str.contains("Finalizada|Cancelada", na=False, case=False)].copy() 
    df_agendados = df_nao_finalizados[df_nao_finalizados['Agendamento'].notna()]
    kpi_vencidos = df_agendados[df_agendados['Agendamento'].dt.date < hoje]; kpi_hoje = df_agendados[df_agendados['Agendamento'].dt.date == hoje]
    kpi_em_andamento = df_filtrado[df_filtrado['Status'].str.lower().isin(['em andamento', 'pausado', 'pendencia'])]; kpi_backlog = df_nao_finalizados[df_nao_finalizados['Agendamento'].isna()]
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    col_kpi1.metric("🚨 Vencidos", len(kpi_vencidos)); col_kpi2.metric("❗ Para Hoje", len(kpi_hoje)); col_kpi3.metric("⚙️ Em Andamento/Pendentes", len(kpi_em_andamento)); col_kpi4.metric("🗃️ Backlog (Sem Data)", len(kpi_backlog))
    if not df_filtrado.empty: df_filtrado['proxima_etapa_calc'] = df_filtrado.apply(get_next_stage, args=(df_etapas_config,), axis=1)
    if not df_filtrado.empty:
        stage_counts = df_filtrado['proxima_etapa_calc'].value_counts()
        stage_counts = stage_counts.drop(labels=["Ignorado", "Sem Etapas", "Concluído"], errors='ignore')
        if not stage_counts.empty:
            st.markdown("#### 📋 Resumo das Próximas Etapas"); top_stages = stage_counts.head(4); cols_kpi_stages = st.columns(4)
            for i, (stage, count) in enumerate(top_stages.items()): cols_kpi_stages[i].metric(label=f"{stage}", value=count)
    st.divider()
    if ordem_selecionada == "Data Agendamento (Mais Recente)": df_filtrado = df_filtrado.sort_values(by="Agendamento", ascending=False, na_position='last')
    elif ordem_selecionada == "Data Agendamento (Mais Antigo)": df_filtrado = df_filtrado.sort_values(by="Agendamento", ascending=True, na_position='last')
    elif ordem_selecionada == "Prioridade (Alta > Baixa)":
        priority_map = {"Alta": 1, "Média": 2, "Baixa": 3}; df_filtrado['prioridade_num'] = df_filtrado['Prioridade'].map(priority_map).fillna(2)
        df_filtrado = df_filtrado.sort_values(by="prioridade_num", ascending=True); df_filtrado = df_filtrado.drop(columns=['prioridade_num']) 
    elif ordem_selecionada == "SLA Restante (Menor > Maior)":
        def calculate_remaining_days(row):
            agendamento = row['Agendamento']; status = row['Status']; finalizacao = row.get('Data de Finalização')
            if pd.isna(agendamento) or pd.notna(finalizacao) or ('finalizad' in str(status).lower()) or ('cancelad' in str(status).lower()): return float('inf') 
            prazo_dias = 30 
            try: 
                 rule = df_sla[df_sla["Nome do Projeto"].astype(str).str.upper() == str(row.get("Projeto","")).upper()]
                 if not rule.empty: prazo_dias = int(rule.iloc[0]["Prazo (dias)"])
            except: pass
            dias_corridos = (hoje - agendamento.date()).days; return prazo_dias - dias_corridos
        df_filtrado['sla_dias_restantes'] = df_filtrado.apply(calculate_remaining_days, axis=1)
        df_filtrado = df_filtrado.sort_values(by="sla_dias_restantes", ascending=True)
    col_info_export, col_export_btn = st.columns([4, 1.2]); total_items = len(df_filtrado)
    with col_info_export: st.info(f"Projetos encontrados (filtrados): {total_items}")
    with col_export_btn:
        excel_bytes = utils.dataframe_to_excel_bytes(df_filtrado.drop(columns=['sla_dias_restantes', 'proxima_etapa_calc'], errors='ignore'))
        st.download_button(label="📥 Exportar para Excel", data=excel_bytes, file_name=f"projetos_{date.today().strftime('%Y-%m-%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    st.divider()
    items_per_page = 10; 
    if 'page_number' not in st.session_state: st.session_state.page_number = 0
    total_pages = (total_items // items_per_page) + (1 if total_items % items_per_page > 0 else 0); 
    if total_pages == 0: total_pages = 1
    current_max_page = total_pages - 1
    if st.session_state.page_number > current_max_page: st.session_state.page_number = 0
    start_idx = st.session_state.page_number * items_per_page; end_idx = start_idx + items_per_page
    df_paginado = df_filtrado.iloc[start_idx:end_idx] 
    agencias_cfg = utils.carregar_config_db("agencias"); agencia_options = ["N/A"] + (agencias_cfg.iloc[:, 0].tolist() if not agencias_cfg.empty and len(agencias_cfg.columns) > 0 else [])
    tecnicos_cfg = utils.carregar_config_db("tecnicos"); tecnico_options = ["N/A"] + (tecnicos_cfg.iloc[:, 0].tolist() if not tecnicos_cfg.empty and len(tecnicos_cfg.columns) > 0 else [])
    status_options_df = utils.carregar_config_db("status"); status_options = status_options_df.iloc[:, 0].tolist() if not status_options_df.empty and len(status_options_df.columns) > 0 else []
    projetos_cfg = utils.carregar_config_db("projetos_nomes"); projeto_options = ["N/A"] + (projetos_cfg.iloc[:, 0].tolist() if not projetos_cfg.empty and len(projetos_cfg.columns) > 0 else [])
    limite_lembrete = hoje + timedelta(days=3)
    for _, row in df_paginado.iterrows():
        project_id = row['ID']; status_raw = row.get('Status', 'N/A'); status_text = html.escape(str(status_raw))
        analista_text = html.escape(str(row.get('Analista', 'N/A'))); agencia_text = html.escape(str(row.get("Agência", "N/A")))
        projeto_nome_text = html.escape(str(row.get("Projeto", "N/A"))); agendamento_str = row.get('Agendamento_str', 'N/A') 
        gestor_text = html.escape(str(row.get('Gestor', 'N/A'))); gestor_color = utils.get_color_for_name(gestor_text) 
        lembrete_ativo = False; icone_lembrete = ""; cor_lembrete = ""; texto_lembrete_html = ""
        agendamento_date_obj = row.get('Agendamento').date() if pd.notna(row.get('Agendamento')) else None
        sla_text, sla_color_real = utils.calcular_sla(row, df_sla) 
        if not ('finalizad' in status_raw.lower() or 'cancelad' in status_raw.lower()):
            if agendamento_date_obj == hoje: icone_lembrete = "❗"; cor_lembrete = "red"; texto_lembrete_html = f"<p style='color:{cor_lembrete}; font-weight:bold; margin-top: -5px;'>ATENÇÃO - DEMANDA PARA HOJE</p>"
            elif agendamento_date_obj and hoje < agendamento_date_obj <= limite_lembrete: icone_lembrete = "⚠️"; cor_lembrete = "orange"; texto_lembrete_html = f"<p style='color:{cor_lembrete}; font-weight:bold; margin-top: -5px;'>Lembrete: Próximo!</p>"
        proxima_etapa = row.get('proxima_etapa_calc', 'Sem Etapas'); 
        if proxima_etapa == "Ignorado" or proxima_etapa == "Sem Etapas": proxima_etapa_texto = "Nenhuma etapa configurada"
        elif proxima_etapa == "Concluído": proxima_etapa_texto = "✔️ Todas concluídas"
        else: proxima_etapa_texto = proxima_etapa
        st.markdown("<div class='project-card'>", unsafe_allow_html=True)
        col_info_card, col_analista_card, col_agencia_card, col_status_card = st.columns([2.5, 2, 1.5, 2.0]) 
        with col_info_card:
            st.markdown(f"<h6>{icone_lembrete} 📅 {agendamento_str}</h6>", unsafe_allow_html=True) 
            st.markdown(f"<h5 style='margin:2px 0'>{projeto_nome_text.upper()}</h5>", unsafe_allow_html=True)
        with col_analista_card:
            st.markdown(f"**Analista:** {analista_text}")
            st.markdown(f"<p style='color:{sla_color_real}; font-weight:bold; margin-top: 5px;'>{sla_text}</p>", unsafe_allow_html=True) 
            st.markdown(texto_lembrete_html, unsafe_allow_html=True) 
        with col_agencia_card:
            st.markdown(f"**Agência:** {agencia_text}") 
            st.markdown(f"<span style='color:{gestor_color}; font-weight: bold;'>Gestor: {gestor_text}</span>", unsafe_allow_html=True)
        with col_status_card:
            status_color_name = utils.get_status_color(str(status_raw)) 
            st.markdown(f"""<div style="height:100%; display:flex; flex-direction: column; align-items: flex-end; justify-content: center;"><span style="background-color:{status_color_name}; color:black; padding:8px 15px; border-radius:5px; font-weight:bold; font-size:0.9em; margin-bottom: 5px;">{status_text}</span><span style="font-size: 0.95em; color: var(--primary-dark); font-weight: bold; text-align: right;">{proxima_etapa_texto}</span></div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander(f"Ver/Editar Detalhes - ID: {project_id}"):
            with st.form(f"form_edicao_card_{project_id}"):
                st.markdown("#### Evolução da Demanda")
                etapas_do_projeto = df_etapas_config[df_etapas_config["Nome do Projeto"] == row.get("Projeto", "")] if "Nome do Projeto" in df_etapas_config.columns else pd.DataFrame()
                etapas_concluidas_str = row.get("Etapas Concluidas", ""); etapas_concluidas_lista = []
                if pd.notna(etapas_concluidas_str) and isinstance(etapas_concluidas_str, str) and etapas_concluidas_str.strip(): etapas_concluidas_lista = [e.strip() for e in etapas_concluidas_str.split(',') if e.strip()]
                novas_etapas_marcadas = [] 
                if not etapas_do_projeto.empty and "Etapa" in etapas_do_projeto.columns:
                    todas_etapas_possiveis = etapas_do_projeto["Etapa"].astype(str).str.strip().tolist(); total_etapas = len(todas_etapas_possiveis) 
                    num_etapas_concluidas = len(etapas_concluidas_lista); progresso = num_etapas_concluidas / total_etapas if total_etapas > 0 else 0
                    st.progress(progresso); st.caption(f"{num_etapas_concluidas} de {total_etapas} etapas concluídas ({progresso:.0%})")
                    for etapa in todas_etapas_possiveis:
                        marcado = st.checkbox(etapa, value=(etapa in etapas_concluidas_lista), key=f"chk_{project_id}_{utils.clean_key(etapa)}")
                        if marcado: novas_etapas_marcadas.append(etapa)
                else: st.caption("Nenhuma etapa de evolução configurada."); todas_etapas_possiveis = []; total_etapas = 0
                st.markdown("#### Informações e Prazos")
                c1,c2,c3,c4 = st.columns(4)
                with c1: status_selecionaveis = status_options[:]; status_atual = row.get('Status'); idx_status = status_selecionaveis.index(status_atual) if status_atual in status_selecionaveis else 0; novo_status_selecionado = st.selectbox("Status", status_selecionaveis, index=idx_status, key=f"status_{project_id}")
                with c2: abertura_default = _to_date_safe(row.get('Data de Abertura')); nova_data_abertura = st.date_input("Data Abertura", value=abertura_default, key=f"abertura_{project_id}", format="DD/MM/YYYY")
                with c3: agendamento_default = _to_date_safe(row.get('Agendamento')); novo_agendamento = st.date_input("Agendamento", value=agendamento_default, key=f"agend_{project_id}", format="DD/MM/YYYY")
                with c4: finalizacao_default = _to_date_safe(row.get('Data de Finalização')); nova_data_finalizacao = st.date_input("Data Finalização", value=finalizacao_default, key=f"final_{project_id}", format="DD/MM/YYYY")
                st.markdown("#### Detalhes do Projeto")
                c5,c6,c7, c_prio = st.columns(4) 
                with c5: projeto_val = row.get('Projeto', ''); idx_proj = projeto_options.index(projeto_val) if projeto_val in projeto_options else 0; novo_projeto = st.selectbox("Projeto", options=projeto_options, index=idx_proj, key=f"proj_{project_id}")
                with c6: novo_analista = st.text_input("Analista", value=row.get('Analista', ''), key=f"analista_{project_id}")
                with c7: novo_gestor = st.text_input("Gestor", value=row.get('Gestor', ''), key=f"gestor_{project_id}")
                with c_prio:
                     prioridade_atual = row.get('Prioridade', 'Média'); prioridades = ["Baixa", "Média", "Alta"]
                     idx_prio = prioridades.index(prioridade_atual) if prioridade_atual in prioridades else 1
                     nova_prioridade = st.selectbox("Prioridade", options=prioridades, index=idx_prio, key=f"prio_{project_id}")
                c8,c9 = st.columns(2)
                with c8: agencia_val = row.get('Agência', ''); idx_ag = agencia_options.index(agencia_val) if agencia_val in agencia_options else 0; nova_agencia = st.selectbox("Agência", agencia_options, index=idx_ag, key=f"agencia_{project_id}")
                with c9: tecnico_val = row.get('Técnico', ''); idx_tec = tecnico_options.index(tecnico_val) if tecnico_val in tecnico_options else 0; novo_tecnico = st.selectbox("Técnico", tecnico_options, index=idx_tec, key=f"tecnico_{project_id}")
                nova_demanda = st.text_input("Demanda", value=row.get('Demanda', ''), key=f"demanda_{project_id}")
                nova_descricao = st.text_area("Descrição", value=row.get('Descrição', ''), key=f"desc_{project_id}")
                nova_observacao = st.text_area("Observação / Pendências", value=row.get('Observação', ''), key=f"obs_{project_id}")
                links_salvos = row.get('Links de Referência', '')
                if links_salvos and links_salvos.strip():
                    st.markdown("---"); st.markdown("📎 **Links Salvos** (clicáveis)")
                    links_lista = links_salvos.strip().split('\n')
                    for link in links_lista:
                        link_limpo = link.strip()
                        if link_limpo.startswith("http"):
                            display_text = link_limpo; 
                            if len(display_text) > 70: display_text = display_text[:67] + "..."
                            st.markdown(f"- [{display_text}]({link_limpo})")
                        elif link_limpo: st.markdown(f"- {link_limpo} (Texto salvo)")
                    st.markdown("---")
                nova_links = st.text_area("Editar Links de Referência", value=links_salvos, key=f"links_{project_id}", placeholder="Cole links aqui, um por linha...")
                log_agendamento_existente = row.get("Log Agendamento", "") if pd.notna(row.get("Log Agendamento")) else ""; st.text_area("Histórico de Alterações", value=log_agendamento_existente, height=100, disabled=True, key=f"log_{project_id}")
                _, col_save, col_delete = st.columns([3, 1.5, 1]) 
                with col_save: btn_salvar_card = st.form_submit_button("💾 Salvar", use_container_width=True)
                with col_delete: btn_excluir_card = st.form_submit_button("🗑️ Excluir", use_container_width=True, type="primary")
                if btn_excluir_card:
                    if utils.excluir_projeto_db(project_id): st.success(f"Projeto ID {project_id} excluído."); st.rerun()
                if btn_salvar_card:
                    status_final = novo_status_selecionado 
                    if novo_projeto == "N/A": st.error("ERRO: 'Projeto' é obrigatório.", icon="🚨"); st.stop()
                    if nova_agencia == "N/A": st.error("ERRO: 'Agência' é obrigatória.", icon="🚨"); st.stop()
                    if 'finalizad' in status_final.lower():
                        if total_etapas > 0 and len(novas_etapas_marcadas) < total_etapas: st.error(f"ERRO: Para 'Finalizado', todas as {total_etapas} etapas devem estar selecionadas.", icon="🚨"); st.stop() 
                        if not _to_date_safe(nova_data_finalizacao): st.error("ERRO: Se 'Finalizada', Data de Finalização é obrigatória.", icon="🚨"); st.stop() 
                    status_atual_normalizado = str(row.get('Status', '')).strip().upper(); status_final_normalizado = str(status_final).strip().upper()
                    if (status_atual_normalizado == 'NÃO INICIADA') and (len(novas_etapas_marcadas) > 0) and (status_final_normalizado == 'NÃO INICIADA'):
                        status_final = 'EM ANDAMENTO'; st.info("Status alterado para 'EM ANDAMENTO'.")
                    nova_data_abertura_date = _to_date_safe(nova_data_abertura); nova_data_finalizacao_date = _to_date_safe(nova_data_finalizacao); novo_agendamento_date = _to_date_safe(novo_agendamento)
                    updates = {"Status": status_final, "Agendamento": novo_agendamento_date, "Analista": novo_analista,"Agência": nova_agencia if nova_agencia != "N/A" else None, "Gestor": novo_gestor, "Projeto": novo_projeto, "Técnico": novo_tecnico if novo_tecnico != "N/A" else None, "Demanda": nova_demanda, "Descrição": nova_descricao, "Observação": nova_observacao, "Data de Abertura": nova_data_abertura_date, "Data de Finalização": nova_data_finalizacao_date, "Etapas Concluidas": ",".join(novas_etapas_marcadas) if novas_etapas_marcadas else None, "Prioridade": nova_prioridade, "Links de Referência": nova_links }
                    if utils.atualizar_projeto_db(project_id, updates): st.success(f"Projeto '{novo_projeto}' (ID: {project_id}) atualizado."); st.rerun()
    # (Paginação)
    st.divider()
    if total_pages > 1:
        col_info_pag, col_prev_pag, col_next_pag = st.columns([5, 1.5, 1.5]) 
        with col_info_pag: st.markdown(f"<div style='text-align: left; margin-top: 10px;'>Página <b>{st.session_state.page_number + 1}</b> de <b>{total_pages}</b></div>", unsafe_allow_html=True)
        with col_prev_pag:
            if st.button("⬅️ Anterior", use_container_width=True, disabled=(st.session_state.page_number == 0)): st.session_state.page_number -= 1; st.rerun()
        with col_next_pag:
            if st.button("Próxima ➡️", use_container_width=True, disabled=(st.session_state.page_number >= total_pages - 1)): st.session_state.page_number += 1; st.rerun()

# ----------------- Função: Tela Kanban (ATUALIZADA) -----------------
def tela_kanban():
    st.markdown("<div class='section-title-center'>VISÃO KANBAN</div>", unsafe_allow_html=True)

    # --- ATUALIZADO: Passa permissão para carregar dados ---
    usuario_nome = st.session_state.get("usuario", "N/A")
    usuario_permissao = st.session_state.get("permissao", "Usuario")
    df = utils.carregar_projetos_db(usuario_nome, usuario_permissao)
    # --- FIM ---

    df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce') 
    df_sla = utils.carregar_config_db("sla") 
    df_etapas_config = utils.carregar_config_db("etapas_evolucao") 
    agencias_cfg = utils.carregar_config_db("agencias"); agencia_options = ["N/A"] + (agencias_cfg.iloc[:, 0].tolist() if not agencias_cfg.empty and len(agencias_cfg.columns) > 0 else [])
    tecnicos_cfg = utils.carregar_config_db("tecnicos"); tecnico_options = ["N/A"] + (tecnicos_cfg.iloc[:, 0].tolist() if not tecnicos_cfg.empty and len(tecnicos_cfg.columns) > 0 else [])
    status_options_df = utils.carregar_config_db("status"); status_options = status_options_df.iloc[:, 0].tolist() if not status_options_df.empty and len(status_options_df.columns) > 0 else []
    projetos_cfg = utils.carregar_config_db("projetos_nomes"); projeto_options = ["N/A"] + (projetos_cfg.iloc[:, 0].tolist() if not projetos_cfg.empty and len(projetos_cfg.columns) > 0 else [])
    hoje = date.today(); limite_lembrete = hoje + timedelta(days=3)

    # (Filtros e Ordenação)
    st.markdown("#### 🔍 Busca e Ordenação")
    col_busca, col_ordem = st.columns([3, 2])
    with col_busca: termo_busca = st.text_input("Buscar", key="kanban_termo_busca", placeholder="Digite um termo para buscar...", label_visibility="collapsed")
    with col_ordem:
        opcoes_ordenacao = ["Prioridade (Alta > Baixa)", "Data Agendamento (Mais Antigo)", "Data Agendamento (Mais Recente)"]
        ordem_selecionada = st.selectbox("Ordenar por:", options=opcoes_ordenacao, key="ordem_kanban", label_visibility="collapsed")
    st.markdown("#### 🎛️ Filtros")
    filtros = {} 
    col1, col2, col3, col4 = st.columns(4); campos_linha_1 = {"Status": col1, "Analista": col2, "Agência": col3, "Gestor": col4}
    for campo, col in campos_linha_1.items():
        with col:
            if campo in df.columns: unique_values = df[campo].dropna().astype(str).unique(); opcoes = ["Todos"] + sorted(unique_values.tolist()); filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"kanban_filtro_{utils.clean_key(campo)}")
            else: st.empty()
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        campo = "Projeto"; 
        if campo in df.columns: unique_values = df[campo].dropna().astype(str).unique(); opcoes = ["Todos"] + sorted(unique_values.tolist()); filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"kanban_filtro_{utils.clean_key(campo)}")
        else: st.empty()
    with col6:
        campo = "Técnico"; 
        if campo in df.columns: unique_values = df[campo].dropna().astype(str).unique(); opcoes = ["Todos"] + sorted(unique_values.tolist()); filtros[campo] = st.selectbox(f"{campo}", opcoes, key=f"kanban_filtro_{utils.clean_key(campo)}")
        else: st.empty()
    with col7: data_inicio = st.date_input("Agendamento (de)", value=None, key="kanban_data_inicio_filtro", format="DD/MM/YYYY")
    with col8: data_fim = st.date_input("Agendamento (até)", value=None, key="kanban_data_fim_filtro", format="DD/MM/YYYY")
    
    # (Lógica de Filtros)
    df_filtrado = df.copy()
    for campo, valor in filtros.items():
        if valor != "Todos" and campo in df_filtrado.columns: df_filtrado = df_filtrado[df_filtrado[campo].astype(str) == str(valor)]
    if data_inicio: df_filtrado = df_filtrado[(df_filtrado['Agendamento'].notna()) & (df_filtrado['Agendamento'] >= pd.to_datetime(data_inicio))]
    if data_fim: df_filtrado = df_filtrado[(df_filtrado['Agendamento'].notna()) & (df_filtrado['Agendamento'] <= pd.to_datetime(data_fim).replace(hour=23, minute=59, second=59))]
    if termo_busca: termo = termo_busca.lower().strip(); mask_busca = df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(termo, na=False, regex=False).any(), axis=1); df_filtrado = df_filtrado[mask_busca]
    st.divider()
    
    # (KPIs)
    st.markdown("#### 📈 Indicadores da Visão Atual")
    df_nao_finalizados = df_filtrado[~df_filtrado['Status'].str.contains("Finalizada|Cancelada", na=False, case=False)].copy() 
    df_agendados = df_nao_finalizados[df_nao_finalizados['Agendamento'].notna()]
    kpi_vencidos = df_agendados[df_agendados['Agendamento'].dt.date < hoje]; kpi_hoje = df_agendados[df_agendados['Agendamento'].dt.date == hoje]
    kpi_em_andamento = df_filtrado[df_filtrado['Status'].str.lower().isin(['em andamento', 'pausado', 'pendencia'])]; kpi_backlog = df_nao_finalizados[df_nao_finalizados['Agendamento'].isna()]
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    col_kpi1.metric("🚨 Vencidos", len(kpi_vencidos)); col_kpi2.metric("❗ Para Hoje", len(kpi_hoje)); col_kpi3.metric("⚙️ Em Andamento/Pendentes", len(kpi_em_andamento)); col_kpi4.metric("🗃️ Backlog (Sem Data)", len(kpi_backlog))
    if not df_filtrado.empty: df_filtrado['proxima_etapa_calc'] = df_filtrado.apply(get_next_stage, args=(df_etapas_config,), axis=1)
    if not df_filtrado.empty:
        df_nao_finalizados = df_filtrado[df_filtrado.index.isin(df_nao_finalizados.index)] 
        stage_counts = df_nao_finalizados['proxima_etapa_calc'].value_counts()
        stage_counts = stage_counts.drop(labels=["Ignorado", "Sem Etapas", "Concluído"], errors='ignore')
        if not stage_counts.empty:
            st.markdown("#### 📋 Resumo das Próximas Etapas"); top_stages = stage_counts.head(4); cols_kpi_stages = st.columns(4)
            for i, (stage, count) in enumerate(top_stages.items()): cols_kpi_stages[i].metric(label=f"{stage}", value=count)
    st.divider()
    
    # (Lógica de Colunas Kanban e Ordenação)
    colunas_kanban = ["BACKLOG", "PENDÊNCIA", "NÃO INICIADA", "EM ANDAMENTO"] 
    f_backlog = (df_filtrado['Agendamento'].isna()) & (~df_filtrado['Status'].str.lower().isin(['finalizado', 'cancelado', 'finalizada']))
    f_pendencia = (df_filtrado['Agendamento'].notna()) & (df_filtrado['Status'].str.lower().str.contains('pendencia'))
    f_nao_iniciada = (df_filtrado['Agendamento'].notna()) & (df_filtrado['Status'].str.lower().str.contains('não iniciad')) & (~f_pendencia)
    f_em_andamento = (df_filtrado['Agendamento'].notna()) & (df_filtrado['Status'].str.lower().isin(['em andamento', 'pausado'])) & (~f_pendencia) & (~f_nao_iniciada)
    def sort_df(df_col, ordem):
        if ordem == "Data Agendamento (Mais Recente)": return df_col.sort_values(by="Agendamento", ascending=False, na_position='last')
        if ordem == "Data Agendamento (Mais Antigo)": return df_col.sort_values(by="Agendamento", ascending=True, na_position='last')
        if ordem == "Prioridade (Alta > Baixa)":
            priority_map = {"Alta": 1, "Média": 2, "Baixa": 3}; df_col['prioridade_num'] = df_col['Prioridade'].map(priority_map).fillna(2)
            return df_col.sort_values(by="prioridade_num", ascending=True).drop(columns=['prioridade_num'])
        return df_col 
    dfs_colunas = {"BACKLOG": sort_df(df_filtrado[f_backlog], ordem_selecionada), "PENDÊNCIA": sort_df(df_filtrado[f_pendencia], ordem_selecionada), "NÃO INICIADA": sort_df(df_filtrado[f_nao_iniciada], ordem_selecionada), "EM ANDAMENTO": sort_df(df_filtrado[f_em_andamento], ordem_selecionada) }
    cols_streamlit = st.columns(len(colunas_kanban)); pagination_details = {} 
    
    # --- LOOP 1: Desenhar os CARDS ---
    for i, col_nome in enumerate(colunas_kanban):
        with cols_streamlit[i]:
            df_col = dfs_colunas[col_nome]; count = len(df_col)
            st.markdown(f"<div class='kanban-column-header'>{col_nome.upper()} ({count})</div>", unsafe_allow_html=True)
            itens_por_pagina = 15; total_itens = len(df_col); total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina if total_itens > 0 else 1
            key_pagina = f"pagina_kanban_{col_nome}"
            if key_pagina not in st.session_state: st.session_state[key_pagina] = 1
            if st.session_state[key_pagina] > total_paginas: st.session_state[key_pagina] = total_paginas
            if st.session_state[key_pagina] < 1: st.session_state[key_pagina] = 1
            inicio = (st.session_state[key_pagina] - 1) * itens_por_pagina; fim = inicio + itens_por_pagina
            df_col_paginado = df_col.iloc[inicio:fim] if not df_col.empty else pd.DataFrame()
            pagination_details[col_nome] = {"key": key_pagina, "total_itens": total_itens, "total_paginas": total_paginas, "inicio": inicio, "fim": fim}
            if df_col_paginado.empty: st.markdown("<div style='text-align:center; color:gray; font-size:0.85rem; padding: 10px;'>Nenhum projeto aqui</div>", unsafe_allow_html=True)
            
            for _, row in df_col_paginado.iterrows():
                project_id = row['ID']
                status_raw = row.get('Status', 'N/A'); projeto_nome_text = html.escape(str(row.get("Projeto", "N/A"))) 
                agencia_text = html.escape(str(row.get("Agência", "N/A"))); analista_text = html.escape(str(row.get('Analista', 'N/A')))
                sla_text, sla_color_real = utils.calcular_sla(row, df_sla); texto_lembrete_html = ""; icone_lembrete = ""
                agendamento_date_obj = row.get('Agendamento').date() if pd.notna(row.get('Agendamento')) else None 
                if not ('finalizad' in status_raw.lower() or 'cancelad' in status_raw.lower()):
                    if agendamento_date_obj == hoje: icone_lembrete = "❗"; cor_lembrete = "red"; texto_lembrete_html = f"<small style='color:{cor_lembrete}; font-weight:bold;'>PARA HOJE</small>"
                    elif agendamento_date_obj and hoje < agendamento_date_obj <= limite_lembrete: icone_lembrete = "⚠️"; cor_lembrete = "orange"; texto_lembrete_html = f"<small style='color:{cor_lembrete}; font-weight:bold;'>Próximo</small>"
                
                st.markdown(f"<div class='kanban-card'>", unsafe_allow_html=True)
                st.markdown(f"<strong>{icone_lembrete} {projeto_nome_text.upper()} (ID: {project_id})</strong>", unsafe_allow_html=True)
                st.markdown(f"<small>Agência: {agencia_text}</small>", unsafe_allow_html=True)
                st.markdown(f"<small>Analista: {analista_text}</small>", unsafe_allow_html=True)
                st.markdown(f"<small style='color:{sla_color_real}; font-weight:bold;'>{sla_text}</small>", unsafe_allow_html=True)
                st.markdown(texto_lembrete_html, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

                with st.popover(f"Ver/Editar Detalhes 📝 (ID: {project_id})", use_container_width=True):
                    with st.form(f"form_edicao_card_kanban_{project_id}"): 
                        st.markdown(f"**Editando: {projeto_nome_text.upper()}**") 
                        st.markdown("#### Evolução da Demanda")
                        etapas_do_projeto = df_etapas_config[df_etapas_config["Nome do Projeto"] == row.get("Projeto", "")] if "Nome do Projeto" in df_etapas_config.columns else pd.DataFrame()
                        etapas_concluidas_str = row.get("Etapas Concluidas", ""); etapas_concluidas_lista = []
                        if pd.notna(etapas_concluidas_str) and isinstance(etapas_concluidas_str, str) and etapas_concluidas_str.strip(): etapas_concluidas_lista = [e.strip() for e in etapas_concluidas_str.split(',') if e.strip()]
                        novas_etapas_marcadas = [] 
                        if not etapas_do_projeto.empty and "Etapa" in etapas_do_projeto.columns:
                            todas_etapas_possiveis = etapas_do_projeto["Etapa"].astype(str).str.strip().tolist(); total_etapas = len(todas_etapas_possiveis) 
                            num_etapas_concluidas = len(etapas_concluidas_lista); progresso = num_etapas_concluidas / total_etapas if total_etapas > 0 else 0
                            st.progress(progresso); st.caption(f"{num_etapas_concluidas} de {total_etapas} etapas concluídas ({progresso:.0%})")
                            for etapa in todas_etapas_possiveis:
                                marcado = st.checkbox(etapa, value=(etapa in etapas_concluidas_lista), key=f"chk_kanban_{project_id}_{utils.clean_key(etapa)}")
                                if marcado: novas_etapas_marcadas.append(etapa)
                        else: st.caption("Nenhuma etapa de evolução configurada."); todas_etapas_possiveis = []; total_etapas = 0
                        st.markdown("#### Informações e Prazos")
                        c1,c2,c3,c4 = st.columns(4)
                        with c1: status_selecionaveis = status_options[:]; status_atual = row.get('Status'); idx_status = status_selecionaveis.index(status_atual) if status_atual in status_selecionaveis else 0; novo_status_selecionado = st.selectbox("Status", status_selecionaveis, index=idx_status, key=f"status_kanban_{project_id}")
                        with c2: abertura_default = _to_date_safe(row.get('Data de Abertura')); nova_data_abertura = st.date_input("Data Abertura", value=abertura_default, key=f"abertura_kanban_{project_id}", format="DD/MM/YYYY")
                        with c3: agendamento_default = _to_date_safe(row.get('Agendamento')); novo_agendamento = st.date_input("Agendamento", value=agendamento_default, key=f"agend_kanban_{project_id}", format="DD/MM/YYYY")
                        with c4: finalizacao_default = _to_date_safe(row.get('Data de Finalização')); nova_data_finalizacao = st.date_input("Data Finalização", value=finalizacao_default, key=f"final_kanban_{project_id}", format="DD/MM/YYYY")
                        st.markdown("#### Detalhes do Projeto")
                        c5,c6,c7, c_prio = st.columns(4) 
                        with c5: projeto_val = row.get('Projeto', ''); idx_proj = projeto_options.index(projeto_val) if projeto_val in projeto_options else 0; novo_projeto = st.selectbox("Projeto", options=projeto_options, index=idx_proj, key=f"proj_kanban_{project_id}")
                        with c6: novo_analista = st.text_input("Analista", value=row.get('Analista', ''), key=f"analista_kanban_{project_id}")
                        with c7: novo_gestor = st.text_input("Gestor", value=row.get('Gestor', ''), key=f"gestor_kanban_{project_id}")
                        with c_prio:
                             prioridade_atual = row.get('Prioridade', 'Média'); prioridades = ["Baixa", "Média", "Alta"]
                             idx_prio = prioridades.index(prioridade_atual) if prioridade_atual in prioridades else 1
                             nova_prioridade = st.selectbox("Prioridade", options=prioridades, index=idx_prio, key=f"prio_kanban_{project_id}")
                        c8,c9 = st.columns(2)
                        with c8: agencia_val = row.get('Agência', ''); idx_ag = agencia_options.index(agencia_val) if agencia_val in agencia_options else 0; nova_agencia = st.selectbox("Agência", agencia_options, index=idx_ag, key=f"agencia_kanban_{project_id}")
                        with c9: tecnico_val = row.get('Técnico', ''); idx_tec = tecnico_options.index(tecnico_val) if tecnico_val in tecnico_options else 0; novo_tecnico = st.selectbox("Técnico", tecnico_options, index=idx_tec, key=f"tecnico_kanban_{project_id}")
                        nova_demanda = st.text_input("Demanda", value=row.get('Demanda', ''), key=f"demanda_kanban_{project_id}")
                        nova_descricao = st.text_area("Descrição", value=row.get('Descrição', ''), key=f"desc_kanban_{project_id}")
                        nova_observacao = st.text_area("Observação / Pendências", value=row.get('Observação', ''), key=f"obs_kanban_{project_id}")
                        links_salvos = row.get('Links de Referência', '')
                        if links_salvos and links_salvos.strip():
                            st.markdown("---"); st.markdown("📎 **Links Salvos** (clicáveis)")
                            links_lista = links_salvos.strip().split('\n')
                            for link in links_lista:
                                link_limpo = link.strip()
                                if link_limpo.startswith("http"):
                                    display_text = link_limpo; 
                                    if len(display_text) > 70: display_text = display_text[:67] + "..."
                                    st.markdown(f"- [{display_text}]({link_limpo})")
                                elif link_limpo: st.markdown(f"- {link_limpo} (Texto salvo)")
                            st.markdown("---")
                        nova_links = st.text_area("Editar Links de Referência", value=links_salvos, key=f"links_kanban_{project_id}", placeholder="Cole links aqui, um por linha...")
                        log_agendamento_existente = row.get("Log Agendamento", "") if pd.notna(row.get("Log Agendamento")) else ""; st.text_area("Histórico de Alterações", value=log_agendamento_existente, height=100, disabled=True, key=f"log_kanban_{project_id}")
                        _, col_save, col_delete = st.columns([3, 1.5, 1]) 
                        with col_save: btn_salvar_card = st.form_submit_button("💾 Salvar", use_container_width=True)
                        with col_delete: btn_excluir_card = st.form_submit_button("🗑️ Excluir", use_container_width=True, type="primary")
                        if btn_excluir_card:
                            if utils.excluir_projeto_db(project_id): st.success(f"Projeto ID {project_id} excluído."); time.sleep(1); st.rerun() 
                        if btn_salvar_card:
                            status_final = novo_status_selecionado 
                            if novo_projeto == "N/A": st.error("ERRO: 'Projeto' é obrigatório.", icon="🚨"); st.stop()
                            if nova_agencia == "N/A": st.error("ERRO: 'Agência' é obrigatória.", icon="🚨"); st.stop()
                            if 'finalizad' in status_final.lower():
                                if total_etapas > 0 and len(novas_etapas_marcadas) < total_etapas: st.error(f"ERRO: Para 'Finalizado', todas as {total_etapas} etapas devem estar selecionadas.", icon="🚨"); st.stop() 
                                if not _to_date_safe(nova_data_finalizacao): st.error("ERRO: Se 'Finalizada', Data de Finalização é obrigatória.", icon="🚨"); st.stop() 
                            status_atual_normalizado = str(row.get('Status', '')).strip().upper(); status_final_normalizado = str(status_final).strip().upper()
                            if (status_atual_normalizado == 'NÃO INICIADA') and (len(novas_etapas_marcadas) > 0) and (status_final_normalizado == 'NÃO INICIADA'):
                                status_final = 'EM ANDAMENTO'; st.info("Status alterado para 'EM ANDAMENTO'.")
                            nova_data_abertura_date = _to_date_safe(nova_data_abertura); nova_data_finalizacao_date = _to_date_safe(nova_data_finalizacao); novo_agendamento_date = _to_date_safe(novo_agendamento)
                            updates = {"Status": status_final, "Agendamento": novo_agendamento_date, "Analista": novo_analista,"Agência": nova_agencia if nova_agencia != "N/A" else None, "Gestor": novo_gestor, "Projeto": novo_projeto, "Técnico": novo_tecnico if novo_tecnico != "N/A" else None, "Demanda": nova_demanda, "Descrição": nova_descricao, "Observação": nova_observacao, "Data de Abertura": nova_data_abertura_date, "Data de Finalização": nova_data_finalizacao_date, "Etapas Concluidas": ",".join(novas_etapas_marcadas) if novas_etapas_marcadas else None, "Prioridade": nova_prioridade, "Links de Referência": nova_links }
                            if utils.atualizar_projeto_db(project_id, updates): st.success(f"Projeto '{novo_projeto}' (ID: {project_id}) atualizado."); time.sleep(1); st.rerun() 
            st.markdown("<div style='flex-grow: 1; min-height: 1px;'></div>", unsafe_allow_html=True) 
    
    # --- LOOP 2: Desenhar a PAGINAÇÃO ---
    st.divider() 
    pagination_cols = st.columns(len(colunas_kanban))
    for i, col_nome in enumerate(colunas_kanban):
        with pagination_cols[i]:
            details = pagination_details[col_nome]; key_pagina = details["key"]; total_paginas = details["total_paginas"]; total_itens = details["total_itens"]; inicio = details["inicio"]; fim = details["fim"]
            exibindo_ate = min(fim, total_itens)
            st.markdown(f"<div style='text-align:center; font-size:0.85rem;'>Exibindo {inicio + 1 if total_itens>0 else 0}–{exibindo_ate} de {total_itens}</div>", unsafe_allow_html=True)
            col_btn1, col_txt, col_btn2 = st.columns([1, 2, 1])
            with col_btn1:
                if st.button("⬅️", key=f"prev_{col_nome}", use_container_width=True, disabled=(st.session_state[key_pagina] <= 1)):
                    st.session_state[key_pagina] -= 1; st.rerun()
            with col_txt:
                st.markdown(f"<div style='text-align:center; padding-top: 5px;'>Pág {st.session_state[key_pagina]} de {total_paginas}</div>", unsafe_allow_html=True)
            with col_btn2:
                if st.button("➡️", key=f"next_{col_nome}", use_container_width=True, disabled=(st.session_state[key_pagina] >= total_paginas)):
                    st.session_state[key_pagina] += 1; st.rerun()

# ----------------- Função: Main (ATUALIZADA) -----------------
def main():
    # Inicializa estados
    if "logado" not in st.session_state: st.session_state.logado = False
    if "boas_vindas" not in st.session_state: st.session_state.boas_vindas = False 
    if "tela_principal" not in st.session_state: st.session_state.tela_principal = False
    if "tela_cadastro_proj" not in st.session_state: st.session_state.tela_cadastro_proj = False
    if "tela_configuracoes" not in st.session_state: st.session_state.tela_configuracoes = False
    if "usuario" not in st.session_state: st.session_state.usuario = None 
    if "permissao" not in st.session_state: st.session_state.permissao = "Usuario" # Padrão
    if "visao_atual" not in st.session_state: st.session_state.visao_atual = "Lista" 
    if "tela_relatorio_excel" not in st.session_state: st.session_state.tela_relatorio_excel = False

    # --- LÓGICA PRINCIPAL DE ROTEAMENTO (COM PERMISSÕES) ---
    
    if not st.session_state.logado:
        tela_login()
    elif st.session_state.boas_vindas:
        tela_boas_vindas()
    elif st.session_state.tela_principal:
        
        # Pega a permissão do usuário
        is_admin = (st.session_state.permissao == "Admin")

        # --- Sidebar ---
        st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}")
        st.sidebar.divider()
        st.sidebar.title("Ações")
        
        if st.sidebar.button("➕ Novo Projeto", use_container_width=True):
            st.session_state.tela_cadastro_proj = True
            st.session_state.tela_configuracoes = False; st.session_state.tela_relatorio_excel = False 
            st.rerun()
            
        st.sidebar.divider() 
        st.sidebar.title("Sistema")
        
        # --- Botões de Admin ---
        if is_admin: # Só mostra para Admins
            if st.sidebar.button("➕ Usuários", use_container_width=True):
                st.session_state.tela_configuracoes = True
                st.session_state.tela_cadastro_proj = False; st.session_state.tela_relatorio_excel = False 
                st.rerun()
            
            # (Adicione o botão de Relatório Excel aqui, se também for só para Admin)
            # if st.sidebar.button("📊 Relatório de Itens", use_container_width=True):
            #    ... (lógica) ...
            
        if st.sidebar.button("Logout", use_container_width=True, type="primary"):
            st.session_state.clear(); st.rerun()
    
        # --- Lógica de Exibição da Página ---
        
        if st.session_state.get("tela_configuracoes"):
            if is_admin: tela_configuracoes() # Proteção extra
            else: st.error("Acesso negado."); tela_projetos() # Volta para o início
        elif st.session_state.get("tela_cadastro_proj"):
            tela_cadastro_projeto() 
        # (Adicione a rota para 'tela_relatorio_excel' aqui)
        # elif st.session_state.get("tela_relatorio_excel"):
        #    tela_relatorio_excel() 
        else:
            # --- Seletor de Visão (Só para Admin) ---
            if is_admin:
                st.markdown("#### 👁️ Modo de Visualização")
                st.session_state.visao_atual = st.radio(
                    "Escolha a visão:", ["Lista", "Kanban"],
                    horizontal=True, label_visibility="collapsed", key="seletor_visao"
                )
            else:
                st.session_state.visao_atual = "Lista" # Usuários normais só veem a lista
            
            if st.session_state.visao_atual == "Kanban" and is_admin:
                tela_kanban() 
            else:
                tela_projetos() # Padrão
            
    else:
        st.session_state.clear(); st.session_state.logado = False; st.rerun()

# --- PONTO DE ENTRADA DO APP ---
if __name__ == "__main__":
    utils.criar_tabelas_iniciais() 
    main()
