import streamlit as st
import pandas as pd
import utils # Apenas para CSS e Login Check
import utils_chamados # <<< NOSSO NOVO ARQUIVO
from datetime import date, datetime
import re 
import html 

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() # Tenta carregar o CSS
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
    
    # Validação (o CSV tem 29 colunas, T=19)
    if len(colunas_originais) < 20: 
        st.error(f"Erro: O arquivo carregado parece ter apenas {len(colunas_originais)} colunas. O formato esperado (com 20+ colunas) não foi reconhecido.")
        return None
    try:
        col_nomes_originais = {idx: colunas_originais[idx] for idx in col_map.keys() if idx < len(colunas_originais)}
        df_para_renomear = df[list(col_nomes_originais.values())].copy() # Convertido para lista
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
            As colunas necessárias (baseado no arquivo 'RelatorioAnexo...'):
            - **A:** Chamado (ID)
            - **B:** Codigo_Ponto (ID Agência)
            - **C:** Nome (Nome Agência)
            - **D:** UF
            - **J:** Servico
            - **K:** Projeto
            - **L:** Data_Agendamento (Formato DD/MM/AAAA)
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
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file, sep=';', header=0, encoding='latin-1', keep_default_na=False, dtype=str) # Lê tudo como string
                else:
                    df_raw = pd.read_excel(uploaded_file, header=0, keep_default_na=False, dtype=str) # Lê tudo como string

                df_raw.dropna(how='all', inplace=True)
                if df_raw.empty: st.error("Erro: O arquivo está vazio."); st.stop()

                # --- Mapeamento (Q = 16) ---
                col_map = {
                    0: 'chamado_id', 1: 'agencia_id', 2: 'agencia_nome', 3: 'agencia_uf',
                    9: 'servico', 10: 'projeto_nome', 11: 'data_agendamento', 12: 'sistema',
                    13: 'cod_equipamento', 14: 'nome_equipamento',
