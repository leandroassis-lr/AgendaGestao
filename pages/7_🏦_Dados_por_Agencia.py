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

# --- 1. DIALOG (POP-UP) DE IMPORTAÇÃO ---
@st.dialog("Importar Novos Chamados (Excel/CSV)")
def run_importer_dialog():
    st.info(f"""
            Arraste seu arquivo Excel de chamados (formato `.xlsx` ou `.csv` com `;`) aqui.
            O sistema espera que a **primeira linha** contenha os cabeçalhos.
            As colunas necessárias (A, B, C, D, J, K, L, M, N, O, Q, T) serão lidas automaticamente.
            Se um `Chamado` (Coluna A) já existir, ele será **atualizado**.
    """)
    uploaded_file = st.file_uploader("Selecione o arquivo Excel/CSV de chamados", type=["xlsx", "xls", "csv"], key="chamado_uploader_dialog")

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_raw = pd.read_csv(uploaded_file, sep=';', header=0, encoding='latin-1', keep_default_na=False, dtype=str) 
            else:
                df_raw = pd.read_excel(uploaded_file, header=0, keep_default_na=False, dtype=str) 

            df_raw.dropna(how='all', inplace=True)
            if df_raw.empty: 
                st.error("Erro: O arquivo está vazio.")
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
                st.success("Arquivo lido. Pré-visualização dos dados extraídos:")
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
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")

    if st.session_state.get("importer_done", False):
        st.session_state.importer_done = False 
        st.rerun()

    if st.button("Cancelar"):
        st.rerun()


