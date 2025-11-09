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
        df_chamados_filtrado['Agendamento_str'] = pd.to_datetime(df_chamados_filtrado['Agendamento']).dt.strftime('%d/%m/%Y').fillna('Sem Data')
        df_chamados_filtrado['Abertura_str'] = pd.to_datetime(df_chamados_filtrado['Abertura']).dt.strftime('%d/%m/%Y').fillna('Sem Data')
        df_chamados_filtrado['Fechamento_str'] = pd.to_datetime(df_chamados_filtrado['Fechamento']).dt.strftime('%d/%m/%Y').fillna('N/A')
        
        if 'Analista' not in df_chamados_filtrado.columns: df_chamados_filtrado['Analista'] = 'N/A'
        if 'Técnico' not in df_chamados_filtrado.columns: df_chamados_filtrado['Técnico'] = 'N/A'
        if 'UF' not in df_chamados_filtrado.columns: df_chamados_filtrado['UF'] = 'N/A'
        
        chave_agencia = 'Agencia_Combinada'
        chave_projeto = ['Projeto', 'Gestor', 'Agendamento_str']

    except KeyError as e:
        st.error(f"Erro ao preparar dados: Coluna {e} não encontrada. Verifique o mapeamento da importação.")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao processar datas: {e}")
        st.stop()

    
    # --- NÍVEL 1: Loop pelas Agências ---
    if agencia_selecionada == "Todas":
        agencias_agrupadas = df_chamados_filtrado.groupby(chave_agencia)
    else:
        agencias_agrupadas = [(agencia_selecionada, df_chamados_filtrado)]

    for nome_agencia, df_agencia in agencias_agrupadas:
        
        if agencia_selecionada == "Todas":
            expander_agencia = st.expander(f"🏦 {nome_agencia} ({len(df_agencia)} chamados)")
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
                st.error("Falha ao agrupar por Projeto/Gestor/Agendamento. Verifique se as colunas existem.")
                continue

            for (nome_projeto, nome_gestor, data_agend), df_projeto in projetos_agrupados:
                
                nome_projeto_str = str(nome_projeto).upper()
                nome_gestor_str = html.escape(str(nome_gestor))
                
                header_projeto = f"Projeto: {nome_projeto_str} | Gestor: {nome_gestor_str} | Agendamento: {data_agend}"
                
                with st.expander(header_projeto):
                    
                    # --- NÍVEL 3 (Resumo do Projeto) ---
                    
                    # Lista de Chamados
                    lista_chamados_str = ", ".join(df_projeto['Nº Chamado'].unique())
                    st.info(f"Chamados neste projeto: {lista_chamados_str}")

                    # Descrição Agregada (Equipamentos)
                    descricao_list = []
                    for _, chamado_row_desc in df_projeto.iterrows():
                        # --- INÍCIO DA CORREÇÃO pd.to_numeric ---
                        qtd_val_numeric = pd.to_numeric(chamado_row_desc.get('Qtd.'), errors='coerce')
                        if pd.isna(qtd_val_numeric):
                            qtd_int = 0
                        else:
                            qtd_int = int(qtd_val_numeric)
                        # --- FIM DA CORREÇÃO ---
                        equip_str = str(chamado_row_desc.get('Equipamento', 'N/A'))
                        descricao_list.append(f"{qtd_int:02d} - {equip_str}")
                    
                    descricao_texto = "\n".join(descricao_list)
                    st.text_area(
                        "Descrição (Equipamentos do Projeto)", 
                        value=descricao_texto, 
                        height=max(50, len(descricao_list) * 25 + 25), # Altura dinâmica
                        disabled=True,
                        key=f"desc_proj_{nome_agencia}_{nome_projeto}_{data_agend}"
                    )
                    
                    st.markdown("---")
                    st.markdown("##### 🔎 Detalhes por Chamado Individual")

                    # --- NÍVEL 3 (Detalhes por Chamado) ---
                    for _, chamado_row in df_projeto.iterrows():
                        chamado_id_interno = chamado_row['ID']
                        chamado_id_str = chamado_row['Nº Chamado']
                        status_chamado = str(chamado_row.get('Status', 'N/A'))
                        
                        expander_title = f"▶️ Chamado: {chamado_id_str} (Status: {status_chamado})"
                        
                        with st.expander(expander_title):
                            
                            # (Aqui podemos adicionar o "Ver/Editar Detalhes" no futuro)
                            # st.button("Ver/Editar Detalhes", key=f"edit_{chamado_id_interno}")
                            
                            st.markdown("**Informações e Prazos**")
                            c1, c2, c3, c4 = st.columns(4)
                            c1.text_input("Status", value=status_chamado, disabled=True, key=f"status_{chamado_id_interno}")
                            c2.text_input("Data Abertura", value=chamado_row['Abertura_str'], disabled=True, key=f"abertura_{chamado_id_interno}")
                            c3.text_input("Agendamento", value=chamado_row['Agendamento_str'], disabled=True, key=f"agend_{chamado_id_interno}")
                            c4.text_input("Data Finalização", value=chamado_row['Fechamento_str'], disabled=True, key=f"final_{chamado_id_interno}")

                            st.markdown("**Detalhes do Projeto**")
                            c1, c2, c3, c4 = st.columns(4)
                            c1.text_input("Projeto", value=chamado_row['Projeto'], disabled=True, key=f"proj_{chamado_id_interno}")
                            c2.text_input("Analista", value=chamado_row['Analista'], disabled=True, key=f"analista_{chamado_id_interno}")
                            c3.text_input("Gestor", value=chamado_row['Gestor'], disabled=True, key=f"gestor_{chamado_id_interno}")
                            c4.text_input("Agência", value=chamado_row['Agencia_Combinada'], disabled=True, key=f"ag_{chamado_id_interno}")
                            
                            c1, c2, c3 = st.columns(3) # Segunda linha de detalhes
                            c1.text_input("Técnico", value=chamado_row['Técnico'], disabled=True, key=f"tec_{chamado_id_interno}")
                            c2.text_input("Serviço", value=chamado_row.get('Serviço', 'N/A'), disabled=True, key=f"serv_{chamado_id_interno}")
                            c3.text_input("Sistema", value=chamado_row.get('Sistema', 'N/A'), disabled=True, key=f"sist_{chamado_id_interno}")

                            st.markdown("**Descrição (Equipamento deste chamado)**")
                            # Recalcula a Qtd/Equip para ESTE chamado
                            qtd_val_numeric_ind = pd.to_numeric(chamado_row.get('Qtd.'), errors='coerce')
                            qtd_int_ind = int(qtd_val_numeric_ind) if pd.notna(qtd_val_numeric_ind) else 0
                            equip_str_ind = str(chamado_row.get('Equipamento', 'N/A'))
                            
                            st.text_area(
                                "Equipamento e Quantidade", 
                                value=f"{qtd_int_ind:02d} - {equip_str_ind}", 
                                disabled=True, height=50,
                                key=f"desc_ind_{chamado_id_interno}"
                            )

                            st.markdown("**Observação / Pendências**")
                            st.text_area(
                                "Observações", 
                                value=chamado_row.get('Observação', ''), 
                                disabled=True, 
                                key=f"obs_{chamado_id_interno}"
                            )
                            
                            st.markdown("**Histórico de Alterações**")
                            st.text_area(
                                "Log de Alterações", 
                                value=chamado_row.get('Log do Chamado', 'Sem histórico.'), 
                                disabled=True, height=100,
                                key=f"log_{chamado_id_interno}"
                            )

# --- Ponto de Entrada ---
tela_dados_agencia()
