import streamlit as st
import pandas as pd
import utils # Importa nosso arquivo de utilidades
from datetime import date, datetime
import re 
import html # Importar html para escapar

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() # Tenta carregar o CSS
except:
    pass # Ignora se falhar

# --- Controle Principal de Login (Independente do app.py) ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

# --- Funções Helper da Página ---

def extrair_e_mapear_colunas(df, col_map):
    """
    Extrai colunas do DataFrame raw (lido do Excel/CSV) com base em um mapa
    de índices (números) para nomes de colunas do banco de dados.
    """
    df_extraido = pd.DataFrame()
    colunas_originais = df.columns.tolist()
    
    # Validação para garantir que o arquivo não está totalmente fora do padrão
    if len(colunas_originais) < 20: # O seu arquivo tem 20+ colunas (T=19)
        st.error(f"Erro: O arquivo carregado parece ter apenas {len(colunas_originais)} colunas. O formato esperado não foi reconhecido.")
        return None

    try:
        # Pega os nomes das colunas originais do arquivo (da linha 1)
        col_nomes_originais = {
            idx: colunas_originais[idx] for idx in col_map.keys() if idx < len(colunas_originais)
        }
        
        # Pega as colunas pelos Nomes Originais
        df_para_renomear = df[col_nomes_originais.values()].copy()
        
        # Mapeia o Nome Original -> Nome do BD
        col_rename_map = {
             orig_name: db_name for idx, db_name in col_map.items() 
             if idx in col_nomes_originais and (orig_name := col_nomes_originais[idx])
        }
        
        df_extraido = df_para_renomear.rename(columns=col_rename_map)
        
    except KeyError as e:
        st.error(f"Erro ao mapear colunas. Coluna esperada {e} não encontrada no arquivo.")
        st.error(f"Colunas encontradas: {colunas_originais}")
        return None
    except Exception as e:
        st.error(f"Erro ao processar colunas: {e}")
        return None
            
    return df_extraido

def formatar_agencia_excel(id_agencia, nome_agencia):
    """ Formata o ID e Nome da Agência para o padrão 'AG 0001 - NOME' """
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except (ValueError, TypeError):
        id_str = str(id_agencia).strip() 
    
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
            Arraste seu arquivo Excel de chamados (formato `.xlsx` ou `.csv` com `;`) aqui.
            O sistema espera que a **primeira linha** contenha os cabeçalhos.
            As colunas necessárias (baseado no arquivo 'RelatorioAnexo...'):
            - **A:** Chamado (ID)
            - **B:** Codigo_Ponto (ID Agência)
            - **C:** Nome (Nome Agência)
            - **D:** UF
            - **J:** Servico
            - **K:** Projeto
            - **L:** Data_Agendamento
            - **M:** Tipo_De_Solicitacao (será salvo como 'Sistema')
            - **N:** Sistema (será salvo como 'Cód. Equipamento')
            - **O:** Codigo_Equipamento (será salvo como 'Nome Equipamento')
            - **Q:** Quantidade_Solicitada (será salvo como 'Quantidade')
            - **T:** Gestor
            
            Se um `Chamado` (Coluna A) já existir, ele será **atualizado**.
        """)
        uploaded_file = st.file_uploader("Selecione o arquivo Excel/CSV de chamados", type=["xlsx", "xls", "csv"], key="chamado_uploader")

        if uploaded_file is not None:
            try:
                # Lê o arquivo a partir da LINHA 1 (índice 0)
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file, sep=';', header=0, encoding='latin-1', keep_default_na=False) 
                else:
                    df_raw = pd.read_excel(uploaded_file, header=0, keep_default_na=False) 

                df_raw.dropna(how='all', inplace=True)
                if df_raw.empty:
                    st.error("Erro: O arquivo está vazio ou não foi lido corretamente.")
                    st.stop()

                # --- >>> CORREÇÃO DO MAPEAMENTO <<< ---
                # Coluna A=0, B=1, C=2, D=3, J=9, K=10, L=11, M=12, N=13, O=14, Q=16, T=19
                col_map = {
                    0: 'chamado_id', 1: 'agencia_id', 2: 'agencia_nome', 3: 'agencia_uf',
                    9: 'servico', 10: 'projeto_nome', 11: 'data_agendamento', 12: 'sistema',
                    13: 'cod_equipamento', 14: 'nome_equipamento', 
                    16: 'quantidade', # <<< CORRIGIDO: P (15) -> Q (16)
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

    # --- 5. Exibição dos Dados ---
    if agencia_selecionada == "Todas":
        df_chamados_filtrado = df_chamados_raw
    else:
        # Filtra pelo Cód. Agência, não pelo nome combinado, para ser mais preciso
        agencia_id_filtro = agencia_selecionada.split(" - ")[0].replace("AG ", "").lstrip('0')
        df_chamados_filtrado = df_chamados_raw[df_chamados_raw['Cód. Agência'].astype(str) == agencia_id_filtro]

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

    # --- 7. Visão Agrupada (Projeto -> Chamados) ---
    st.markdown("---")
    st.markdown("#### 📋 Chamados Agrupados por Projeto")
    
    if df_chamados_filtrado.empty:
        st.info("Nenhum chamado encontrado para esta agência.")
    else:
        df_chamados_filtrado['Projeto'] = df_chamados_filtrado['Projeto'].fillna('Projeto Não Especificado')
        df_chamados_por_projeto = df_chamados_filtrado.groupby('Projeto')
        
        for projeto_nome, chamados_do_projeto in df_chamados_por_projeto:
            total_chamados_projeto = len(chamados_do_projeto)
            valor_projeto = pd.to_numeric(chamados_do_projeto['Valor (R$)'], errors='coerce').fillna(0).sum()
            header = f"**{str(projeto_nome).upper()}** ({total_chamados_projeto} chamados) | **Valor Total:** R$ {valor_projeto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            with st.expander(header, expanded=False): 
                status_fechamento = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado']
                chamados_abertos_proj = len(chamados_do_projeto[~chamados_do_projeto['Status'].astype(str).str.lower().isin(status_fechamento)])
                
                if chamados_abertos_proj > 0:
                    st.warning(f"**Atenção:** {chamados_abertos_proj} chamado(s) deste projeto ainda estão abertos.")
                else:
                    st.success("Todos os chamados deste projeto estão fechados.")

                colunas_chamados_visiveis = ['Nº Chamado', 'Descrição', 'Status', 'Abertura', 'Fechamento', 'Equipamento', 'Qtd.', 'Gestor']
                colunas_chamados = [col for col in colunas_chamados_visiveis if col in chamados_do_projeto.columns]
                st.dataframe(chamados_do_projeto[colunas_chamados], use_container_width=True, hide_index=True)

# --- Ponto de Entrada ---
tela_dados_agencia()
