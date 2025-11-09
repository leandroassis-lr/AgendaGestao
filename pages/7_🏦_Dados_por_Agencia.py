import streamlit as st
import pandas as pd
import utils 
from datetime import date, datetime
import re 
import html 

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() # Tenta carregar o CSS
except:
    pass 

# --- Controle Principal de Login (Independente do app.py) ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()
    
# Função Helper para converter datas (evita erros)
def _to_date_safe(val):
    if val is None or pd.isna(val): return None
    if isinstance(val, date) and not isinstance(val, datetime): return val
    try:
        ts = pd.to_datetime(val, errors='coerce')
        if pd.isna(ts): return None
        return ts.date()
    except Exception: return None

# --- Funções Helper da Página ---
def extrair_e_mapear_colunas(df, col_map):
    """ Extrai e renomeia colunas com base em índices. """
    df_extraido = pd.DataFrame()
    colunas_originais = df.columns.tolist()
    
    if len(colunas_originais) < 20: 
        st.error(f"Erro: O arquivo carregado parece ter apenas {len(colunas_originais)} colunas. O formato esperado não foi reconhecido.")
        return None
    try:
        col_nomes_originais = {idx: colunas_originais[idx] for idx in col_map.keys() if idx < len(colunas_originais)}
        df_para_renomear = df[col_nomes_originais.values()].copy()
        col_rename_map = {orig_name: db_name for idx, db_name in col_map.items() if idx in col_nomes_originais and (orig_name := col_nomes_originais[idx])}
        df_extraido = df_para_renomear.rename(columns=col_rename_map)
    except KeyError as e:
        st.error(f"Erro ao mapear colunas. Coluna esperada {e} não encontrada no arquivo.")
        st.error(f"Colunas encontradas: {colunas_originais}")
        return None
    except Exception as e:
        st.error(f"Erro ao processar colunas: {e}"); return None
    return df_extraido

def formatar_agencia_excel(id_agencia, nome_agencia):
    """ Formata o ID e Nome da Agência para o padrão 'AG 0001 - NOME' """
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except (ValueError, TypeError): id_str = str(id_agencia).strip() 
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo):
         nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"


