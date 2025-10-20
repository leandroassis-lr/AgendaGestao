import streamlit as st
import pandas as pd
from datetime import date, datetime
import re
import html

# Importa TODAS as nossas funções do arquivo utils.py
import utils 

# ----------------- Helpers -----------------
def _to_date_safe(val):
    """Converte várias representações (str, pd.Timestamp, datetime, date) para datetime.date ou None."""
    if val is None:
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
utils.load_css() # Carrega o CSS do arquivo utils

# ----------------- Telas da Página Principal -----------------
def tela_login():
    st.markdown("<div class='main-title'>GESTÃO DE PROJETOS</div>", unsafe_allow_html=True)
    st.title("")
    st.write("")
    with st.form("form_login"):
        email = st.text_input("Email (Opcional)", key="login_email")
        st.text_input("Senha (Desativada)", type="password", disabled=True)
        if st.form_submit_button("Conectar-se"):
            nome_usuario = "Visitante"
            # Esta função (autenticar_direto) já foi atualizada no utils.py
            if email: nome_usuario = utils.autenticar_direto(email) or email
            st.session_state.update(usuario=nome_usuario, logado=True)
            st.rerun()
    st.divider()
    if st.button("Novo usuário", key="btn_novo_usuario"):
        st.session_state.cadastro = True
        st.rerun()

def tela_cadastro_usuario():
    st.subheader("Cadastrar Novo Usuário")
    with st.form("form_cadastro_usuario"):
        nome = st.text_input("Nome", key="cad_nome")
        email = st.text_input("Email", key="cad_email")
        senha = st.text_input("Senha", type="password", key="cad_senha")
        if st.form_submit_button("Cadastrar"):
            if not nome or not email:
                st.error("Preencha Nome e Email.")
                return
            
            # --- MUDANÇA AQUI ---
            # Carrega usuários do banco de dados
            df = utils.carregar_usuarios_db() 
            
            if email.lower() in df["Email"].astype(str).str.lower().values:
                st.error("Email já cadastrado!")
            else:
                nova_linha = pd.DataFrame([[nome, email, senha]], columns=["Nome", "Email", "Senha"]) # Colunas corretas
                df = pd.concat([df, nova_linha], ignore_index=True)
                
                # --- MUDANÇA AQUI ---
                # Salva usuários no banco de dados
                if utils.salvar_usuario_db(df): 
                    st.success("Usuário cadastrado!")
                    st.session_state.cadastro = False
                    st.rerun()
                else:
                    st.error("Erro ao salvar usuário no banco de dados.")

    if st.button("Voltar para Login"):
        st.session_state.cadastro = False
        st.rerun()

def tela_cadastro_projeto():
    if st.button("⬅️ Voltar para Projetos"):
        st.session_state.tela_cadastro_proj = False
        st.rerun()
    st.subheader("Cadastrar Novo Projeto")
    
    # --- MUDANÇA AQUI ---
    # Carrega perguntas do banco de dados
    perguntas_customizadas = utils.carregar_config_db("perguntas") 
    
    if perguntas_customizadas.empty:
        st.info("🚨 Nenhuma pergunta customizada configurada. (Vá para Configurações > Perguntas)")
        return

    with st.form("form_cadastro_projeto"):
        respostas_customizadas = {}
        for index, row in perguntas_customizadas.iterrows():
            pergunta = row['Pergunta']; tipo = row['Tipo (texto, numero, data)']; key = utils.clean_key(pergunta)
            if tipo == 'data': respostas_customizadas[pergunta] = st.date_input(pergunta, value=None, key=f"custom_{key}", format="DD/MM/YYYY")
            elif tipo == 'numero': respostas_customizadas[pergunta] = st.number_input(pergunta, key=f"custom_{key}", step=1)
            else: respostas_customizadas[pergunta] = st.text_input(pergunta, key=f"custom_{key}")
        btn_cadastrar = st.form_submit_button("Cadastrar Projeto")
    
    if btn_cadastrar:
        projeto_nome = respostas_customizadas.get(perguntas_customizadas.iloc[0]['Pergunta'], 'Projeto Customizado')
        nova_linha_data = {
            "Status": "NÃO INICIADA",
            "Data de Abertura": date.today().strftime('%Y-%m-%d'),
            "Analista": st.session_state.get('usuario', 'N/A'),
            "Projeto": projeto_nome
        }
        for pergunta, resposta in respostas_customizadas.items():
            if isinstance(resposta, date):
                nova_linha_data[pergunta] = resposta.strftime('%Y-%m-%d')
            else:
                nova_linha_data[pergunta] = resposta
        
        if utils.adicionar_projeto_db(nova_linha_data):
            st.success(f"Projeto '{projeto_nome}' cadastrado!")
            st.session_state["tela_cadastro_proj"] = False
            st.rerun()

