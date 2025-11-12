import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, datetime
import re 
import html 
import io

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
        # Correção para o 'orig_name' funcionar
        col_indices = list(col_map.keys())
        col_nomes_originais = {idx: colunas_originais[idx] for idx in col_indices if idx < len(colunas_originais)}
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
                st.dataframe(df_para_salvar.head(), width='stretch') # CORRIGIDO
                
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


# --- FUNÇÃO "CÉREBRO" DE STATUS (v11.1) ---
def calcular_e_atualizar_status_projeto(df_projeto, ids_para_atualizar):
    
    status_atual = str(df_projeto.iloc[0].get('Status', 'Não Iniciado')).strip()
    status_manual_list = ["Pendência de Infra", "Pendência de Equipamento", "Pausado", "Cancelado", "Finalizado"]
    if status_atual in status_manual_list:
        sub_status_atual_val = df_projeto.iloc[0].get('Sub-Status')
        sub_status_atual = "" if pd.isna(sub_status_atual_val) else str(sub_status_atual_val).strip()
        
        if sub_status_atual != "":
            updates = {"Sub-Status": None}
            for chamado_id in ids_para_atualizar:
                utils_chamados.atualizar_chamado_db(chamado_id, updates)
            return True 
        return False 
    
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
    protocolo_presente = check_col_present(df_projeto, 'Nº Protocolo')
    pedido_presente = check_col_present(df_projeto, 'Nº Pedido')
    envio_presente = check_date_present(df_projeto, 'Data Envio')
    tecnico_presente = check_col_present(df_projeto, 'Técnico')
    
    novo_status = "Não Iniciado"
    novo_sub_status = ""

    # --- Cenário 1: Só Serviço (S-Only) ---
    if has_S and not has_E:
        if protocolo_presente:
            novo_status = "Concluído"
            novo_sub_status = "Enviar Book"
        elif tecnico_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Enviar Status Cliente"
        elif link_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Acionar técnico"
        else:
            novo_status = "Não Iniciado"
            novo_sub_status = "Pendente Link"

    # --- Cenário 2: Misto (S e E) ---
    elif has_S and has_E:
        if protocolo_presente:
            novo_status = "Concluído"
            novo_sub_status = "Enviar Book"
        elif tecnico_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Enviar Status Cliente"
        elif envio_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Equipamento entregue - Acionar técnico"
        elif pedido_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Equipamento Solicitado"
        elif link_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Solicitar Equipamento"
        else:
            novo_status = "Não Iniciado"
            novo_sub_status = "Pendente Link"

    # --- Cenário 3: Só Equipamento (E-Only) ---
    elif not has_S and has_E:
        if envio_presente:
            novo_status = "Concluído"
            novo_sub_status = "Equipamento entregue"
        elif pedido_presente:
            novo_status = "Em Andamento"
            novo_sub_status = "Equipamento Solicitado"
        else:
            novo_status = "Não Iniciado"
            novo_sub_status = "Solicitar Equipamento"
    
    else: 
        novo_status = "Não Iniciado"
        novo_sub_status = "Verificar Chamados"

    sub_status_atual_val = df_projeto.iloc[0].get('Sub-Status')
    sub_status_atual = "" if pd.isna(sub_status_atual_val) else str(sub_status_atual_val).strip()
    
    if status_atual != novo_status or sub_status_atual != novo_sub_status:
        st.info(f"Status do projeto mudou de '{status_atual} | {sub_status_atual}' para '{novo_status} | {novo_sub_status}'")
        updates = {"Status": novo_status, "Sub-Status": novo_sub_status}
        for chamado_id in ids_para_atualizar:
            utils_chamados.atualizar_chamado_db(chamado_id, updates)
        return True
    return False

# --- FUNÇÃO HELPER PARA LIMPAR VALORES ---
def clean_val(val, default="N/A"):
    """Converte None, NaN, etc. para 'N/A' ou o padrão definido."""
    if val is None or pd.isna(val) or str(val).lower() == "none" or str(val).lower() == "nan":
        return default
    return str(val)