# --- Tela Principal da Página ---
def tela_dados_agencia():
    st.markdown("<div class='section-title-center'>GESTÃO DE DADOS POR AGÊNCIA</div>", unsafe_allow_html=True)
    st.write(" ")

    # --- 1. Importador de Chamados ---
    with st.expander("📥 Importar Novos Chamados (Excel/CSV)"):
        st.info(f"""
            Arraste seu arquivo Excel/CSV. O sistema espera que a **primeira linha** contenha os cabeçalhos.
            As colunas necessárias (A, B, C, D, J, K, L, M, N, O, Q, T) serão lidas automaticamente.
            Se um `Chamado` (Coluna A) já existir, ele será **atualizado**.
        """)
        uploaded_file = st.file_uploader("Selecione o arquivo Excel/CSV de chamados", type=["xlsx", "xls", "csv"], key="chamado_uploader")

        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file, sep=';', header=0, encoding='latin-1', keep_default_na=False) 
                else:
                    df_raw = pd.read_excel(uploaded_file, header=0, keep_default_na=False) 

                df_raw.dropna(how='all', inplace=True)
                if df_raw.empty: st.error("Erro: O arquivo está vazio."); st.stop()

                # --- CORREÇÃO DO MAPEAMENTO (Q = 16) ---
                col_map = {
                    0: 'chamado_id', 1: 'agencia_id', 2: 'agencia_nome', 3: 'agencia_uf',
                    9: 'servico', 10: 'projeto_nome', 11: 'data_agendamento', 12: 'sistema',
                    13: 'cod_equipamento', 14: 'nome_equipamento', 
                    16: 'quantidade', # <<< CORRIGIDO: P(15) -> Q(16)
                    19: 'gestor'
                }
                
                df_para_salvar = extrair_e_mapear_colunas(df_raw, col_map)
                
                if df_para_salvar is not None:
                    st.success("Arquivo lido. Pré-visualização dos dados extraídos:")
                    st.dataframe(df_para_salvar.head(), use_container_width=True)

                    if st.button("▶️ Iniciar Importação de Chamados"):
                        if df_para_salvar.empty: st.error("Planilha vazia ou colunas não encontradas.")
                        else:
                            with st.spinner("Importando e atualizando chamados..."):
                                # Renomeia colunas para o formato que 'bulk_insert_chamados_db' espera
                                reverse_map = {
                                    'chamado_id': 'Chamado', 'agencia_id': 'Codigo_Ponto', 'agencia_nome': 'Nome',
                                    'agencia_uf': 'UF', 'servico': 'Servico', 'projeto_nome': 'Projeto',
                                    'data_agendamento': 'Data_Agendamento', 'sistema': 'Tipo_De_Solicitacao',
                                    'cod_equipamento': 'Sistema', 'nome_equipamento': 'Codigo_Equipamento',
                                    'quantidade': 'Quantidade_Solicitada', # <<< CORRIGIDO
                                    'gestor': 'Substitui_Outro_Equipamento_(Sim/Não)'
                                }
                                df_final_para_salvar = df_para_salvar.rename(columns=reverse_map)

                                sucesso, num_importados = utils.bulk_insert_chamados_db(df_final_para_salvar)
                                if sucesso:
                                    st.success(f"🎉 {num_importados} chamados importados/atualizados com sucesso!")
                                    st.balloons(); st.rerun() 
                                else:
                                    st.error("A importação de chamados falhou.")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")
                st.error("Verifique o formato do arquivo (Excel ou CSV com ';') e se ele não está corrompido.")

    st.divider()

    # --- 2. Carregar Dados (APENAS CHAMADOS) ---
    with st.spinner("Carregando dados de chamados..."):
        df_chamados_raw = utils.carregar_chamados_db()

    if df_chamados_raw.empty:
        st.info("Nenhum dado de chamado encontrado no sistema. Comece importando um arquivo acima.")
        st.stop()

    # --- 3. Criar o Campo Combinado de Agência ---
    if not df_chamados_raw.empty and 'Cód. Agência' in df_chamados_raw.columns:
        df_chamados_raw['Agencia_Combinada'] = df_chamados_raw.apply(
            lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), 
            axis=1
        )
    else:
        st.error("Tabela de chamados parece estar incompleta (sem 'Cód. Agência'). Tente re-importar."); st.stop()

    lista_agencias_completa = sorted(df_chamados_raw['Agencia_Combinada'].dropna().astype(str).unique())
    lista_agencias_completa = [a for a in lista_agencias_completa if a not in ["N/A", "None", ""]]
    lista_agencias_completa.insert(0, "Todas") 

    # --- 4. Filtro Principal por Agência ---
    st.markdown("#### 🏦 Selecionar Agência")
    agencia_selecionada = st.selectbox(
        "Selecione uma Agência para ver o histórico completo:",
        options=lista_agencias_completa,
        key="filtro_agencia_principal",
        label_visibility="collapsed"
    )
    st.divider()

    # --- 5. Exibição dos Dados (Filtrados) ---
    if agencia_selecionada == "Todas":
        df_chamados_filtrado = df_chamados_raw
    else:
        df_chamados_filtrado = df_chamados_raw[df_chamados_raw['Agencia_Combinada'] == agencia_selecionada]

    # --- 6. Painel Financeiro e KPIs ---
    total_chamados = len(df_chamados_filtrado)
    valor_total_chamados = 0.0
    chamados_abertos_count = 0
    
    if not df_chamados_filtrado.empty:
        if 'Valor (R$)' in df_chamados_filtrado.columns:
            valor_total_chamados = pd.to_numeric(df_chamados_filtrado['Valor (R$)'], errors='coerce').fillna(0).sum()
        if 'Status' in df_chamados_filtrado.columns:
            status_fechamento = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado']
            chamados_abertos_count = len(df_chamados_filtrado[~df_chamados_filtrado['Status'].astype(str).str.lower().isin(status_fechamento)])

    st.markdown(f"### 📊 Resumo da Agência: {agencia_selecionada}")
    cols_kpi = st.columns(3) 
    cols_kpi[0].metric("Total de Chamados", total_chamados)
    cols_kpi[1].metric("Chamados Abertos", chamados_abertos_count)
    cols_kpi[2].metric("Financeiro Chamados (R$)", f"{valor_total_chamados:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')) 
    st.divider()

    # --- 7. Visão em CARDS (Substitui as abas) ---
    st.markdown("#### 📋 Chamados Registrados")
    
    if df_chamados_filtrado.empty:
        st.info("Nenhum chamado encontrado para esta agência.")
    else:
        # Ordena os chamados pela data de agendamento mais recente
        df_chamados_filtrado['Agendamento'] = pd.to_datetime(df_chamados_filtrado['Agendamento'], errors='coerce')
        df_chamados_filtrado = df_chamados_filtrado.sort_values(by="Agendamento", ascending=False, na_position='last')
        
        # Loop para criar os cards de chamado
        for _, row in df_chamados_filtrado.iterrows():
            chamado_id_str = str(row.get('Nº Chamado', 'N/A'))
            
            # --- Monta o Cabeçalho (Conforme solicitado) ---
            data_recente_str = row.get('Agendamento_str', 'Sem Data')
            if pd.isna(row.get('Agendamento')):
                data_recente_str = "Sem Agendamento"
            else:
                data_recente_str = row.get('Agendamento').strftime('%d/%m/%Y')
                
            agencia_nome = row.get('Agencia_Combinada', 'N/A')
            projeto_nome = str(row.get('Projeto', 'N/A')).upper()
            gestor_nome = html.escape(str(row.get('Gestor', 'N/A')))
            uf_nome = html.escape(str(row.get('UF', 'N/A')))
            
            st.markdown(f"""
                <div class='project-card'>
                    <div style='display: flex; justify-content: space-between; align-items: flex-start;'>
                        <div style='flex: 3;'>
                            <h6 style='margin-bottom: 5px;'>📅 {data_recente_str} | {agencia_nome} ({uf_nome})</h6>
                            <h5 style='margin:2px 0;'>{projeto_nome}</h5>
                        </div>
                        <div style='flex: 1; text-align: right;'>
                            <span style='font-weight: bold; color: {utils.get_color_for_name(gestor_nome)};'>Gestor: {gestor_nome}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # --- Expander com Formulário de Edição ---
            with st.expander(f"Ver/Editar Detalhes do Chamado: {chamado_id_str}"):
                
                with st.form(f"form_chamado_edit_{row.get('ID')}"):
                    st.markdown(f"**Editando Chamado:** {chamado_id_str}")
                    
                    # Colunas do Card (Conforme solicitado)
                    col_form1, col_form2 = st.columns(2)
                    with col_form1:
                        data_abertura = _to_date_safe(row.get('Abertura'))
                        st.date_input("Data Abertura (Importado)", value=data_abertura, format="DD/MM/YYYY", disabled=True)
                        
                        agendamento_val = _to_date_safe(row.get('Agendamento'))
                        novo_agendamento = st.date_input("Data Agendamento (Editável)", value=agendamento_val, format="DD/MM/YYYY")
                        
                        finalizacao_val = _to_date_safe(row.get('Fechamento'))
                        novo_fechamento = st.date_input("Data Finalização (Editável)", value=finalizacao_val, format="DD/MM/YYYY")
                        
                        st.text_input("Nº Chamado", value=chamado_id_str, disabled=True)
                        st.text_input("Sistema", value=row.get('Sistema'), disabled=True)

                    with col_form2:
                        st.text_input("Serviço", value=row.get('Serviço'), disabled=True)
                        st.text_input("Nome Equipamento", value=row.get('Equipamento'), disabled=True)
                        st.text_input("Quantidade", value=row.get('Qtd.'), disabled=True)
                        st.text_input("Cód. Equipamento", value=row.get('Cód. Equip.'), disabled=True)
                        st.text_input("Status (do Excel)", value=row.get('Status'), disabled=True)
                    
                    # --- Novas Caixas de Texto ---
                    st.markdown("---")
                    nova_observacao = st.text_area(
                        "Observações (Editável)", 
                        value=row.get('Observação', ''),
                        placeholder="Insira observações sobre este chamado..."
                    )
                    log_chamado = row.get('Log do Chamado', '')
                    st.text_area(
                        "Log de Alterações", 
                        value=log_chamado, 
                        disabled=True, 
                        height=100
                    )
                    
                    # Botão de Salvar
                    btn_salvar_chamado = st.form_submit_button("💾 Salvar Alterações do Chamado")
                    
                    if btn_salvar_chamado:
                        # Prepara os dados para salvar
                        updates = {
                            "data_agendamento": novo_agendamento,
                            "data_fechamento": novo_fechamento,
                            "observacao": nova_observacao
                        }
                        
                        with st.spinner("Salvando..."):
                            sucesso = utils.atualizar_chamado_db(chamado_id_str, updates)
                            if sucesso:
                                st.success(f"Chamado {chamado_id_str} atualizado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Falha ao salvar as alterações.")

# --- Ponto de Entrada ---
tela_dados_agencia()
