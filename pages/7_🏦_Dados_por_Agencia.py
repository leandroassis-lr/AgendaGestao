import streamlit as st
import pandas as pd
import utils # Apenas para CSS e Login Check
import utils_chamados # <<< NOSSO ARQUIVO
from datetime import date, datetime
import re 
import html 

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() 
except:
    pass 

# --- Controle Principal de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()
    
# Função Helper para converter datas (evita erros)
def _to_date_safe(val):
    if val is None or pd.isna(val): return None
    if isinstance(val, date) and not isinstance(val, datetime): return val
    try:
        ts = pd.to_datetime(val, errors='coerce', dayfirst=True) 
        if pd.isna(ts): return None
        return ts.date()
    except Exception: return None

# --- Funções Helper da Página ---
def extrair_e_mapear_colunas(df, col_map):
    df_extraido = pd.DataFrame()
    colunas_originais = df.columns.tolist()
    
    if len(colunas_originais) < 20: 
        st.error(f"Erro: O arquivo carregado parece ter apenas {len(colunas_originais)} colunas.")
        return None
    try:
        col_nomes_originais = {idx: colunas_originais[idx] for idx in col_map.keys() if idx < len(colunas_originais)}
        df_para_renomear = df[list(col_nomes_originais.values())].copy() 
        col_rename_map = {orig_name: db_name for idx, db_name in col_map.items() if idx in col_nomes_originais and (orig_name := col_nomes_originais[idx])}
        df_extraido = df_para_renomear.rename(columns=col_rename_map)
    except KeyError as e:
        st.error(f"Erro ao mapear colunas. Coluna esperada {e} não encontrada.")
        return None
    except Exception as e:
        st.error(f"Erro ao processar colunas: {e}"); return None
    return df_extraido

def formatar_agencia_excel(id_agencia, nome_agencia):
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except (ValueError, TypeError): id_str = str(id_agencia).strip() 
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo):
          nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"

