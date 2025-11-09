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
        ts = pd.to_datetime(val, errors='coerce', dayfirst=True) # Tenta ler DD/MM/AAAA
        if pd.isna(ts): return None
        return ts.date()
    except Exception: return None

# --- Funções Helper da Página ---
def extrair_e_mapear_colunas(df, col_map):
    """ Extrai e renomeia colunas com base em índices. """
    df_extraido = pd.DataFrame()
    colunas_originais = df.columns.tolist()
    
    if len(colunas_originais) < 20: 
        st.error(f"Erro: O arquivo carregado parece ter apenas {len(colunas_originais)} colunas. O formato esperado (com 20+ colunas) não foi reconhecido.")
        return None
    try:
        col_nomes_originais = {idx: colunas_originais[idx] for idx in col_map.keys() if idx < len(colunas_originais)}
        df_para_renomear = df[list(col_nomes_originais.values())].copy() 
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
    
    # --- Roda a função de criação/atualização da tabela ---
    utils_chamados.criar_tabela_chamados()

    # --- 1. Importador de Chamados ---
    with st.expander("📥 Importar Novos Chamados (Excel/CSV)"):
        st.info(f"""
             Arraste seu arquivo Excel de chamados (formato `.xlsx` ou `.csv` com `;`) aqui.
             O sistema espera que a **primeira linha** contenha os cabeçalhos.
             As colunas necessárias (A, B, C, D, J, K, L, M, N, O, Q, T) serão lidas automaticamente.
             Se um `Chamado` (Coluna A) já existir, ele será **atualizado**.
        """)
        uploaded_file = st.file_uploader("Selecione o arquivo Excel/CSV de chamados", type=["xlsx", "xls", "csv"], key="chamado_uploader")

        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file, sep=';', header=0, encoding='latin-1', keep_default_na=False, dtype=str) 
                else:
                    df_raw = pd.read_excel(uploaded_file, header=0, keep_default_na=False, dtype=str) 

                df_raw.dropna(how='all', inplace=True)
                if df_raw.empty: st.error("Erro: O arquivo está vazio."); st.stop()

                # --- Mapeamento (Q = 16) ---
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
                        if df_para_salvar.empty: st.error("Planilha vazia ou colunas não encontradas.")
                        else:
                            with st.spinner("Importando e atualizando chamados..."):
                                # Renomeia colunas para o formato que 'bulk_insert_chamados_db' espera
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
                                    st.balloons(); st.rerun() 
                                else:
                                    st.error("A importação de chamados falhou.")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")
                st.error("Verifique o formato do arquivo (Excel ou CSV com ';') e se ele não está corrompido.")

    st.divider()

    # --- 2. Carregar Dados (APENAS CHAMADOS) ---
    with st.spinner("Carregando dados de chamados..."):
        # ATENÇÃO: Carrega SEMPRE todos os dados. O filtro do 'utils' não está sendo usado.
        df_chamados_raw = utils_chamados.carregar_chamados_db()

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
        # Filtra o dataframe PÓS-CARREGAMENTO
        df_chamados_filtrado = df_chamados_raw[df_chamados_raw['Agencia_Combinada'] == agencia_selecionada]


    # --- 6. Painel Financeiro e KPIs ---
    total_chamados = len(df_chamados_filtrado)
    valor_total_chamados = 0.0; chamados_abertos_count = 0
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


    # --- 7. NOVA VISÃO HIERÁRQUICA (Agência -> Projeto -> Chamados) ---
    st.markdown("#### 📋 Visão por Projetos e Chamados")
    
    if df_chamados_filtrado.empty:
        st.info("Nenhum chamado encontrado para os filtros selecionados.")
        st.stop()

    # Prepara o DataFrame para agrupamento
    try:
        # Converte datas para string DD/MM/YYYY para poder agrupar
        df_chamados_filtrado['Agendamento_str'] = pd.to_datetime(df_chamados_filtrado['Agendamento']).dt.strftime('%d/%m/%Y').fillna('Sem Data')
        df_chamados_filtrado['Abertura_str'] = pd.to_datetime(df_chamados_filtrado['Abertura']).dt.strftime('%d/%m/%Y').fillna('Sem Data')
        df_chamados_filtrado['Fechamento_str'] = pd.to_datetime(df_chamados_filtrado['Fechamento']).dt.strftime('%d/%m/%Y').fillna('N/A')
        
        # Garante que colunas de placeholder existam (se você não atualizou o utils)
        if 'Analista' not in df_chamados_filtrado.columns: df_chamados_filtrado['Analista'] = 'N/A'
        if 'Técnico' not in df_chamados_filtrado.columns: df_chamados_filtrado['Técnico'] = 'N/A'
        
        # Define as chaves de agrupamento
        chave_agencia = 'Agencia_Combinada'
        chave_projeto = ['Projeto', 'Gestor', 'Agendamento_str']

    except KeyError as e:
        st.error(f"Erro ao preparar dados: Coluna {e} não encontrada. Verifique o mapeamento da importação.")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao processar datas: {e}")
        st.stop()

    
    # --- NÍVEL 1: Loop pelas Agências ---
    # (Se 'Todas' não estiver selecionado, este loop rodará apenas 1x)
    
    if agencia_selecionada == "Todas":
        agencias_agrupadas = df_chamados_filtrado.groupby(chave_agencia)
    else:
        # Cria um "grupo falso" para o loop funcionar da mesma forma
        agencias_agrupadas = [(agencia_selecionada, df_chamados_filtrado)]

    for nome_agencia, df_agencia in agencias_agrupadas:
        
        # Se 'Todas' estiver ativo, cria um expander para a agência
        if agencia_selecionada == "Todas":
            expander_agencia = st.expander(f"🏦 {nome_agencia} ({len(df_agencia)} chamados)")
        else:
            # Se uma agência já foi selecionada, não precisamos de outro expander
            expander_agencia = st.container() 

        with expander_agencia:
            
            # --- NÍVEL 2: Loop pelos Projetos ---
            try:
                projetos_agrupados = df_agencia.groupby(chave_projeto)
                if not projetos_agrupados.groups:
                    st.info(f"Nenhum chamado encontrado para a agência {nome_agencia}.")
                    continue # Vai para a próxima agência
            
            except KeyError:
                st.error("Falha ao agrupar por Projeto/Gestor/Agendamento. Verifique se as colunas existem.")
                continue

            for (nome_projeto, nome_gestor, data_agend), df_projeto in projetos_agrupados:
                
                # Monta o cabeçalho do Projeto
                nome_projeto_str = str(nome_projeto).upper()
                nome_gestor_str = html.escape(str(nome_gestor))
                
                header_projeto = f"Projeto: {nome_projeto_str} | Gestor: {nome_gestor_str} | Agendamento: {data_agend}"
                
                with st.expander(header_projeto):
                    
                    # --- NÍVEL 3: Detalhes do Projeto ---
                    
                    # Parte A: A "Descrição" (Resumo de Equipamentos)
                    descricao_list = []
                    for _, chamado_row in df_projeto.iterrows():
                        # Converte Qtd para int, tratando nulos/erros
                        qtd_val = pd.to_numeric(chamado_row.get('Qtd.'), errors='coerce').fillna(0)
                        qtd_int = int(qtd_val)
                        equip_str = str(chamado_row.get('Equipamento', 'N/A'))
                        descricao_list.append(f"{qtd_int:02d} - {equip_str}")
                    
                    descricao_texto = "\n".join(descricao_list)
                    
                    st.text_area(
                        "Descrição (Equipamentos do Projeto)", 
                        value=descricao_texto, 
                        height=150, 
                        disabled=True,
                        key=f"desc_proj_{nome_agencia}_{nome_projeto}_{data_agend}" # Chave única
                    )
                    
                    st.markdown("---")
                    st.markdown("##### Chamados Individuais deste Projeto:")

                    # Parte B: A Tabela de Chamados
                    
                    # Define as colunas que queremos exibir na tabela
                    colunas_para_exibir = [
                        'Nº Chamado', 
                        'Status', 
                        'Abertura_str', # Usamos a string formatada
                        'Agendamento_str', # Usamos a string formatada
                        'Fechamento_str', # Usamos a string formatada
                        'Analista', 
                        'Técnico', 
                        'Sistema', 
                        'Serviço'
                    ]
                    
                    # Renomeia colunas para a visualização
                    df_display = df_projeto[colunas_para_exibir].rename(columns={
                        'Abertura_str': 'Abertura',
                        'Agendamento_str': 'Agendamento',
                        'Fechamento_str': 'Finalização'
                    })

                    # Exibe os chamados em uma tabela
                    st.dataframe(df_display, use_container_width=True)

                    # NOTA: A antiga lógica de "st.form" para CADA chamado
                    # foi removida para dar lugar a esta tabela-resumo.

# --- Ponto de Entrada ---
tela_dados_agencia()
