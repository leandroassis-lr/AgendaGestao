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


# --- FUNÇÃO HELPER PARA LIMPAR VALORES ---
def clean_val(val, default="N/A"):
    """Converte None, NaN, etc. para 'N/A' ou o padrão definido."""
    if val is None or pd.isna(val) or str(val).lower() == "none" or str(val).lower() == "nan":
        return default
    return str(val)


# --- Tela Principal da Página ---
def tela_dados_agencia():
    
    # CSS customizado para o Card (Layout da Foto 1)
    st.markdown("""
        <style>
            .card-grid { display: grid; grid-template-columns: 2.5fr 2fr 2.5fr 2.5fr; gap: 16px; align-items: start; }
            .card-grid h5 { margin-top: 5px; margin-bottom: 0; font-size: 1.15rem; font-weight: 700; color: var(--gray-darkest); }
            .card-grid .date { font-weight: 600; font-size: 0.95rem; color: var(--gray-dark); }
            .card-grid .label { font-size: 0.85rem; color: #555; margin-bottom: 0; }
            .card-grid .value { font-size: 0.95rem; font-weight: 500; color: var(--gray-darkest); margin-bottom: 8px; }
            .card-grid .sla { font-size: 0.9rem; font-weight: 600; margin-top: 5px; }
            .card-status-badge { background-color: #B0BEC5; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 0.85em; display: inline-block; width: 100%; text-align: center; }
            .card-action-text { text-align: center; font-size: 0.9em; font-weight: 600; margin-top: 8px; color: var(--primary-dark); }
            .project-card [data-testid="stExpander"] { border: 1px solid var(--gray-border); border-radius: var(--std-radius); margin-top: 15px; }
            .project-card [data-testid="stExpander"] > summary { font-weight: 600; font-size: 0.95rem; }
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
    # Status agora é manual e editável
    status_options = ["Não Iniciado", "Em Andamento", "Concluído", "Pendencia de infra", "Pendencia de equipamento", "Pausado", "Cancelado", "Acionar técnico", "Solicitar Equipamento", "Equipamento Solicitado", "Equipamento entregue - Acionar técnico", "Equipamento entregue - Concluído"]
    
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
                
                first_row = df_projeto.iloc[0]
                chamado_ids_internos_list = df_projeto['ID'].tolist()
                
                status_val = str(first_row.get('Status', 'Não Iniciado')).strip()
                if status_val == "" or status_val.lower() == "none" or status_val.lower() == "nan":
                    status_principal_atual = "Não Iniciado"
                else:
                    status_principal_atual = status_val
                
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
                
                gestor_color = utils_chamados.get_color_for_name(nome_gestor)
                status_color = utils_chamados.get_status_color(status_principal_atual)

                st.markdown('<div class="project-card">', unsafe_allow_html=True)
                with st.container():
                    
                    col1, col2, col3, col4 = st.columns([2.5, 2.5, 2.5, 2])
                    
                    with col1:
                        st.markdown(f"**📅 {data_agend}**", unsafe_allow_html=True)
                        st.markdown(f"##### {clean_val(nome_projeto, 'Sem Projeto').upper()}", unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"**Analista:**\n{clean_val(first_row.get('Analista'))}", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size: 0.9rem; margin-top: 8px;'>{sla_text}</div>", unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown(f"**Agência:**\n{clean_val(first_row.get('Agencia_Combinada'))}", unsafe_allow_html=True)
                        gestor_html = f"<span style='color: {gestor_color}; font-weight: 500;'>{clean_val(nome_gestor)}</span>"
                        st.markdown(f"**Gestor:**\n{gestor_html}", unsafe_allow_html=True)

                    with col4:
                        st.markdown(f"""
                        <div style="background-color: {status_color}; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 0.85em; display: inline-block; width: 100%; text-align: center;">
                            {clean_val(status_principal_atual, "Não Iniciado").upper()}
                        </div>
                        """, unsafe_allow_html=True)
                        # --- Texto de Ação REMOVIDO pois o status é manual ---

                    # --- NÍVEL 3 (Expander com formulários) ---
                    expander_title = f"Ver/Editar Detalhes - ID: {first_row['ID']}"
                    with st.expander(expander_title):
                        
                        # --- INÍCIO DO NOVO FORMULÁRIO DE LOTE (NÍVEL 2) ---
                        form_key_lote = f"form_lote_edit_{first_row['ID']}"
                        
                        with st.form(key=form_key_lote):
                            st.markdown(f"**Editar todos os {len(df_projeto)} chamados deste projeto:**")
                            
                            st.markdown("<h6>Informações e Prazos</h6>", unsafe_allow_html=True)
                            c1, c2, c3, c4 = st.columns(4)
                            
                            novo_prazo = c1.text_input("Prazo", value=first_row.get('Prazo', ''), key=f"{form_key_lote}_prazo")
                            
                            status_val = first_row.get('Status', 'Não Iniciado')
                            status_idx = status_options.index(status_val) if status_val in status_options else 0
                            novo_status = c2.selectbox("STATUS", options=status_options, index=status_idx, key=f"{form_key_lote}_status")
                            
                            abertura_val = _to_date_safe(first_row.get('Abertura'))
                            if abertura_val is None: abertura_val = date.today() # Padrão
                            nova_abertura = c3.date_input("Data Abertura", value=abertura_val, format="DD/MM/YY", key=f"{form_key_lote}_abertura")
                            
                            agend_val = _to_date_safe(first_row.get('Agendamento'))
                            novo_agendamento = c4.date_input("Data Agendamento", value=agend_val, format="DD/MM/YY", key=f"{form_key_lote}_agend")

                            final_val = _to_date_safe(first_row.get('Fechamento'))
                            nova_finalizacao = c4.date_input("Data Finalização", value=final_val, format="DD/MM/YY", key=f"{form_key_lote}_final")

                            st.markdown("<h6>Detalhes do Projeto</h6>", unsafe_allow_html=True)
                            c5, c6, c7 = st.columns(3)
                            
                            proj_val = first_row.get('Projeto', '')
                            proj_idx = projeto_list.index(proj_val) if proj_val in projeto_list else 0
                            novo_projeto = c5.selectbox("Nome do projeto", options=projeto_list, index=proj_idx, key=f"{form_key_lote}_proj")
                            
                            analista_val = first_row.get('Analista', '')
                            novo_analista = c6.text_input("Analista", value=analista_val, key=f"{form_key_lote}_analista")

                            gestor_val = first_row.get('Gestor', '')
                            gestor_idx = gestor_list.index(gestor_val) if gestor_val in gestor_list else 0
                            novo_gestor = c7.selectbox("Gestor", options=gestor_list, index=gestor_idx, key=f"{form_key_lote}_gestor")

                            c8, c9, c10 = st.columns(3)
                            
                            novo_sistema = c8.text_input("Sistema", value=first_row.get('Sistema', ''), key=f"{form_key_lote}_sistema")
                            novo_servico = c9.text_input("Serviço", value=first_row.get('Serviço', ''), key=f"{form_key_lote}_servico")
                            novo_tecnico = c10.text_input("Técnico", value=first_row.get('Técnico', ''), key=f"{form_key_lote}_tec")

                            nova_descricao = st.text_area("Descrição", value=first_row.get('Descrição', ''), key=f"{form_key_lote}_desc")
                            nova_obs_pend = st.text_area("Observações e Pendencias", value=first_row.get('Observações e Pendencias', ''), key=f"{form_key_lote}_obs")

                            btn_salvar_lote = st.form_submit_button("💾 Salvar Alterações do Projeto", use_container_width=True)

                        if btn_salvar_lote:
                            updates = {
                                "Prazo": novo_prazo,
                                "Status": novo_status,
                                "Data Abertura": nova_abertura,
                                "Data Agendamento": novo_agendamento,
                                "Data Finalização": nova_finalizacao,
                                "Projeto": novo_projeto,
                                "Analista": novo_analista,
                                "Gestor": novo_gestor,
                                "Sistema": novo_sistema,
                                "Serviço": novo_servico,
                                "Técnico": novo_tecnico,
                                "Descrição": nova_descricao,
                                "Observações e Pendencias": nova_obs_pend
                            }
                            
                            with st.spinner(f"Atualizando {len(chamado_ids_internos_list)} chamados..."):
                                sucesso_count = 0
                                for chamado_id in chamado_ids_internos_list:
                                    if utils_chamados.atualizar_chamado_db(chamado_id, updates):
                                        sucesso_count += 1
                                st.success(f"{sucesso_count} de {len(chamado_ids_internos_list)} chamados foram atualizados!")
                                st.cache_data.clear(); st.rerun()
                        # --- FIM DO NOVO FORMULÁRIO DE LOTE ---

                        
                        # --- INÍCIO DA NOVA VISÃO INDIVIDUAL (READ-ONLY) ---
                        st.markdown("---")
                        st.markdown("##### 🔎 Detalhes por Chamado Individual")
                        
                        for _, chamado_row in df_projeto.iterrows():
                            st.markdown(f"**Chamado:** `{chamado_row['Nº Chamado']}`")
                            
                            c1, c2 = st.columns(2)
                            
                            # Mostra Link e Protocolo (se for Serviço)
                            if '-S-' in chamado_row['Nº Chamado']:
                                c1.text_input("Link Externo", value=chamado_row.get('Link Externo', ''), disabled=True, key=f"link_{chamado_row['ID']}")
                                c2.text_input("Nº Protocolo", value=chamado_row.get('Nº Protocolo', ''), disabled=True, key=f"proto_{chamado_row['ID']}")
                            
                            # Mostra Pedido e Data (se for Equipamento)
                            elif '-E-' in chamado_row['Nº Chamado']:
                                c1.text_input("Nº Pedido", value=chamado_row.get('Nº Pedido', ''), disabled=True, key=f"pedido_{chamado_row['ID']}")
                                data_envio_val = _to_date_safe(chamado_row.get('Data Envio'))
                                c2.date_input("Data Envio", value=data_envio_val, format="DD/MM/YY", disabled=True, key=f"envio_{chamado_row['ID']}")
                            
                            # Descrição do equipamento (individual)
                            qtd_val_numeric_ind = pd.to_numeric(chamado_row.get('Qtd.'), errors='coerce')
                            qtd_int_ind = int(qtd_val_numeric_ind) if pd.notna(qtd_val_numeric_ind) else 0
                            equip_str_ind = str(chamado_row.get('Equipamento', 'N/A'))
                            
                            st.text_area(
                                "Descrição (equipamento deste chamado)", 
                                value=f"{qtd_int_ind:02d} - {equip_str_ind}", 
                                disabled=True, height=50,
                                key=f"desc_ind_{chamado_row['ID']}"
                            )
                        # --- FIM DA NOVA VISÃO INDIVIDUAL ---
                        
                        
                        # --- Descrição Agregada (Total de Equipamentos) ---
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