# --- 1. DIALOG (POP-UP) DE IMPORTAÇÃO (COM MULTI-UPLOAD E UTF-8) ---
@st.dialog("Importar Novos Chamados (Excel/CSV)")
def run_importer_dialog():
    st.info(f"""
            Arraste seu arquivo Excel de chamados (formato `.xlsx` ou `.csv` com `;`) aqui.
            O sistema espera que a **primeira linha** contenha os cabeçalhos.
            As colunas necessárias (A, B, C, D, J, K, L, M, N, O, Q, T) serão lidas automaticamente.
            Se um `Chamado` (Coluna A) já existir, ele será **atualizado**.
    """)
    
    uploaded_files = st.file_uploader(
        "Selecione o(s) arquivo(s) Excel/CSV de chamados", 
        type=["xlsx", "xls", "csv"], 
        key="chamado_uploader_dialog",
        accept_multiple_files=True
    )

    if uploaded_files:
        dfs_list = []
        all_files_ok = True
        
        with st.spinner("Lendo e processando arquivos..."):
            for uploaded_file in uploaded_files:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_individual = pd.read_csv(uploaded_file, sep=';', header=0, encoding='utf-8', keep_default_na=False, dtype=str) 
                    else:
                        df_individual = pd.read_excel(uploaded_file, header=0, keep_default_na=False, dtype=str) 

                    df_individual.dropna(how='all', inplace=True)
                    if not df_individual.empty:
                        dfs_list.append(df_individual)
                    else:
                        st.warning(f"Arquivo '{uploaded_file.name}' está vazio e será ignorado.")
                
                except Exception as e:
                    st.error(f"Erro ao ler o arquivo '{uploaded_file.name}': {e}")
                    all_files_ok = False
                    break 

        if dfs_list and all_files_ok:
            try:
                df_raw = pd.concat(dfs_list, ignore_index=True)
                if df_raw.empty:
                    st.error("Erro: Nenhum dado válido encontrado nos arquivos.")
                    return
            except Exception as e:
                st.error(f"Erro ao combinar arquivos: {e}")
                return

            col_map = {
                0: 'chamado_id', 1: 'agencia_id', 2: 'agencia_nome', 3: 'agencia_uf',
                9: 'servico', 10: 'projeto_nome', 11: 'data_agendamento', 12: 'sistema',
                13: 'cod_equipamento', 14: 'nome_equipamento', 
                16: 'quantidade', # Coluna Q (Quantidade_Solicitada)
                19: 'gestor'
            }
            df_para_salvar = extrair_e_mapear_colunas(df_raw, col_map)
            
            if df_para_salvar is not None:
                st.success(f"Sucesso! {len(df_raw)} linhas lidas de {len(uploaded_files)} arquivo(s). Pré-visualização:")
                st.dataframe(df_para_salvar.head(), use_container_width=True)
                
                if st.button("▶️ Iniciar Importação de Chamados"):
                    if df_para_salvar.empty: 
                        st.error("Planilha vazia ou colunas não encontradas.")
                    else:
                        with st.spinner("Importando e atualizando chamados..."):
                            reverse_map = {
                                'chamado_id': 'Chamado', 'agencia_id': 'Codigo_Ponto', 'agencia_nome': 'Nome',
                                'agencia_uf': 'UF', 'servico': 'Servico', 'projeto_nome': 'Projeto',
                                'data_agendamento': 'Data_Agendamento', 'sistema': 'Tipo_De_Solicitacao',
                                'cod_equipamento': 'Sistema', 'nome_equipamento': 'Codigo_Equipamento',
                                'quantidade': 'Quantidade_Solicitada', 
                                'gestor': 'Substitui_Outro_Equipamento_(Sim/Não)'
                            }
                            df_final_para_salvar = df_para_salvar.rename(columns=reverse_map)
                            sucesso, num_importados = utils_chamados.bulk_insert_chamados_db(df_final_para_salvar)
                            if sucesso:
                                st.success(f"🎉 {num_importados} chamados importados/atualizados com sucesso!")
                                st.balloons()
                                st.session_state.importer_done = True 
                            else:
                                st.error("A importação de chamados falhou.")
        elif not all_files_ok:
            st.error("Processamento interrompido devido a erro na leitura de um arquivo.")
        elif not dfs_list:
            st.info("Nenhum dado válido encontrado nos arquivos selecionados.")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False 
        st.rerun()

    if st.button("Cancelar"):
        st.rerun()