def tela_projetos():
    st.markdown("<div class='section-title-center'>PROJETOS</div>", unsafe_allow_html=True)
    
    # --- MUDANÇAS AQUI ---
    df = utils.carregar_projetos_db()
    df_sla = utils.carregar_config_db("sla") 
    df_etapas_config = utils.carregar_config_db("etapas_evolucao") 
    
    if df.empty:
        st.info("Nenhum projeto cadastrado ainda.")
        return

    # Normaliza agendamento para string segura
    df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime("%d/%m/%y").fillna('N/A')

    st.markdown("#### 🔍 Filtros e Busca")
    termo_busca = st.text_input("Buscar", key="termo_busca", placeholder="Digite um termo para buscar...")
    col1, col2, col3, col4 = st.columns(4)
    campos_select_1 = {"Status": col1, "Analista": col2, "Agência": col3, "Gestor": col4}
    campos_select_2 = {"Projeto": col1, "Técnico": col2}
    filtros = {}
    for campo, col in campos_select_1.items():
        with col:
            if campo in df.columns:
                opcoes = ["Todos"] + sorted(df[campo].astype(str).unique().tolist())
                filtros[campo] = st.selectbox(f"Filtrar por {campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")
    for campo, col in campos_select_2.items():
        with col:
            if campo in df.columns:
                opcoes = ["Todos"] + sorted(df[campo].astype(str).unique().tolist())
                filtros[campo] = st.selectbox(f"Filtrar por {campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")

    data_existente = pd.to_datetime(df['Agendamento'], errors='coerce').dropna()
    data_min = data_existente.min().date() if not data_existente.empty else date.today()
    data_max = data_existente.max().date() if not data_existente.empty else date.today()
    with col3:
        st.markdown("Agendamento (De):")
        data_inicio_filtro = st.date_input("De", value=data_min, key="filtro_data_start", label_visibility="collapsed", format="DD/MM/YYYY")
    with col4:
        st.markdown("Agendamento (Até):")
        data_fim_filtro = st.date_input("Até", value=data_max, key="filtro_data_end", label_visibility="collapsed", format="DD/MM/YYYY")

    df_filtrado = df.copy()
    for campo, valor in filtros.items():
        if valor != "Todos" and campo in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado[campo].astype(str) == valor]
    if data_inicio_filtro and data_fim_filtro:
        agendamento_dates = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce').dt.date
        mask = agendamento_dates.notna() & (agendamento_dates >= data_inicio_filtro) & (agendamento_dates <= data_fim_filtro)
        df_filtrado = df_filtrado[mask.fillna(False)]
    if termo_busca:
        termo = termo_busca.lower().strip()
        mask_busca = df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(termo, na=False).any(), axis=1)
        df_filtrado = df_filtrado[mask_busca]

    st.markdown("---")
    st.info(f"Projetos encontrados: {len(df_filtrado)}")
    
    # --- MUDANÇAS AQUI ---
    agencias_cfg = utils.carregar_config_db("agencias")
    tecnicos_cfg = utils.carregar_config_db("tecnicos")
    status_options_df = utils.carregar_config_db("status") # Pega o DataFrame
    
    agencia_options = ["N/A"] + (agencias_cfg["Agência"].tolist() if not agencias_cfg.empty else [])
    tecnico_options = ["N/A"] + (tecnicos_cfg["Técnico"].tolist() if not tecnicos_cfg.empty else [])
    status_options = status_options_df["Status"].tolist() if not status_options_df.empty else [] # Pega a lista

    for _, row in df_filtrado.iterrows():
        project_id = row['ID']
        
        status_raw = row['Status'] if pd.notna(row['Status']) else 'N/A'
        status_text = html.escape(str(status_raw))
        analista_text = html.escape(str(row['Analista'])) if pd.notna(row['Analista']) else 'N/A'
        agencia_text = html.escape(str(row.get("Agencia", "N/A")))
        projeto_text = html.escape(str(row.get("Projeto", "N/A")))
        demanda_text = html.escape(str(row.get("Demanda", "N/A")))
        tecnico_text = html.escape(str(row.get("Tecnico", "N/A")))
        status_color_name = utils.get_status_color(str(status_raw))
        sla_text, sla_color = utils.calcular_sla(row, df_sla)

        st.markdown("<div class='project-card'>", unsafe_allow_html=True)
        col_info, col_analista, col_agencia, col_status = st.columns([3, 2, 2, 1.5])
        with col_info:
            st.markdown(f"<h6>📅 {row['Agendamento_str']}</h6>", unsafe_allow_html=True)
            st.markdown(f"<h5 style='margin:2px 0'>{projeto_text.upper()}</h5>", unsafe_allow_html=True)
            st.markdown(f"<small style='color:var(--muted);'>{demanda_text} - {tecnico_text}</small>", unsafe_allow_html=True)
        with col_analista:
            st.markdown(f"**Analista:** {analista_text}")
            st.markdown(f"<p style='color:{sla_color}; font-weight:bold;'>{sla_text}</p>", unsafe_allow_html=True)
        with col_agencia:
            st.markdown(f"**Agência:**")
            st.markdown(f"{agencia_text}")
        with col_status:
            st.markdown(
                f"""<div style="height:100%;display:flex;align-items:center;justify-content:flex-end;">
                <span style="background-color:{status_color_name};color:black;padding:8px 15px;border-radius:5px;font-weight:bold;font-size:0.9em;">{status_text}</span>
                </div>""",
                unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander(f"Ver/Editar Detalhes - ID: {project_id}"):
            with st.form(f"form_edicao_card_{project_id}"):
                
                st.markdown("#### Evolução da Demanda")
                etapas_do_projeto = df_etapas_config[df_etapas_config["Nome do Projeto"] == row.get("Projeto", "")]
                etapas_concluidas_str = row.get("Etapas Concluidas", "")
                etapas_concluidas_lista = etapas_concluidas_str.split(',') if isinstance(etapas_concluidas_str, str) and etapas_concluidas_str else []
                novas_etapas_marcadas = []
                if not etapas_do_projeto.empty:
                    total_etapas = len(etapas_do_projeto)
                    num_etapas_concluidas = len(etapas_concluidas_lista)
                    progresso = num_etapas_concluidas / total_etapas if total_etapas > 0 else 0
                    st.progress(progresso)
                    st.caption(f"{num_etapas_concluidas} de {total_etapas} etapas concluídas ({progresso:.0%})")
                    for etapa in etapas_do_projeto["Etapa"]:
                        marcado = st.checkbox(etapa, value=(etapa in etapas_concluidas_lista), key=f"chk_{project_id}_{utils.clean_key(etapa)}")
                        if marcado: novas_etapas_marcadas.append(etapa)
                else:
                    st.caption("Nenhuma etapa de evolução configurada para este tipo de projeto.")

                st.markdown("#### Informações e Prazos")
                c1,c2,c3,c4 = st.columns(4)
                with c1:
                    status_selecionaveis = status_options[:] # Usa a lista carregada do DB
                    if row.get('Status') != 'NÃO INICIADA':
                        if 'NÃO INICIADA' in status_selecionaveis: status_selecionaveis.remove('NÃO INICIADA')
                    idx_status = status_selecionaveis.index(row['Status']) if row['Status'] in status_selecionaveis else 0
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

                st.markdown("#### Detalhes do Projeto")
                c5,c6,c7 = st.columns(3)
                with c5: novo_projeto = st.text_input("Projeto", value=row['Projeto'], key=f"proj_{project_id}")
                with c6: novo_analista = st.text_input("Analista", value=row['Analista'], key=f"analista_{project_id}")
                with c7: novo_gestor = st.text_input("Gestor", value=row['Gestor'], key=f"gestor_{project_id}")
                c8,c9 = st.columns(2)
                with c8: 
                    agencia_val = row.get('Agência', '')
                    idx_ag = agencia_options.index(agencia_val) if agencia_val in agencia_options else 0
                    nova_agencia = st.selectbox("Agência", agencia_options, index=idx_ag, key=f"agencia_{project_id}")
                with c9:
                    tecnico_val = row.get('Técnico', '')
                    idx_tec = tecnico_options.index(tecnico_val) if tecnico_val in tecnico_options else 0
                    novo_tecnico = st.selectbox("Técnico", tecnico_options, index=idx_tec, key=f"tecnico_{project_id}")

                nova_demanda = st.text_input("Demanda", value=row.get('Demanda', ''), key=f"demanda_{project_id}")
                nova_descricao = st.text_area("Descrição", value=row.get('Descrição', ''), key=f"desc_{project_id}")
                nova_observacao = st.text_area("Observação / Pendências", value=row.get('Observação', ''), key=f"obs_{project_id}")
                log_agendamento_existente = row.get("Log Agendamento", "") if pd.notna(row.get("Log Agendamento")) else ""
                st.text_area("Histórico de Agendamento", value=log_agendamento_existente, height=100, disabled=True, key=f"log_{project_id}")

                btn_salvar_card = st.form_submit_button("💾 Salvar Alterações")
                
            if btn_salvar_card:
                status_final = novo_status_selecionado
                if row['Status'] == 'NÃO INICIADA' and len(novas_etapas_marcadas) > 0:
                    status_final = 'EM ANDAMENTO'
                    st.info("Status alterado para 'EM ANDAMENTO'!")
                
                # Normaliza datas inseridas pelo usuário
                nova_data_abertura_date = _to_date_safe(nova_data_abertura)
                nova_data_finalizacao_date = _to_date_safe(nova_data_finalizacao)
                novo_agendamento_date = _to_date_safe(novo_agendamento)

                if 'finalizad' in status_final.lower():
                    total_etapas_config = len(etapas_do_projeto)
                    if total_etapas_config > 0 and len(novas_etapas_marcadas) < total_etapas_config:
                        st.error(f"ERRO: Para finalizar, todas as {total_etapas_config} etapas devem ser marcadas.", icon="🚨")
                        st.stop()
                    if not nova_data_finalizacao_date:
                        st.error("ERRO: Se o status é 'Finalizada', a Data de Finalização é obrigatória.", icon="🚨")
                        st.stop()
                
                log_final = row.get("Log Agendamento", "") if pd.notna(row.get("Log Agendamento")) else ""
                agendamento_antigo = row.get('Agendamento', None)
                agendamento_antigo_date = _to_date_safe(agendamento_antigo)

                if (agendamento_antigo_date is None and novo_agendamento_date is not None) or (agendamento_antigo_date is not None and novo_agendamento_date != agendamento_antigo_date):
                    data_antiga_str = agendamento_antigo_date.strftime('%d/%m/%Y') if agendamento_antigo_date else "N/A"
                    data_nova_str = novo_agendamento_date.strftime('%d/%m/%Y') if novo_agendamento_date else "N/A"
                    hoje_str = date.today().strftime('%d/%m/%Y')
                    nova_entrada_log = f"Em {hoje_str}: alterado de '{data_antiga_str}' para '{data_nova_str}'."
                    log_final = f"{log_final}\n{nova_entrada_log}".strip()

                updates = {
                    "Status": status_final,
                    "Agendamento": novo_agendamento_date.strftime('%Y-%m-%d') if novo_agendamento_date else None,
                    "Analista": novo_analista,
                    "Agência": nova_agencia,
                    "Gestor": novo_gestor,
                    "Projeto": novo_projeto,
                    "Técnico": novo_tecnico,
                    "Demanda": nova_demanda,
                    "Descrição": nova_descricao,
                    "Observação": nova_observacao,
                    "Data de Abertura": nova_data_abertura_date.strftime('%Y-%m-%d') if nova_data_abertura_date else None,
                    "Data de Finalização": nova_data_finalizacao_date.strftime('%Y-%m-%d') if nova_data_finalizacao_date else None,
                    "Etapas Concluidas": ",".join(novas_etapas_marcadas),
                    "Log Agendamento": log_final
                }

                if utils.atualizar_projeto_db(project_id, updates):
                    st.success(f"Projeto '{novo_projeto}' (ID: {project_id}) atualizado.")
                    st.rerun()

            st.markdown("---")
            if st.button("🗑️ Excluir Projeto", key=f"btn_excluir_{project_id}", type="primary"):
                if utils.excluir_projeto_db(project_id):
                    st.rerun()

# ----------------- CONTROLE PRINCIPAL -----------------
def main():
    if "logado" not in st.session_state: st.session_state.logado = False
    if "cadastro" not in st.session_state: st.session_state.cadastro = False
    if "tela_cadastro_proj" not in st.session_state: st.session_state.tela_cadastro_proj = False

    if not st.session_state.get("logado", False):
        if st.session_state.get("cadastro", False):
            tela_cadastro_usuario()
        else:
            tela_login()
        return

    # ==========================================================
    # FERRAMENTA DE MIGRAÇÃO (ADICIONADA AQUI)
    # ==========================================================
    with st.expander("🚨 FERRAMENTA DE MIGRAÇÃO (USO ÚNICO) 🚨"):
        st.warning("Clique neste botão APENAS UMA VEZ para copiar os dados dos arquivos Excel (config.xlsx, usuarios.xlsx) para o banco de dados Turso. Após o sucesso, remova este bloco de código do app.py.")
        
        if st.button("EXECUTAR MIGRAÇÃO DE DADOS"):
            try:
                st.subheader("Migrando Configurações...")
                # Puxa a lista de abas do utils.py
                tabs_config = list(utils.CONFIG_TABS_EXCEL.keys()) 
                prog_bar_config = st.progress(0, text="Migrando configurações...")
                
                for i, tab_name in enumerate(tabs_config):
                    # Carrega do Excel
                    df_excel = utils._carregar_config_excel(tab_name) 
                    if not df_excel.empty:
                        # Salva no DB
                        if utils.salvar_config_db(df_excel, tab_name): 
                            st.write(f"✅ Aba '{tab_name}' migrada com sucesso.")
                        else:
                            st.error(f"❌ Falha ao salvar '{tab_name}' no DB.")
                    else:
                        st.write(f"ℹ️ Aba '{tab_name}' estava vazia no Excel. Pulando.")
                    prog_bar_config.progress((i + 1) / len(tabs_config), text=f"Migrando: {tab_name}")
                
                st.subheader("Migrando Usuários...")
                # Carrega do Excel
                df_usuarios_excel = utils._carregar_usuarios_excel() 
                if not df_usuarios_excel.empty:
                    # Salva no DB
                    if utils.salvar_usuario_db(df_usuarios_excel): 
                        st.success("✅ Usuários migrados com sucesso!")
                    else:
                        st.error("❌ Falha ao salvar usuários no DB.")
                else:
                    st.info("ℹ️ Arquivo 'usuarios.xlsx' estava vazio. Pulando.")
                
                st.balloons()
                st.success("🎉 MIGRAÇÃO CONCLUÍDA! 🎉")
                st.info("Pode recarregar a página (F5). Você pode remover este expander do 'app.py' agora.")
                st.cache_data.clear() # Limpa todo o cache
                
            except Exception as e:
                st.error(f"Ocorreu um erro durante a migração: {e}")
    # ==========================================================
    # FIM DA FERRAMENTA DE MIGRAÇÃO
    # ==========================================================

    st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}! 📋")
    st.sidebar.divider()
    # O Streamlit criará a navegação para as outras páginas aqui!
    st.sidebar.divider()
    st.sidebar.title("Ações")
    if st.sidebar.button("➕ Novo Projeto", use_container_width=True):
        st.session_state.tela_cadastro_proj = True
        st.rerun()
    st.sidebar.divider()
    st.sidebar.title("Sistema")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    
    if st.session_state.get("tela_cadastro_proj"):
        tela_cadastro_projeto()
    else:
        tela_projetos()

if __name__ == "__main__":
    main()