# --- Tela Principal da Página ---
def tela_dados_agencia():
    
    # --- TÍTULO E BOTÃO DE IMPORTAR (NOVO LAYOUT) ---
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
    status_options = ["Não iniciada", "Em andamento", "Concluído", "Pendencia de infra", "Pendencia de equipamento", "Pausado", "Cancelado"]
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
        status_fechamento = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado']
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
        # Garante que 'Agendamento' seja datetime para o cálculo da data mínima
        df_chamados_filtrado['Agendamento'] = pd.to_datetime(df_chamados_filtrado['Agendamento'], errors='coerce')
        df_chamados_filtrado['Agendamento_str'] = df_chamados_filtrado['Agendamento'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
        
        if 'Analista' not in df_chamados_filtrado.columns: df_chamados_filtrado['Analista'] = 'N/A'
        if 'Técnico' not in df_chamados_filtrado.columns: df_chamados_filtrado['Técnico'] = 'N/A'
        if 'Prioridade' not in df_chamados_filtrado.columns: df_chamados_filtrado['Prioridade'] = 'Média'
        
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
        
        # --- NOVO: Cálculo da Data Mais Próxima ---
        hoje = pd.Timestamp.now().normalize()
        proximas_datas = df_agencia[df_agencia['Agendamento'] >= hoje]['Agendamento']
        
        header_agencia = f"🏦 {nome_agencia} ({len(df_agencia)} chamados)"
        if not proximas_datas.empty:
            prox_data_str = proximas_datas.min().strftime('%d/%m/%Y')
            header_agencia = f"🏦 {nome_agencia} ({len(df_agencia)} chamados) | 🗓️ Próximo Ag: {prox_data_str}"
        # --- FIM DA MUDANÇA ---

        if agencia_selecionada == "Todas":
            expander_agencia = st.expander(header_agencia) # Usa o novo header
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
                
                nome_projeto_str = str(nome_projeto).upper()
                nome_gestor_str = html.escape(str(nome_gestor))
                
                header_projeto = f"Projeto: {nome_projeto_str} | Gestor: {nome_gestor_str} | Agendamento: {data_agend}"
                
                with st.expander(header_projeto):
                    
                    first_row = df_projeto.iloc[0]
                    chamado_ids_internos_list = df_projeto['ID'].tolist()
                    form_key = f"form_bulk_edit_{first_row['ID']}"
                    
                    with st.form(key=form_key):
                        
                        # --- NOVO: Botão Salvar no Topo ---
                        c_title, c_btn = st.columns([3, 1])
                        with c_title:
                            st.markdown(f"**Editar todos os {len(df_projeto)} chamados deste projeto:**")
                        with c_btn:
                            btn_salvar_bulk = st.form_submit_button("💾 Salvar Lote", use_container_width=True)
                        # --- FIM DA MUDANÇA ---
                        
                        st.markdown("<h6>Informações e Prazos</h6>", unsafe_allow_html=True)
                        c1, c2, c3, c4 = st.columns(4)
                        
                        status_val = first_row.get('Status', 'Não iniciada')
                        status_idx = status_options.index(status_val) if status_val in status_options else 0
                        novo_status = c1.selectbox("Status", options=status_options, index=status_idx, key=f"{form_key}_status")
                        
                        abertura_val = _to_date_safe(first_row.get('Abertura'))
                        nova_abertura = c2.date_input("Data Abertura", value=abertura_val, format="DD/MM/YYYY", key=f"{form_key}_abertura")
                        
                        agend_val = _to_date_safe(first_row.get('Agendamento'))
                        novo_agendamento = c3.date_input("Agendamento", value=agend_val, format="DD/MM/YYYY", key=f"{form_key}_agend")
                        
                        final_val = _to_date_safe(first_row.get('Fechamento'))
                        nova_finalizacao = c4.date_input("Data Finalização", value=final_val, format="DD/MM/YYYY", key=f"{form_key}_final")

                        st.markdown("<h6>Detalhes do Projeto</h6>", unsafe_allow_html=True)
                        c1, c2, c3, c4 = st.columns(4)
                        
                        proj_val = first_row.get('Projeto', '')
                        proj_idx = projeto_list.index(proj_val) if proj_val in projeto_list else 0
                        novo_projeto = c1.selectbox("Projeto", options=projeto_list, index=proj_idx, key=f"{form_key}_proj")
                        
                        # --- NOVO: Campo Analista Editável ---
                        analista_val = first_row.get('Analista', '')
                        novo_analista = c2.text_input("Analista", value=analista_val, key=f"{form_key}_analista")
                        # --- FIM DA MUDANÇA ---

                        gestor_val = first_row.get('Gestor', '')
                        gestor_idx = gestor_list.index(gestor_val) if gestor_val in gestor_list else 0
                        novo_gestor = c3.selectbox("Gestor", options=gestor_list, index=gestor_idx, key=f"{form_key}_gestor")
                        
                        prior_val = first_row.get('Prioridade', 'Média')
                        prior_idx = prioridade_options.index(prior_val) if prior_val in prioridade_options else 1
                        nova_prioridade = c4.selectbox("Prioridade", options=prioridade_options, index=prior_idx, key=f"{form_key}_prior")

                        # --- Layout da Linha 3 Ajustado (Botão saiu) ---
                        c1, c2 = st.columns(2)
                        
                        ag_val = first_row.get('Agencia_Combinada', '')
                        ag_id_num = str(ag_val).split(" - ")[0].replace("AG ", "").lstrip('0')
                        ag_idx = agencia_list_no_todas.index(ag_val) if ag_val in agencia_list_no_todas else 0
                        nova_agencia_selecionada = c1.selectbox("Agência", options=agencia_list_no_todas, index=ag_idx, key=f"{form_key}_ag")
                        nova_agencia_id = str(nova_agencia_selecionada).split(" - ")[0].replace("AG ", "").lstrip('0')
                        
                        # --- NOVO: Campo Técnico Editável ---
                        tec_val = first_row.get('Técnico', '')
                        novo_tecnico = c2.text_input("Técnico", value=tec_val, key=f"{form_key}_tec")
                        # --- FIM DA MUDANÇA ---

                    if btn_salvar_bulk:
                        updates = {
                            "Status": novo_status, "Data Abertura": nova_abertura, "Data Agendamento": novo_agendamento,
                            "Data Finalização": nova_finalizacao, "Projeto": novo_projeto, "Analista": novo_analista,
                            "Gestor": novo_gestor, "Prioridade": nova_prioridade, "Agência": nova_agencia_id,
                            "Técnico": novo_tecnico
                        }
                        
                        with st.spinner(f"Atualizando {len(chamado_ids_internos_list)} chamados..."):
                            sucesso_count = 0
                            for chamado_id in chamado_ids_internos_list:
                                if utils_chamados.atualizar_chamado_db(chamado_id, updates):
                                    sucesso_count += 1
                            
                            st.cache_data.clear()
                            st.success(f"{sucesso_count} de {len(chamado_ids_internos_list)} chamados foram atualizados!")
                            st.rerun()
                    
                    # --- NÍVEL 3 (Simplificado) ---
                    st.markdown("---")
                    st.markdown("##### 🔎 Detalhes por Chamado Individual")

                    for _, chamado_row in df_projeto.iterrows():
                        chamado_id_interno = chamado_row['ID']
                        chamado_id_str = chamado_row['Nº Chamado']
                        
                        with st.expander(f"▶️ Chamado: {chamado_id_str}"):
                            c1, c2 = st.columns(2)
                            c1.text_input("Serviço", value=chamado_row.get('Serviço', 'N/A'), disabled=True, key=f"serv_{chamado_id_interno}")
                            c2.text_input("Sistema", value=chamado_row.get('Sistema', 'N/A'), disabled=True, key=f"sist_{chamado_id_interno}")

                            qtd_val_numeric_ind = pd.to_numeric(chamado_row.get('Qtd.'), errors='coerce')
                            qtd_int_ind = int(qtd_val_numeric_ind) if pd.notna(qtd_val_numeric_ind) else 0
                            equip_str_ind = str(chamado_row.get('Equipamento', 'N/A'))
                            
                            st.text_area(
                                "Descrição (equipamento deste chamado)", 
                                value=f"{qtd_int_ind:02d} - {equip_str_ind}", 
                                disabled=True, height=50,
                                key=f"desc_ind_{chamado_id_interno}"
                            )
                    
                    # --- DESCRIÇÃO AGREGADA (Final) ---
                    st.markdown("---")
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
                        key=f"desc_proj_{nome_agencia}_{nome_projeto}_{data_agend}"
                    )

# --- Ponto de Entrada ---
tela_dados_agencia()
