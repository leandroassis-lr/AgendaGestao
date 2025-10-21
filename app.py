import streamlit as st
import pandas as pd
import psycopg2.extras
from utils import get_db_connection, normalize_key # Importa do seu novo utils.py

# =========================================================================
# FUNÇÕES DE IMPORTAÇÃO
# =========================================================================

def importar_configuracoes(conn, uploaded_file):
    """
    Lê um arquivo Excel com múltiplas abas (Status, Demanda, etc.)
    e salva cada aba como um registro JSON na tabela 'configuracoes'.
    """
    st.info("Iniciando importação das configurações...")
    try:
        # Usa pd.ExcelFile para poder ler múltiplas abas
        excel_data = pd.ExcelFile(uploaded_file)
        aba_nomes = excel_data.sheet_names
        
        with conn.cursor() as cur:
            for aba in aba_nomes:
                st.write(f"- Processando aba: '{aba}'...")
                df_aba = pd.read_excel(excel_data, sheet_name=aba)
                
                # Converte o DataFrame da aba para uma string JSON
                dados_json = df_aba.to_json(orient='records')
                
                # Query para inserir ou atualizar (UPSERT)
                query = """
                INSERT INTO configuracoes (aba_nome, dados_json)
                VALUES (%s, %s)
                ON CONFLICT (aba_nome) DO UPDATE SET
                    dados_json = EXCLUDED.dados_json;
                """
                cur.execute(query, (aba, dados_json))
        
        conn.commit()
        st.success(f"Configurações das abas {aba_nomes} importadas com sucesso!")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao importar configurações: {e}")
        conn.rollback()
        return False

def importar_dados_tabela(conn, df, table_name, column_mapping, delete_first=False):
    """
    Função genérica para importar um DataFrame para uma tabela específica.
    
    Args:
        conn: Conexão com o banco de dados.
        df: DataFrame com os dados a serem importados.
        table_name: Nome da tabela de destino (ex: 'projetos', 'usuarios').
        column_mapping: Dicionário para mapear nomes de colunas do arquivo para o BD.
        delete_first: Se True, apaga todos os dados da tabela antes de inserir.
    """
    st.info(f"Iniciando importação para a tabela '{table_name}'...")

    # 1. Renomeia as colunas do arquivo para o padrão do banco
    df_renamed = df.rename(columns=column_mapping)
    
    # 2. Define as colunas válidas para a tabela de destino
    db_columns = {
        'projetos': [
            'Projeto', 'Descricao', 'Agencia', 'Tecnico', 'Status', 'Agendamento', 
            'Data_Abertura', 'Data_Finalizacao', 'Observacao', 'Demanda', 
            'Log_Agendamento', 'Respostas_Perguntas', 'Etapas_Concluidas'
        ],
        'usuarios': ['Nome', 'Email', 'Senha']
    }
    
    valid_cols = db_columns.get(table_name, [])
    df_to_insert = df_renamed[[col for col in valid_cols if col in df_renamed.columns]]

    # 3. Converte para o formato que o banco de dados entende
    tuples = [tuple(row.where(pd.notna(row), None)) for _, row in df_to_insert.iterrows()]
    cols = ','.join([f'"{col}"' for col in df_to_insert.columns])

    # 4. Executa a inserção em massa
    with conn.cursor() as cur:
        try:
            if delete_first:
                st.write(f"Limpando dados antigos da tabela '{table_name}'...")
                cur.execute(f"DELETE FROM {table_name}")

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
# INTERFACE DO STREAMLIT
# =========================================================================
st.set_page_config(layout="wide")
st.title("Ferramenta de Migração de Dados Completa 🚀")
st.warning("Atenção: Use esta ferramenta apenas uma vez para migrar seus dados. Seus arquivos devem ter os nomes de colunas esperados.")

# --- SEÇÃO 1: CONFIGURAÇÕES ---
st.header("1. Importar Configurações (de um arquivo Excel)")
config_file = st.file_uploader(
    "Selecione o arquivo Excel de configurações (ex: `config.xlsx`)",
    type=["xlsx"],
    key="config_uploader"
)
if config_file:
    try:
        abas = pd.ExcelFile(config_file).sheet_names
        st.write("Abas encontradas no arquivo:", abas)
        if st.button("Importar Configurações", key="btn_config"):
            with st.spinner("Conectando ao banco e importando abas..."):
                conn = get_db_connection()
                if conn:
                    importar_configuracoes(conn, config_file)
    except Exception as e:
        st.error(f"Não foi possível ler o arquivo de configuração: {e}")

# --- SEÇÃO 2: USUÁRIOS ---
st.header("2. Importar Usuários")
user_file = st.file_uploader(
    "Selecione o arquivo de usuários (ex: `usuarios.xlsx` ou `usuarios.csv`)",
    type=["xlsx", "csv"],
    key="user_uploader"
)
if user_file:
    try:
        df_users = pd.read_excel(user_file) if user_file.name.endswith('xlsx') else pd.read_csv(user_file)
        st.dataframe(df_users.head())
        if st.button("Importar Usuários", key="btn_users"):
            # Mapeia as colunas do seu arquivo para as colunas do banco
            user_col_mapping = {'E-mail': 'Email', 'Nome': 'Nome', 'Senha': 'Senha'}
            with st.spinner("Importando usuários..."):
                conn = get_db_connection()
                if conn:
                    # `delete_first=True` para substituir todos os usuários existentes
                    importar_dados_tabela(conn, df_users, 'usuarios', user_col_mapping, delete_first=True)
    except Exception as e:
        st.error(f"Não foi possível ler o arquivo de usuários: {e}")

# --- SEÇÃO 3: PROJETOS ---
st.header("3. Importar Projetos")
project_file = st.file_uploader(
    "Selecione o arquivo de projetos (ex: `projetos.xlsx` ou `projetos.csv`)",
    type=["xlsx", "csv"],
    key="project_uploader"
)
if project_file:
    try:
        df_projects = pd.read_excel(project_file) if project_file.name.endswith('xlsx') else pd.read_csv(project_file)
        st.dataframe(df_projects.head())
        if st.button("Importar Projetos", key="btn_projects", type="primary"):
            # Mapeia as colunas do seu arquivo para as colunas do banco.
            # Usa a função `normalize_key` para tratar variações de nomes.
            project_col_mapping = {col: normalize_key(col) for col in df_projects.columns}
            with st.spinner("Importando projetos... Isso pode levar um momento."):
                conn = get_db_connection()
                if conn:
                    # `delete_first=False` (padrão) para apenas adicionar os projetos
                    importar_dados_tabela(conn, df_projects, 'projetos', project_col_mapping)
    except Exception as e:
        st.error(f"Não foi possível ler o arquivo de projetos: {e}")