# --- Tela Principal da Página ---
def tela_dados_agencia():
    
    # CSS customizado
    st.markdown("""
        <style>
            .card-grid { display: grid; grid-template-columns: 2.5fr 2fr 2.5fr 2.5fr; gap: 16px; align-items: start; }
            .card-grid h5 { margin-top: 5px; margin-bottom: 0; font-size: 1.15rem; font-weight: 700; color: var(--gray-darkest); }
            .card-grid .date { font-weight: 600; font-size: 0.95rem; color: var(--gray-dark); }
            .card-grid .label { font-size: 0.85rem; color: #555; margin-bottom: 0; }
            .card-grid .value { font-size: 0.95rem; font-weight: 500; color: var(--gray-darkest); margin-bottom: 8px; }
            .card-grid .sla { font-size: 0.9rem; font-weight: 600; margin-top: 5px; }
            .card-status-badge { background-color: #B0BEC5; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 0.85em; display: inline-block; width: 100%; text-align: center; }
            .card-action-text { text-align: center; font-size: 0.9em; font-weight: 600; margin-top: 8px; color: var(--primary-dark); background-color: #F0F2F5; padding: 4px; border-radius: 5px; } 
            .agency-card-grid { display: grid; grid-template-columns: 1.5fr 3fr 2fr 1.5fr; gap: 16px; align-items: center; }
            .agency-card-grid .tag { font-weight: bold; }
            .agency-card-grid .agency-name { font-size: 1.15rem; font-weight: bold; }
            .agency-card-grid .date-info { font-size: 1rem; }
            .agency-card-grid .count { font-size: 1rem; font-weight: bold; text-align: right; }
            .project-card [data-testid="stExpander"] { border: 1px solid var(--gray-border); border-radius: var(--std-radius); margin-top: 15px; }
            .project-card [data-testid="stExpander"] > summary { font-weight: 600; font-size: 0.95rem; }
            [data-testid="stExpander"] [data-testid="stForm"] { border: none; box-shadow: none; padding: 0; }
        </style>
    """, unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 1])
    with c1:
        # --- INÍCIO DA CORREÇÃO DO SYNTAXERROR ---
        st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
        # --- FIM DA CORREÇÃO DO SYNTAXERROR ---
    with c2:
        if st.button("📥 Importar Novos Chamados", width='stretch'): # CORRIGIDO
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
    status_manual_options = [
        "(Status Automático)", "Pendência de Infra", "Pendência de Equipamento", 
        "Pausado", "Cancelado", "Finalizado"
    ]
    
    def get_options_list(df, column_name):
        # Pega valores únicos, converte para string, remove Nulos/NaN, ordena e adiciona "Todos"
        options = sorted(df[column_name].dropna().astype(str).unique())
        return ["Todos"] + options

    agencia_list = get_options_list(df_chamados_raw, 'Agencia_Combinada')
    analista_list = get_options_list(df_chamados_raw, 'Analista')
    projeto_list_filtro = get_options_list(df_chamados_raw, 'Projeto') # Lista para o filtro
    gestor_list_filtro = get_options_list(df_chamados_raw, 'Gestor') # Lista para o filtro
    sistema_list = get_options_list(df_chamados_raw, 'Sistema') # <-- NOVO FILTRO
    status_list = get_options_list(df_chamados_raw, 'Status')

    # Listas para os formulários de edição (sem o "Todos")
    projeto_list_form = sorted([str(p) for p in df_chamados_raw['Projeto'].dropna().unique() if p])
    gestor_list_form = sorted([str(g) for g in df_chamados_raw['Gestor'].dropna().unique() if g])
        
    # --- 5. FILTROS E BOTÃO DE EXPORTAÇÃO ---
    
    # A inicialização do state do modal deve vir ANTES do expander
    if "show_export_popup" not in st.session_state:
        st.session_state.show_export_popup = False
    
    with st.expander("🔎 Filtros, Busca e Exportação", expanded=True):
        st.markdown("#### 🔎 Busca Total")
        busca_total = st.text_input(
            "Busca Total", 
            placeholder="Buscar por Nº Chamado, Equipamento, Descrição, Obs., etc...", 
            label_visibility="collapsed", 
            key="filtro_busca_total"
        )
        
        st.markdown("#### 🎛️ Filtros Específicos")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_agencia = st.selectbox("Agência:", options=agencia_list, key="filtro_agencia")
        with col2:
            filtro_analista = st.selectbox("Analista:", options=analista_list, key="filtro_analista")
        with col3:
            filtro_projeto = st.selectbox("Projeto:", options=projeto_list_filtro, key="filtro_projeto")
    
        col4, col5, col6 = st.columns(3)
        with col4:
            filtro_gestor = st.selectbox("Gestor:", options=gestor_list_filtro, key="filtro_gestor")
        with col5:
            filtro_status = st.selectbox("Status:", options=status_list, key="filtro_status")
        with col6:
            filtro_sistema = st.selectbox("Sistema:", options=sistema_list, key="filtro_sistema")
        
        col7, col8 = st.columns(2)
        with col7:
            filtro_data_inicio = st.date_input("Agendamento (De):", value=None, format="DD/MM/YYYY", key="filtro_data_inicio")
        with col8:
            filtro_data_fim = st.date_input("Agendamento (Até):", value=None, format="DD/MM/YYYY", key="filtro_data_fim")
        
        # --- BOTÃO DE TRIGGER (ESTAVA FALTANDO) ---
        st.divider() 
        st.markdown("#### 📤 Exportação")
        
        if st.button("⬇️ Exportar Dados Filtrados", width='stretch'):
            st.session_state.show_export_popup = True
        # --- FIM DA SEÇÃO MOVIDA ---
    
    # Esse divider fica FORA do expander
    st.divider()
    
    # --- 6. Filtrar DataFrame Principal (COMPLETO) ---
    # (ESSA SEÇÃO PRECISA VIR ANTES DO MODAL)
    df_filtrado = df_chamados_raw.copy()
    
    # --- Filtros específicos (Dropdowns) ---
    if filtro_agencia != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Agencia_Combinada'] == filtro_agencia]
    if filtro_analista != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]
    if filtro_projeto != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Projeto'] == filtro_projeto]
    if filtro_gestor != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Gestor'] == filtro_gestor]
    if filtro_status != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Status'] == filtro_status]
    if filtro_sistema != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Sistema'] == filtro_sistema]
    
    # --- Filtro de Data ---
    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    if filtro_data_inicio:
        df_filtrado = df_filtrado[df_filtrado['Agendamento'] >= pd.to_datetime(filtro_data_inicio)]
    if filtro_data_fim:
        df_filtrado = df_filtrado[df_filtrado['Agendamento'] <= pd.to_datetime(filtro_data_fim).replace(hour=23, minute=59)]
    
    # --- Filtro de Busca Total ---
    if busca_total:
        termo = busca_total.lower()
        cols_to_search = [
            'Nº Chamado', 'Projeto', 'Gestor', 'Analista', 'Sistema', 'Serviço',
            'Equipamento', 'Descrição', 'Observações e Pendencias', 'Obs. Equipamento',
            'Link Externo', 'Nº Protocolo', 'Nº Pedido', 'Agencia_Combinada'
        ]
        masks = []
        for col in cols_to_search:
            if col in df_filtrado.columns:
                masks.append(df_filtrado[col].astype(str).str.lower().str.contains(termo, na=False))
        if masks:
            combined_mask = pd.concat(masks, axis=1).any(axis=1)
            df_filtrado = df_filtrado[combined_mask]
    # --- FIM DA SEÇÃO 6 ---
    
    # --- 6b. LÓGICA DO "MODAL" DE EXPORTAÇÃO ---
    
    if st.session_state.show_export_popup:
    
        # Usando um expander para simular o modal (já que st.modal não funcionou)
        with st.expander("⬇️ Download do Excel", expanded=True):
                
            # --- Criação do buffer do arquivo Excel ---
            # Agora o df_filtrado existe e está correto
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_filtrado.to_excel(writer, index=False, sheet_name="Dados Filtrados")
            buffer.seek(0)
    
            # --- Botão de download principal ---
            st.download_button(
                label="📥 Baixar Arquivo Excel",
                data=buffer,
                file_name="dados_filtrados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
            # --- Botão de fechamento do "popup" ---
            if st.button("Fechar", use_container_width=True):
                st.session_state.show_export_popup = False
                st.rerun()
         
    # --- 7. Painel de KPIs ---
    total_chamados = len(df_filtrado)
    status_fechamento_kpi = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado', 'equipamento entregue - concluído', 'finalizado']
    if not df_filtrado.empty:
        chamados_abertos_count = len(df_filtrado[~df_filtrado['Status'].astype(str).str.lower().isin(status_fechamento_kpi)])
    else:
        chamados_abertos_count = 0
    
    st.markdown(f"### 📊 Resumo da Visão Filtrada")
    cols_kpi = st.columns(2) 
    cols_kpi[0].metric("Total de Chamados", total_chamados)
    cols_kpi[1].metric("Chamados Abertos", chamados_abertos_count)
    st.divider()
    
    # --- 8. NOVA VISÃO HIERÁRQUICA (Agência -> Projeto -> Chamados) ---
    st.markdown("#### 📋 Visão por Projetos e Chamados")
    
    if df_filtrado.empty:
        st.info("Nenhum chamado encontrado para os filtros selecionados.")
        st.stop() 

    # Prepara o DataFrame para agrupamento
    try:
        df_filtrado['Agendamento_str'] = df_filtrado['Agendamento'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
        
        chave_agencia = 'Agencia_Combinada'
        chave_projeto = ['Projeto', 'Gestor', 'Agendamento_str']

    except Exception as e:
        st.error(f"Erro ao processar datas para agrupamento: {e}")
        st.stop()

    
    # --- NÍVEL 1: Loop pelas Agências ---
    agencias_agrupadas = df_filtrado.groupby(chave_agencia)
    
    if not agencias_agrupadas.groups:
        st.info("Nenhum projeto agrupado encontrado para os filtros selecionados.")
    else:
        for nome_agencia, df_agencia in agencias_agrupadas:
            
            status_fechamento_proj = ['concluído', 'cancelado', 'equipamento entregue - concluído', 'finalizado']
            df_agencia_aberta = df_agencia[~df_agencia['Status'].astype(str).str.lower().isin(status_fechamento_proj)]
            
            hoje_ts = pd.Timestamp.now().normalize()
            datas_abertas = pd.to_datetime(df_agencia_aberta['Agendamento'], errors='coerce')
            
            tag_html = ""
            urgency_text = ""
            
            if datas_abertas.empty:
                tag_html = "🟦"
                urgency_text = "Sem Agendamentos"
            else:
                earliest_date = datas_abertas.min()
                if earliest_date < hoje_ts:
                    tag_html = "<span style='color: var(--red-alert); font-weight: bold;'>🟥 ATRASADO</span>"
                    urgency_text = f"Urgente: {earliest_date.strftime('%d/%m/%Y')}"
                elif earliest_date == hoje_ts:
                    tag_html = "<span style='color: #FFA726; font-weight: bold;'>🟧 PARA HOJE</span>"
                    urgency_text = f"📅 {earliest_date.strftime('%d/%m/%Y')}"
                else:
                    tag_html = "🟦"
                    urgency_text = f"📅 {earliest_date.strftime('%d/%m/%Y')}"

            num_projetos = len(df_agencia.groupby(chave_projeto))
            
            st.markdown('<div class="project-card">', unsafe_allow_html=True)
            with st.container():
                # Card Nível 1 (Agência)
                with st.container():
                    col1, col2, col3, col4 = st.columns([1.5, 3, 2, 1.5])
                    with col1:
                        st.markdown(tag_html, unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"<span style='font-size: 1.15rem; font-weight: bold;'>{nome_agencia}</span>", unsafe_allow_html=True)
                    with col3:
                        st.markdown(urgency_text, unsafe_allow_html=True)
                    with col4:
                        proj_s = "Projetos" if num_projetos > 1 else "Projeto"
                        st.markdown(f"**{num_projetos} {proj_s}**")

                # Expander para MOSTRAR os projetos
                with st.expander("Ver Projetos desta Agência"):
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
                        
                        status_principal_atual = clean_val(first_row.get('Status'), default="Não Iniciado")
                        sub_status_atual = clean_val(first_row.get('Sub-Status'), default="")
                        
                        sla_text = ""
                        try:
                            agendamento_date = pd.to_datetime(data_agend, format='%d/%m/%Y')
                            dias_restantes = (agendamento_date - hoje_ts).days
                            if dias_restantes < 0:
                                sla_text = f"<span style='color: var(--red-alert); font-weight: bold;'>SLA: {dias_restantes}d (Atrasado)</span>"
                            else:
                                sla_text = f"<span style='color: var(--primary-color);'>SLA: {dias_restantes}d restantes</span>"
                        except Exception:
                            sla_text = "<span style='color: #888;'>SLA: N/D</span>"
                        
                        gestor_color = utils_chamados.get_color_for_name(nome_gestor)
                        status_color = utils_chamados.get_status_color(status_principal_atual)

                        # --- Nível 2: Card de Projeto ---
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
                                status_html = html.escape(status_principal_atual.upper())
                                st.markdown(f"""
                                <div class="card-status-badge" style="background-color: {status_color};">
                                    {status_html}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                if sub_status_atual != "":
                                    st.markdown(f"""
                                    <div class="card-action-text">
                                        {sub_status_atual}
                                    </div>
                                    """, unsafe_allow_html=True)

                            # --- NÍVEL 3 (Expander com formulários) ---
                            expander_title = f"Ver/Editar Detalhes - ID: {first_row['ID']}"
                            with st.expander(expander_title):
                                
                                # --- Formulário de Lote (Nível 2) ---
                                form_key_lote = f"form_lote_edit_{first_row['ID']}"
                                
                                with st.form(key=form_key_lote):
                                    st.markdown(f"**Editar todos os {len(df_projeto)} chamados deste projeto:**")
                                    st.markdown("<h6>Informações e Prazos</h6>", unsafe_allow_html=True)
                                    
                                    c1, c2 = st.columns(2)
                                    novo_prazo = c1.text_input("Prazo", value=first_row.get('Prazo', ''), key=f"{form_key_lote}_prazo")
                                    
                                    status_manual_atual = status_principal_atual if status_principal_atual in status_manual_options else "(Status Automático)"
                                    status_idx = status_manual_options.index(status_manual_atual)
                                    novo_status_manual = c2.selectbox("Forçar Status Manual", options=status_manual_options, index=status_idx, key=f"{form_key_lote}_status")
                                    
                                    c3, c4, c5 = st.columns(3)
                                    abertura_val = _to_date_safe(first_row.get('Abertura'))
                                    if abertura_val is None: abertura_val = date.today() 
                                    nova_abertura = c3.date_input("Data Abertura", value=abertura_val, format="DD/MM/YYYY", key=f"{form_key_lote}_abertura")
                                    
                                    agend_val = _to_date_safe(first_row.get('Agendamento'))
                                    novo_agendamento = c4.date_input("Data Agendamento", value=agend_val, format="DD/MM/YYYY", key=f"{form_key_lote}_agend")

                                    final_val = _to_date_safe(first_row.get('Fechamento'))
                                    nova_finalizacao = c5.date_input("Data Finalização", value=final_val, format="DD/MM/YYYY", key=f"{form_key_lote}_final")

                                    st.markdown("<h6>Detalhes do Projeto</h6>", unsafe_allow_html=True)
                                    c6, c7, c8 = st.columns(3)
                                    
                                    proj_val = first_row.get('Projeto', '')
                                    proj_idx = projeto_list_form.index(proj_val) if proj_val in projeto_list_form else 0
                                    novo_projeto = c6.selectbox("Nome do projeto", options=projeto_list_form, index=proj_idx, key=f"{form_key_lote}_proj")
                                    
                                    analista_val = first_row.get('Analista', '')
                                    novo_analista = c7.text_input("Analista", value=analista_val, key=f"{form_key_lote}_analista")

                                    gestor_val = first_row.get('Gestor', '')
                                    gestor_idx = gestor_list_form.index(gestor_val) if gestor_val in gestor_list_form else 0
                                    novo_gestor = c8.selectbox("Gestor", options=gestor_list_form, index=gestor_idx, key=f"{form_key_lote}_gestor")

                                    c9, c10, c11 = st.columns(3)
                                    
                                    novo_sistema = c9.text_input("Sistema", value=first_row.get('Sistema', ''), key=f"{form_key_lote}_sistema")
                                    novo_servico = c10.text_input("Serviço", value=first_row.get('Serviço', ''), key=f"{form_key_lote}_servico")
                                    novo_tecnico = c11.text_input("Técnico", value=first_row.get('Técnico', ''), key=f"{form_key_lote}_tec")

                                    nova_descricao = st.text_area("Descrição", value=first_row.get('Descrição', ''), key=f"{form_key_lote}_desc")
                                    nova_obs_pend = st.text_area("Observações e Pendencias", value=first_row.get('Observações e Pendencias', ''), key=f"{form_key_lote}_obs")

                                    btn_salvar_lote = st.form_submit_button("💾 Salvar Alterações do Projeto", width='stretch')

                                if btn_salvar_lote:
                                    updates = {
                                        "Prazo": novo_prazo, "Data Abertura": nova_abertura,
                                        "Data Agendamento": novo_agendamento, "Data Finalização": nova_finalizacao,
                                        "Projeto": novo_projeto, "Analista": novo_analista, "Gestor": novo_gestor,
                                        "Sistema": novo_sistema, "Serviço": novo_servico, "Técnico": novo_tecnico,
                                        "Descrição": nova_descricao, "Observações e Pendencias": nova_obs_pend
                                    }
                                    
                                    status_foi_mudado = False
                                    if novo_status_manual == "Finalizado":
                                        if nova_finalizacao is None:
                                            st.error("Erro: Para 'Finalizado', a Data de Finalização é obrigatória.")
                                            st.stop()
                                        else:
                                            updates['Status'] = 'Finalizado'
                                            updates['Sub-Status'] = None
                                            status_foi_mudado = True
                                    
                                    elif novo_status_manual != "(Status Automático)":
                                        updates['Status'] = novo_status_manual
                                        updates['Sub-Status'] = None 
                                        status_foi_mudado = True
                                    
                                    elif novo_status_manual == "(Status Automático)":
                                        status_foi_mudado = True 

                                    with st.spinner(f"Atualizando {len(chamado_ids_internos_list)} chamados..."):
                                        sucesso_count = 0
                                        for chamado_id in chamado_ids_internos_list:
                                            if utils_chamados.atualizar_chamado_db(chamado_id, updates):
                                                sucesso_count += 1
                                        st.success(f"{sucesso_count} de {len(chamado_ids_internos_list)} chamados foram atualizados!")
                                        
                                        if status_foi_mudado:
                                            df_chamados_atualizado = utils_chamados.carregar_chamados_db()
                                            df_projeto_atualizado = df_chamados_atualizado[df_chamados_atualizado['ID'].isin(chamado_ids_internos_list)]
                                            calcular_e_atualizar_status_projeto(df_projeto_atualizado, chamado_ids_internos_list)

                                        st.cache_data.clear(); st.rerun()
                                
                                
                                # --- Nível 3: Edição Individual (Híbrido) ---
                                st.markdown("---")
                                st.markdown("##### 🔎 Detalhes por Chamado Individual (Gatilhos)")
                                
                                for _, chamado_row in df_projeto.iterrows():
                                    with st.expander(f"▶️ Chamado: {chamado_row['Nº Chamado']}"):
                                        
                                        form_key_ind = f"form_ind_edit_{chamado_row['ID']}"
                                        with st.form(key=form_key_ind):
                                            
                                            is_servico = '-S-' in chamado_row['Nº Chamado']
                                            is_equipamento = '-E-' in chamado_row['Nº Chamado']
                                            updates_individuais = {}
                                            
                                            if is_servico:
                                                st.markdown("**Gatilhos de Serviço (-S-)**")
                                                c1, c2 = st.columns(2)
                                                link_val = chamado_row.get('Link Externo', '')
                                                novo_link = c1.text_input("Link Externo", value=link_val, key=f"link_{chamado_row['ID']}")
                                                updates_individuais['Link Externo'] = novo_link
                                                
                                                proto_val = chamado_row.get('Nº Protocolo', '')
                                                novo_protocolo = c2.text_input("Nº Protocolo", value=proto_val, key=f"proto_{chamado_row['ID']}")
                                                updates_individuais['Nº Protocolo'] = novo_protocolo
                                            
                                            if is_equipamento:
                                                st.markdown("**Gatilhos de Equipamento (-E-)**")
                                                c1, c2 = st.columns(2)
                                                pedido_val = chamado_row.get('Nº Pedido', '')
                                                novo_pedido = c1.text_input("Nº Pedido", value=pedido_val, key=f"pedido_{chamado_row['ID']}")
                                                updates_individuais['Nº Pedido'] = novo_pedido
                                                
                                                envio_val = _to_date_safe(chamado_row.get('Data Envio'))
                                                nova_data_envio = c2.date_input("Data Envio", value=envio_val, format="DD/MM/YYYY", key=f"envio_{chamado_row['ID']}")
                                                updates_individuais['Data Envio'] = nova_data_envio
                                                
                                                obs_val = chamado_row.get('Obs. Equipamento', '')
                                                nova_obs_equip = st.text_area("Obs. Equipamento", value=obs_val, height=100, key=f"obs_equip_{chamado_row['ID']}")
                                                updates_individuais['Obs. Equipamento'] = nova_obs_equip

                                            qtd_val_numeric_ind = pd.to_numeric(chamado_row.get('Qtd.'), errors='coerce')
                                            qtd_int_ind = int(qtd_val_numeric_ind) if pd.notna(qtd_val_numeric_ind) else 0
                                            equip_str_ind = str(chamado_row.get('Equipamento', 'N/A'))
                                            st.text_area(
                                                "Descrição (equipamento deste chamado)", 
                                                value=f"{qtd_int_ind:02d} - {equip_str_ind}", 
                                                disabled=True, height=50,
                                                key=f"desc_ind_{chamado_row['ID']}"
                                            )
                                            
                                            btn_salvar_individual = st.form_submit_button("💾 Salvar Gatilho Individual", width='stretch')

                                        if btn_salvar_individual:
                                            with st.spinner(f"Salvando chamado {chamado_row['Nº Chamado']}..."):
                                                if utils_chamados.atualizar_chamado_db(chamado_row['ID'], updates_individuais):
                                                    st.success("Chamado salvo!")
                                                    
                                                    df_chamados_atualizado = utils_chamados.carregar_chamados_db()
                                                    df_projeto_atualizado = df_chamados_atualizado[df_chamados_atualizado['ID'].isin(chamado_ids_internos_list)]
                                                    calcular_e_atualizar_status_projeto(df_projeto_atualizado, chamado_ids_internos_list)
                                                    
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
                        
                        # Fecha o <div> do project-card (Nível 2)
                        st.markdown("</div>", unsafe_allow_html=True)
            
            # Fecha o <div> do agency-card (Nível 1)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True) # Adiciona um espaço entre as agências
    
    # --- FIM DA CORREÇÃO DO SYNTAXERROR (else alinhado) ---
    # else: # <--- O 'else:' STRAY QUE CAUSOU O ERRO FOI REMOVIDO DAQUI
    #     st.info("Nenhum projeto encontrado para os filtros selecionados.")


# --- Ponto de Entrada ---
tela_dados_agencia()













