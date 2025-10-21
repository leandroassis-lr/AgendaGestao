import streamlit as st
import pandas as pd
import psycopg2.extras
from utils import get_db_connection, normalize_key # Importa do utils.py corrigido

# =========================================================================
# FUNÇÕES DE IMPORTAÇÃO (Corrigidas)
# =========================================================================
def importar_configuracoes(conn, uploaded_file):
    """Lê um arquivo Excel com múltiplas abas e salva na tabela 'configuracoes'."""
    st.info("Iniciando importação das configurações...")
    try:
        excel_data = pd.ExcelFile(uploaded_file)
        aba_nomes = excel_data.sheet_names
        
        with conn.cursor() as cur:
            # Limpa configurações antigas antes de inserir as novas
            cur.execute("DELETE FROM configuracoes")
            st.write("Configurações antigas removidas.")

            for aba in aba_nomes:
                st.write(f"- Processando aba: '{aba}'...")
                df_aba = pd.read_excel(excel_data, sheet_name=aba)
                dados_json = df_aba.to_json(orient='records')
                
                query = "INSERT INTO configuracoes (aba_nome, dados_json) VALUES (%s, %s)"
                cur.execute(query, (aba.lower(), dados_json))
        
        conn.commit()
        st.success(f"Configurações das abas {aba_nomes} importadas com sucesso!")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao importar configurações: {e}")
        conn.rollback()
        return False

def importar_dados_tabela(conn, df, table_name, delete_first=False):
    """Função genérica para importar um DataFrame para uma tabela (projetos ou usuarios)."""
    st.info(f"Iniciando importação para a tabela '{table_name}'...")

    # 1. Normaliza as colunas do arquivo para o padrão do banco (minúsculo, underscore)
    df_renamed = df.rename(columns={col: normalize_key(col) for col in df.columns})
    
    # 2. Lista de colunas válidas para cada tabela (TUDO EM MINÚSCULAS)
    db_columns = {
        'projetos': [
            'projeto', 'descricao', 'agencia', 'tecnico', 'status', 'agendamento', 
            'data_abertura', 'data_finalizacao', 'observacao', 'demanda', 
            'log_agendamento', 'respostas_perguntas', 'etapas_concluidas'
        ],
        'usuarios': ['nome', 'email', 'senha']
    }
    
    valid_cols = db_columns.get(table_name, [])
    # Filtra o DataFrame para conter apenas colunas que existem na tabela de destino
    df_to_insert = df_renamed[[col for col in valid_cols if col in df_renamed.columns]]

    # 3. Converte para o formato que o banco de dados entende
    tuples = [tuple(row.where(pd.notna(row), None)) for _, row in df_to_insert.iterrows()]
    cols = ','.join(df_to_insert.columns) # Nomes já estão normalizados e seguros

    # 4. Executa a inserção em massa
    with conn.cursor() as cur:
        try:
            if delete_first:
                st.write(f"Limpando dados antigos da tabela '{table_name}'...")
                cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")

            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO {table_name} ({cols}) VALUES %s",
                tuples
            )
            conn.commit()
            st.success(f"{len(tuples)} registros importados para '{table_name}' com sucesso!")
            return True
        except Exception as e:
            st.error(f"Ocorreu um erro durante a importação para '{table_name}': {e}")
            conn.rollback()
            return False

# =========================================================================
# INTERFACE DO STREAMLIT (Inalterada)
# =========================================================================
st.set_page_config(layout="wide")
st.title("Ferramenta de Migração de Dados Completa 🚀")
st.warning("Atenção: Use esta ferramenta apenas uma vez para migrar seus dados.")

conn = get_db_connection()
if not conn:
    st.stop()

# --- SEÇÃO 1: CONFIGURAÇÕES ---
st.header("1. Importar Configurações (de um arquivo Excel)")
config_file = st.file_uploader("Selecione o arquivo Excel de configurações (ex: `config.xlsx`)", type=["xlsx"], key="config_uploader")
if config_file and st.button("Importar Configurações", key="btn_config"):
    importar_configuracoes(conn, config_file)

# --- SEÇÃO 2: USUÁRIOS ---
st.header("2. Importar Usuários")
user_file = st.file_uploader("Selecione o arquivo de usuários (ex: `usuarios.xlsx` ou `usuarios.csv`)", type=["xlsx", "csv"], key="user_uploader")
if user_file:
    df_users = pd.read_excel(user_file) if user_file.name.endswith('xlsx') else pd.read_csv(user_file)
    st.dataframe(df_users.head())
    if st.button("Importar Usuários", key="btn_users"):
        importar_dados_tabela(conn, df_users, 'usuarios', delete_first=True)

# --- SEÇÃO 3: PROJETOS ---
st.header("3. Importar Projetos")
project_file = st.file_uploader("Selecione o arquivo de projetos (ex: `projetos.xlsx` ou `projetos.csv`)", type=["xlsx", "csv"], key="project_uploader")
if project_file:
    df_projects = pd.read_excel(project_file) if project_file.name.endswith('xlsx') else pd.read_csv(project_file)
    st.dataframe(df_projects.head())
    if st.button("Importar Projetos", key="btn_projects", type="primary"):
        importar_dados_tabela(conn, df_projects, 'projetos', delete_first=True)