# --- FUNÇÃO "CÉREBRO" DE STATUS ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    """
    Calcula o novo status de um projeto com base nas suas regras de negócio
    e atualiza o campo 'Status' de todos os chamados do grupo.
    """
    has_S = df_projeto['Nº Chamado'].str.contains('-S-').any()
    has_E = df_projeto['Nº Chamado'].str.contains('-E-').any()
    
    def check_col_present(df, col_name):
        if col_name in df.columns:
            return df[col_name].fillna('').astype(str).str.strip().ne('').any()
        return False

    def check_date_present(df, col_name):
        if col_name in df.columns:
            return df[col_name].notna().any()
        return False
    
    link_presente = check_col_present(df_projeto, 'Link Externo')
    pedido_presente = check_col_present(df_projeto, 'Nº Pedido')
    envio_presente = check_date_present(df_projeto, 'Data Envio')
    tecnico_presente = check_col_present(df_projeto, 'Técnico')
    
    novo_status = "Indefinido"

    # --- Cenário 1: Só Serviço (S-Only) ---
    if has_S and not has_E:
        if tecnico_presente:
            novo_status = "Em Andamento"
        elif link_presente:
            novo_status = "Acionar técnico"
        else:
            novo_status = "Não Iniciado"

    # --- Cenário 2: Misto (S e E) ---
    elif has_S and has_E:
        if tecnico_presente:
            novo_status = "Em Andamento"
        elif envio_presente:
            novo_status = "Equipamento entregue - Acionar técnico"
        elif pedido_presente:
            novo_status = "Equipamento Solicitado"
        elif link_presente:
            novo_status = "Solicitar Equipamento"
        else:
            novo_status = "Não Iniciado"

    # --- Cenário 3: Só Equipamento (E-Only) ---
    elif not has_S and has_E:
        if envio_presente:
            novo_status = "Equipamento entregue - Concluído"
        elif pedido_presente:
            novo_status = "Equipamento Solicitado"
        else:
            novo_status = "Solicitar Equipamento"
    
    else:
        novo_status = "Não Iniciado"

    # --- CORREÇÃO APLICADA AQUI (para o status_atual) ---
    status_atual_val = str(df_projeto.iloc[0]['Status']).strip() # Converte para string e limpa
    if status_atual_val == "" or status_atual_val.lower() == "none" or status_atual_val.lower() == "nan":
        status_atual = "Não Iniciado"
    else:
        status_atual = status_atual_val
    # --- FIM DA CORREÇÃO ---
    
    if status_atual != novo_status:
        st.info(f"Status do projeto mudou de '{status_atual}' para '{novo_status}'")
        updates = {"Status": novo_status}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    
    return False


# --- Tela Principal da Página ---
def tela_dados_agencia():
    
    # --- NOVO: CSS customizado para o Card (Layout da Foto 1) ---
    st.markdown("""
        <style>
            /* Injeta os estilos do card */
            .card-grid {
                display: grid;
                grid-template-columns: 2.5fr 2fr 2.5fr 2.5fr; /* 4 colunas */
                gap: 16px;
                align-items: start;
            }
            .card-grid h5 { /* Título do Projeto */
                margin-top: 5px;
                margin-bottom: 0;
                font-size: 1.15rem;
                font-weight: 700;
                color: var(--gray-darkest);
            }
            .card-grid .date {
                font-weight: 600;
                font-size: 0.95rem;
                color: var(--gray-dark);
            }
            .card-grid .label {
                font-size: 0.85rem;
                color: #555;
                margin-bottom: 0;
            }
            .card-grid .value {
                font-size: 0.95rem;
                font-weight: 500;
                color: var(--gray-darkest);
                margin-bottom: 8px; /* Espaço entre linhas */
            }
            .card-grid .sla {
                font-size: 0.9rem;
                font-weight: 600;
                margin-top: 5px;
            }
            .card-status-badge {
                background-color: #B0BEC5; /* Cor padrão 'Não Iniciado' */
                color: white;
                padding: 6px 12px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 0.85em;
                display: inline-block;
                width: 100%;
                text-align: center;
            }
            .card-action-text {
                text-align: center;
                font-size: 0.9em;
                font-weight: 600;
                margin-top: 8px;
                color: var(--primary-dark);
            }
            
            /* Ajuste para o expander "Ver/Editar" ficar alinhado */
            .project-card [data-testid="stExpander"] {
                border: 1px solid var(--gray-border);
                border-radius: var(--std-radius);
                margin-top: 15px;
            }
            .project-card [data-testid="stExpander"] > summary {
                font-weight: 600;
                font-size: 0.95rem;
            }
        </style>
    """, unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
    with c2:
        if st.button("📥 Importar Novos Chamados", use_container_width=True):
            run_importer_dialog()
    
    st.write(" ")
    utils_chamados.criar_tabela_chamados()
    st.divider()

    # --- 2. Carregar Dados ---
    with st.spinner("Carregando dados de chamados..."):
        df_chamados_raw = utils_chamados.carregar_chamados_db()

    if df_chamados_raw.empty:
        st.info("Nenhum dado de chamado encontrado no sistema. Comece importando um arquivo acima.")
        st.stop()

    # --- 3. Criar Campo Combinado de Agência ---
    if 'Cód. Agência' in df_chamados_raw.columns:
        df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(
            lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), 
            axis=1
        )
    else:
        st.error("Tabela de chamados incompleta (sem 'Cód. Agência'). Tente re-importar."); st.stop()

    # --- 4. Preparar Listas de Opções para Formulários ---
    prioridade_options = ["Baixa", "Média", "Alta", "Crítica"]
    projeto_list = sorted([str(p) for p in df_chamados_raw['Projeto'].dropna().unique() if p])
    gestor_list = sorted([str(g) for g in df_chamados_raw['Gestor'].dropna().unique() if g])
    
    lista_agencias_completa = sorted(df_chamados_raw['Agencia_Combinada'].dropna().astype(str).unique())
    agencia_list_no_todas = [a for a in lista_agencias_completa if a not in ["N/A", "None", ""]]
    lista_agencias_completa.insert(0, "Todas") 

    # --- 5. Filtro Principal por Agência ---
    st.markdown("#### 🏦 Selecionar Agência")
    agencia_selecionada = st.selectbox(
        "Selecione uma Agência para ver o histórico completo:",
        options=lista_agencias_completa,
        key="filtro_agencia_principal",
        label_visibility="collapsed"
    )
    st.divider()

    # --- 6. Filtrar DataFrame Principal ---
    if agencia_selecionada == "Todas":
        df_chamados_filtrado = df_chamados_raw
    else:
        df_chamados_filtrado = df_chamados_raw[df_chamados_raw['Agencia_Combinada'] == agencia_selecionada]

    # --- 7. Painel de KPIs ---
    total_chamados = len(df_chamados_filtrado)
    if not df_chamados_filtrado.empty:
        status_fechamento = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado', 'equipamento entregue - concluído']
        chamados_abertos_count = len(df_chamados_filtrado[~df_chamados_filtrado['Status'].astype(str).str.lower().isin(status_fechamento)])
    else:
        chamados_abertos_count = 0
    st.markdown(f"### 📊 Resumo da Agência: {agencia_selecionada}")
    cols_kpi = st.columns(2) 
    cols_kpi[0].metric("Total de Chamados", total_chamados)
    cols_kpi[1].metric("Chamados Abertos", chamados_abertos_count)
    st.divider()


    # --- 8. NOVA VISÃO HIERÁRQUICA (Agência -> Projeto -> Chamados) ---
    st.markdown("#### 📋 Visão por Projetos e Chamados")
    
    if df_chamados_filtrado.empty:
        st.info("Nenhum chamado encontrado para os filtros selecionados.")
        st.stop()

    # Prepara o DataFrame para agrupamento
    try:
        df_chamados_filtrado['Agendamento'] = pd.to_datetime(df_chamados_filtrado['Agendamento'], errors='coerce')
        df_chamados_filtrado['Agendamento_str'] = df_chamados_filtrado['Agendamento'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
        
        chave_agencia = 'Agencia_Combinada'
        chave_projeto = ['Projeto', 'Gestor', 'Agendamento_str']

    except Exception as e:
        st.error(f"Erro ao processar datas para agrupamento: {e}")
        st.stop()

    
    # --- NÍVEL 1: Loop pelas Agências ---
    if agencia_selecionada == "Todas":
        agencias_agrupadas = df_chamados_filtrado.groupby(chave_agencia)
    else:
        agencias_agrupadas = [(agencia_selecionada, df_chamados_filtrado)]

    for nome_agencia, df_agencia in agencias_agrupadas:
        
        hoje = pd.Timestamp.now().normalize()
        proximas_datas = df_agencia[df_agencia['Agendamento'] >= hoje]['Agendamento']
        
        header_agencia = f"🏦 {nome_agencia} ({len(df_agencia)} chamados)"
        if not proximas_datas.empty:
            prox_data_str = proximas_datas.min().strftime('%d/%m/%Y')
            header_agencia = f"🏦 {nome_agencia} ({len(df_agencia)} chamados) | 🗓️ Próximo Ag: {prox_data_str}"

        if agencia_selecionada == "Todas":
            expander_agencia = st.expander(header_agencia)
        else:
            expander_agencia = st.container() 

        with expander_agencia:
            
            # --- NÍVEL 2: Loop pelos Projetos ---
            try:
                projetos_agrupados = df_agencia.groupby(chave_projeto)
                if not projetos_agrupados.groups:
                    st.info(f"Nenhum chamado encontrado para a agência {nome_agencia}.")
                    continue 
            except KeyError:
                st.error("Falha ao agrupar por Projeto/Gestor/Agendamento.")
                continue

            for (nome_projeto, nome_gestor, data_agend), df_projeto in projetos_agrupados:
                
                # --- INÍCIO DA MUDANÇA (Layout de Card) ---
                
                first_row = df_projeto.iloc[0]
                chamado_ids_internos_list = df_projeto['ID'].tolist()
                
                # --- CORREÇÃO APLICADA AQUI ---
                status_val = str(first_row.get('Status', 'Não Iniciado')).strip() # Converte para string e limpa
                if status_val == "" or status_val.lower() == "none" or status_val.lower() == "nan":
                    status_principal_atual = "Não Iniciado"
                else:
                    status_principal_atual = status_val
                # --- FIM DA CORREÇÃO ---
                
                # --- Cálculo do SLA (Placeholder) ---
                sla_text = ""
                try:
                    agendamento_date = pd.to_datetime(data_agend, format='%d/%m/%Y')
                    hoje = pd.Timestamp.now().normalize()
                    dias_restantes = (agendamento_date - hoje).days
                    if dias_restantes < 0:
                        sla_text = f"<span style='color: var(--red-alert); font-weight: bold;'>SLA: {dias_restantes}d (Atrasado)</span>"
                    else:
                        sla_text = f"<span style='color: var(--primary-color);'>SLA: {dias_restantes}d restantes</span>"
                except Exception:
                    sla_text = "<span style='color: #888;'>SLA: N/D</span>"
                
                # --- Texto de Ação (Baseado no Status) ---
                acao_text = "FINALIZADO" # Default
                status_lower = status_principal_atual.lower() # Agora é seguro
                if "não iniciado" in status_lower:
                    acao_text = "INICIAR PROJETO"
                elif "acionar técnico" in status_lower:
                    acao_text = "ATRIBUIR TÉCNICO"
                elif "solicitar equipamento" in status_lower:
                    acao_text = "SOLICITAR EQUIPAMENTO"
                elif "equipamento solicitado" in status_lower:
                    acao_text = "REGISTRAR ENTREGA"
                elif "equipamento entregue - acionar" in status_lower:
                    acao_text = "ATRIBUIR TÉCNICO"
                elif "em andamento" in status_lower:
                    acao_text = "EM EXECUÇÃO"

                # --- Cor do Gestor ---
                gestor_color = utils_chamados.get_color_for_name(nome_gestor)
                
                def clean_val(val, default="N/A"):
                    if val is None or pd.isna(val) or str(val).lower() == "none" or str(val).lower() == "nan":
                        return default
                    return str(val)

                gestor_html = f"<span style='color: {gestor_color}; font-weight: 500;'>{html.escape(clean_val(nome_gestor))}</span>"
                projeto_html = html.escape(clean_val(nome_projeto, "Sem Projeto").upper())
                analista_html = html.escape(clean_val(first_row.get('Analista')))
                agencia_html = html.escape(clean_val(first_row.get('Agencia_Combinada')))
                status_html = html.escape(clean_val(status_principal_atual, "Não Iniciado").upper())
                
                status_color = utils_chamados.get_status_color(status_principal_atual)
                
                # --- Monta o HTML do Card ---
                card_html = f"""
                <div class="project-card"> <div class="card-grid">
                        
                        <div>
                            <div class="date">📅 {data_agend}</div>
                            <h5>{projeto_html}</h5>
                        </div>
                        
                        <div>
                            <div class="label">Analista:</div>
                            <div class="value">{analista_html}</div>
                            <div class="sla">{sla_text}</div>
                        </div>
                        
                        <div>
                            <div class="label">Agência:</div>
                            <div class="value">{agencia_html}</div>
                            <div class="label">Gestor:</div>
                            <div class="value">{gestor_html}</div>
                        </div>
                        
                        <div>
                            <div class="card-status-badge" style="background-color: {status_color};">
                                {status_html}
                            </div>
                            <div class="card-action-text">{acao_text}</div>
                        </div>
                        
                    </div>
                """
                
                st.markdown(card_html, unsafe_allow_html=True)
                
                expander_title = f"Ver/Editar Detalhes - ID: {first_row['ID']}"
                with st.expander(expander_title):
                    
                    form_key_lote = f"form_lote_edit_{first_row['ID']}"
                    with st.form(key=form_key_lote):
                        st.markdown(f"**Editar campos comuns (para {len(df_projeto)} chamados):**")
                        c1, c2, c3, c_btn = st.columns([2, 2, 1, 1])
                        
                        analista_val = first_row.get('Analista', '')
                        novo_analista = c1.text_input("Analista", value=analista_val, key=f"{form_key_lote}_analista")
                        tec_val = first_row.get('Técnico', '')
                        novo_tecnico = c2.text_input("Técnico", value=tec_val, key=f"{form_key_lote}_tec")
                        prior_val = first_row.get('Prioridade', 'Média')
                        prior_idx = prioridade_options.index(prior_val) if prior_val in prioridade_options else 1
                        nova_prioridade = c3.selectbox("Prioridade", options=prioridade_options, index=prior_idx, key=f"{form_key_lote}_prior")
                        btn_salvar_lote = c_btn.form_submit_button("💾 Salvar Lote", use_container_width=True)

                    if btn_salvar_lote:
                        updates = {"Analista": novo_analista, "Técnico": novo_tecnico, "Prioridade": nova_prioridade}
                        with st.spinner(f"Atualizando {len(chamado_ids_internos_list)} chamados..."):
                            sucesso_count = 0
                            for chamado_id in chamado_ids_internos_list:
                                if utils_chamados.atualizar_chamado_db(chamado_id, updates):
                                    sucesso_count += 1
                            st.success(f"{sucesso_count} de {len(chamado_ids_internos_list)} chamados foram atualizados!")
                            
                            df_chamados_atualizado = utils_chamados.carregar_chamados_db()
                            df_projeto_atualizado = df_chamados_atualizado[df_chamados_atualizado['ID'].isin(chamado_ids_internos_list)]
                            
                            if calcular_e_atualizar_status_projeto(df_projeto_atualizado, chamado_ids_internos_list):
                                st.cache_data.clear(); st.rerun()
                            else:
                                st.cache_data.clear(); st.rerun()
                    
                    st.markdown("---")
                    st.markdown("##### 🔎 Detalhes por Chamado Individual")
                    for _, chamado_row in df_projeto.iterrows():
                        chamado_id_interno = chamado_row['ID']
                        chamado_id_str = chamado_row['Nº Chamado']
                        form_key_ind = f"form_ind_edit_{chamado_id_interno}"
                        
                        with st.expander(f"▶️ Chamado: {chamado_id_str}"):
                            with st.form(key=form_key_ind):
                                is_servico = '-S-' in chamado_id_str
                                is_equipamento = '-E-' in chamado_id_str
                                updates_individuais = {}
                                
                                if is_servico:
                                    st.markdown("**Gatilhos de Serviço (-S-)**")
                                    link_val = chamado_row.get('Link Externo', '')
                                    novo_link = st.text_input("Link Externo", value=link_val, key=f"{form_key_ind}_link")
                                    updates_individuais['Link Externo'] = novo_link
                                    
                                    proto_val = chamado_row.get('Nº Protocolo', '')
                                    novo_protocolo = st.text_input("Nº Protocolo", value=proto_val, key=f"{form_key_ind}_proto")
                                    updates_individuais['Nº Protocolo'] = novo_protocolo
                                    
                                if is_equipamento:
                                    st.markdown("**Gatilhos de Equipamento (-E-)**")
                                    c1, c2 = st.columns(2)
                                    pedido_val = chamado_row.get('Nº Pedido', '')
                                    novo_pedido = c1.text_input("Nº Pedido", value=pedido_val, key=f"{form_key_ind}_pedido")
                                    updates_individuais['Nº Pedido'] = novo_pedido
                                    
                                    envio_val = _to_date_safe(chamado_row.get('Data Envio'))
                                    nova_data_envio = c2.date_input("Data Envio", value=envio_val, format="DD/MM/YYYY", key=f"{form_key_ind}_envio")
                                    updates_individuais['Data Envio'] = nova_data_envio
                                    
                                    obs_val = chamado_row.get('Obs. Equipamento', '')
                                    nova_obs_equip = st.text_area("Obs. Equipamento", value=obs_val, height=100, key=f"{form_key_ind}_obs_equip")
                                    updates_individuais['Obs. Equipamento'] = nova_obs_equip
                                
                                st.markdown("**Informações do Chamado**")
                                c1, c2 = st.columns(2)
                                c1.text_input("Serviço", value=chamado_row.get('Serviço', 'N/A'), disabled=True)
                                c2.text_input("Sistema", value=chamado_row.get('Sistema', 'N/A'), disabled=True)
                                
                                btn_salvar_individual = st.form_submit_button("💾 Salvar Chamado", use_container_width=True)

                            if btn_salvar_individual:
                                with st.spinner(f"Salvando chamado {chamado_id_str}..."):
                                    if utils_chamados.atualizar_chamado_db(chamado_id_interno, updates_individuais):
                                        st.success("Chamado salvo!")
                                        df_chamados_atualizado = utils_chamados.carregar_chamados_db()
                                        df_projeto_atualizado = df_chamados_atualizado[df_chamados_atualizado['ID'].isin(chamado_ids_internos_list)]
                                        
                                        if calcular_e_atualizar_status_projeto(df_projeto_atualizado, chamado_ids_internos_list):
                                            st.cache_data.clear(); st.rerun()
                                        else:
                                            st.cache_data.clear(); st.rerun()
                                    else:
                                        st.error("Falha ao salvar o chamado.")
                    
                    st.markdown("---")
                    st.markdown("##### Descrição (Total de Equipamentos do Projeto)")
                    descricao_list = []
                    for _, chamado_row_desc in df_projeto.iterrows():
                        qtd_val_numeric = pd.to_numeric(chamado_row_desc.get('Qtd.'), errors='coerce')
                        qtd_int = int(qtd_val_numeric) if pd.notna(qtd_val_numeric) else 0
                        equip_str = str(chamado_row_desc.get('Equipamento', 'N/A'))
                        descricao_list.append(f"{qtd_int:02d} - {equip_str}")
                    
                    descricao_texto = "\n".join(descricao_list)
                    st.text_area(
                        "Descrição (Total de Equipamentos do Projeto)", 
                        value=descricao_texto, 
                        height=max(50, len(descricao_list) * 25 + 25),
                        disabled=True,
                        key=f"desc_proj_{nome_agencia}_{nome_projeto}_{data_agend}",
                        label_visibility="collapsed"
                    )
                
                # Fecha o <div> do project-card
                st.markdown("</div>", unsafe_allow_html=True)

# --- Ponto de Entrada ---
tela_dados_agencia()
