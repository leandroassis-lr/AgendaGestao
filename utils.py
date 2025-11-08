# Atualizando o cache#
import streamlit as st
import pandas as pd
from datetime import date, datetime 
import re
import html
import psycopg2
from psycopg2 import sql
import io
import base64
from io import BytesIO
from PIL import Image
import numpy as np # <<< IMPORTANTE: ADICIONADO NUMPY

# (image_to_base64 - Sem alterações)
def image_to_base64(image):
    """Converte uma imagem PIL em string Base64 para exibição no Streamlit."""
    buffered = BytesIO(); image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# (get_db_connection - Sem alterações)
@st.cache_resource
def get_db_connection():
    """Cria e gerencia a conexão com o banco de dados PostgreSQL."""
    try:
        secrets = st.secrets["postgres"]
        conn = psycopg2.connect(host=secrets["PGHOST"], port=secrets["PGPORT"], user=secrets["PGUSER"], password=secrets["PGPASSWORD"], dbname=secrets["PGDATABASE"])
        conn.autocommit = True; return conn
    except KeyError as e: st.error(f"Erro Crítico: Credencial '{e}' não encontrada."); return None
    except Exception as e: st.error(f"Erro ao conectar ao DB: {e}"); return None

conn = get_db_connection() 

# (criar_tabelas_iniciais - Sem alterações)
def criar_tabelas_iniciais():
    """Cria as tabelas e adiciona colunas ausentes se não existirem."""
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projetos (
                    id SERIAL PRIMARY KEY, projeto TEXT, descricao TEXT, agencia TEXT, 
                    tecnico TEXT, status TEXT, agendamento DATE, data_abertura DATE, 
                    data_finalizacao DATE, observacao TEXT, demanda TEXT, log_agendamento TEXT,
                    respostas_perguntas JSONB, etapas_concluidas TEXT, analista TEXT, 
                    gestor TEXT, prioridade TEXT DEFAULT 'Média',
                    links_referencia TEXT 
                );
            """)
            cur.execute("CREATE TABLE IF NOT EXISTS configuracoes (aba_nome TEXT PRIMARY KEY, dados_json JSONB);")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY, nome TEXT, email TEXT UNIQUE, senha TEXT,
                    permissao TEXT DEFAULT 'Usuario'
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chamados (
                    id SERIAL PRIMARY KEY, agencia_id TEXT, agencia_nome TEXT, agencia_uf TEXT,
                    chamado_id TEXT UNIQUE, servico TEXT, projeto_nome TEXT, data_agendamento DATE,
                    sistema TEXT, cod_equipamento TEXT, nome_equipamento TEXT, quantidade INTEGER,
                    gestor TEXT, descricao TEXT, data_abertura DATE, data_fechamento DATE,
                    status_chamado TEXT, valor_chamado NUMERIC(10, 2) DEFAULT 0.00,
                    status_financeiro TEXT DEFAULT 'Pendente'
                );
            """)
            colunas_a_verificar = {
                'projetos': [('prioridade', "TEXT DEFAULT 'Média'"), ('links_referencia', 'TEXT')],
                'usuarios': [('permissao', "TEXT DEFAULT 'Usuario'")],
                'chamados': [ 
                    ('agencia_id', 'TEXT'), ('agencia_nome', 'TEXT'), ('agencia_uf', 'TEXT'),
                    ('servico', 'TEXT'), ('projeto_nome', 'TEXT'), ('data_agendamento', 'DATE'),
                    ('sistema', 'TEXT'), ('cod_equipamento', 'TEXT'), ('nome_equipamento', 'TEXT'),
                    ('quantidade', 'INTEGER'), ('gestor', 'TEXT'), ('descricao', 'TEXT'),
                    ('data_abertura', 'DATE'), ('data_fechamento', 'DATE'), ('status_chamado', 'TEXT'),
                    ('valor_chamado', 'NUMERIC(10, 2) DEFAULT 0.00'), ('status_financeiro', "TEXT DEFAULT 'Pendente'")
                ]
            }
            for tabela, colunas in colunas_a_verificar.items():
                for coluna, tipo_coluna in colunas:
                    cur.execute(f"SELECT 1 FROM information_schema.columns WHERE table_name = '{tabela}' AND column_name = '{coluna}';")
                    if not cur.fetchone():
                        st.warning(f"Atualizando BD: Adicionando coluna '{coluna}' à tabela '{tabela}'...")
                        cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo_coluna};")
                        st.success(f"Coluna '{coluna}' adicionada.")
    except Exception as e:
        st.error(f"Erro ao criar/verificar tabelas: {e}")

# (_normalize_and_sanitize - Sem alterações)
def _normalize_and_sanitize(data_dict: dict):
    normalized = {}
    for key, value in data_dict.items():
        k = str(key).lower(); k = re.sub(r'[áàâãä]', 'a', k); k = re.sub(r'[éèêë]', 'e', k); k = re.sub(r'[íìîï]', 'i', k); k = re.sub(r'[óòôõö]', 'o', k); k = re.sub(r'[úùûü]', 'u', k); k = re.sub(r'[ç]', 'c', k); k = re.sub(r'[^a-z0-9_ ]', '', k); k = k.replace(' de ', ' ').replace(' ', '_') 
        if 'links' in k and 'referencia' in k: k = 'links_referencia'
        if value is None or (isinstance(value, float) and pd.isna(value)): sanitized_value = None
        elif isinstance(value, (datetime, date)): sanitized_value = value.strftime('%Y-%m-%d')
        elif k == 'prioridade' and value == 'N/A': sanitized_value = None 
        else: sanitized_value = str(value)
        normalized[k] = sanitized_value
    return normalized

# (carregar_projetos_db - Sem alterações)
@st.cache_data(ttl=60) 
def carregar_projetos_db(): 
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT * FROM projetos ORDER BY id DESC"
        df = pd.read_sql_query(query, conn) 
        rename_map = {'id': 'ID', 'descricao': 'Descrição', 'agencia': 'Agência', 'tecnico': 'Técnico','observacao': 'Observação', 'data_abertura': 'Data de Abertura','data_finalizacao': 'Data de Finalização', 'log_agendamento': 'Log Agendamento','etapas_concluidas': 'Etapas Concluidas', 'projeto': 'Projeto', 'status': 'Status','agendamento': 'Agendamento', 'demanda': 'Demanda', 'analista': 'Analista', 'gestor': 'Gestor', 'prioridade': 'Prioridade','links_referencia': 'Links de Referência'}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        if 'Agendamento' in df.columns: df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
        if 'Prioridade' in df.columns: df['Prioridade'] = df['Prioridade'].fillna('Média').replace(['', None], 'Média')
        else: df['Prioridade'] = 'Média' 
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos do DB: {e}"); return pd.DataFrame() 

# (carregar_projetos_sem_agendamento_db - Sem alterações)
@st.cache_data(ttl=60)
def carregar_projetos_sem_agendamento_db(): 
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT * FROM projetos WHERE agendamento IS NULL ORDER BY id DESC"
        df = pd.read_sql_query(query, conn)
        rename_map = {'id': 'ID', 'descricao': 'Descrição', 'agencia': 'Agência', 'tecnico': 'Técnico','observacao': 'Observação', 'data_abertura': 'Data de Abertura','data_finalizacao': 'Data de Finalização', 'log_agendamento': 'Log Agendamento','etapas_concluidas': 'Etapas Concluidas', 'projeto': 'Projeto', 'status': 'Status','agendamento': 'Agendamento', 'demanda': 'Demanda', 'analista': 'Analista', 'gestor': 'Gestor', 'prioridade': 'Prioridade','links_referencia': 'Links de Referência'}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        if 'Agendamento' in df.columns: df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
        if 'Prioridade' in df.columns: df['Prioridade'] = df['Prioridade'].fillna('Média').replace(['', None], 'Média')
        else: df['Prioridade'] = 'Média'
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos do backlog: {e}"); return pd.DataFrame()

# (adicionar_projeto_db - Sem alterações)
def adicionar_projeto_db(data: dict):
    if not conn: return False
    try:
        if "Prioridade" not in data or data["Prioridade"] == "N/A": data["Prioridade"] = "Média" 
        db_data = _normalize_and_sanitize(data)
        cols_with_values = {k: v for k, v in db_data.items() if v is not None}
        if not cols_with_values: st.toast("Erro: Nenhum dado.", icon="🔥"); return False
        cols = cols_with_values.keys(); vals = list(cols_with_values.values())
        query = sql.SQL("INSERT INTO projetos ({}) VALUES ({})").format(sql.SQL(', ').join(map(sql.Identifier, cols)), sql.SQL(', ').join(sql.Placeholder() * len(cols)))
        with conn.cursor() as cur: cur.execute(query, vals)
        st.cache_data.clear(); return True
    except Exception as e: st.toast(f"Erro ao adicionar projeto: {e}", icon="🔥"); return False

# (atualizar_projeto_db - Sem alterações)
def atualizar_projeto_db(project_id, updates: dict):
    if not conn: return False
    usuario_logado = st.session_state.get('usuario', 'Sistema') 
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, analista, etapas_concluidas, agendamento, log_agendamento, prioridade, links_referencia FROM projetos WHERE id = %s", (project_id,))
            current_data_tuple = cur.fetchone()
            if not current_data_tuple: st.error(f"Erro: Projeto com ID {project_id} não encontrado."); return False
            current_status, current_analista, current_etapas, current_agendamento, current_log, current_prioridade, current_links = current_data_tuple
            current_log = current_log or ""; current_agendamento_date = current_agendamento if isinstance(current_agendamento, date) else None
            db_updates_raw = _normalize_and_sanitize(updates); log_entries = []; hoje_str = date.today().strftime('%d/%m/%Y')
            new_status = db_updates_raw.get('status')
            if new_status is not None and new_status != current_status: log_entries.append(f"Em {hoje_str} por {usuario_logado}: Status de '{current_status or 'N/A'}' para '{new_status}'.")
            new_analista = db_updates_raw.get('analista')
            if new_analista is not None and new_analista != current_analista: log_entries.append(f"Em {hoje_str} por {usuario_logado}: Analista de '{current_analista or 'N/A'}' para '{new_analista}'.")
            new_prioridade_norm = db_updates_raw.get('prioridade'); current_prioridade_display = current_prioridade or 'Média'; new_prioridade_display = updates.get("Prioridade", 'Média') 
            if new_prioridade_norm != (current_prioridade.lower() if current_prioridade else None): log_entries.append(f"Em {hoje_str} por {usuario_logado}: Prioridade de '{current_prioridade_display}' para '{new_prioridade_display}'.")
            new_agendamento_str = db_updates_raw.get('agendamento'); new_agendamento_date = None
            if new_agendamento_str:
                try: new_agendamento_date = datetime.strptime(new_agendamento_str, '%Y-%m-%d').date()
                except ValueError: new_agendamento_date = current_agendamento_date; db_updates_raw['agendamento'] = current_agendamento_date.strftime('%Y-%m-%d') if isinstance(current_agendamento_date, date) else None
            if new_agendamento_date != current_agendamento_date:
                data_antiga_str = current_agendamento_date.strftime('%d/%m/%Y') if isinstance(current_agendamento_date, date) else "N/A"; data_nova_str = new_agendamento_date.strftime('%d/%m/%Y') if isinstance(new_agendamento_date, date) else "N/A"
                if data_antiga_str != data_nova_str: log_entries.append(f"Em {hoje_str} por {usuario_logado}: Agendamento de '{data_antiga_str}' para '{data_nova_str}'.")
            new_etapas = db_updates_raw.get('etapas_concluidas'); current_etapas_set = set(e.strip() for e in (current_etapas or "").split(',') if e.strip()); new_etapas_set = set(e.strip() for e in (new_etapas or "").split(',') if e.strip())
            if new_etapas_set != current_etapas_set:
                 concluidas = new_etapas_set - current_etapas_set; desmarcadas = current_etapas_set - new_etapas_set
                 if concluidas: log_entries.append(f"Em {hoje_str} por {usuario_logado}: Etapa(s) concluída(s): {', '.join(sorted(list(concluidas)))}.")
                 if desmarcadas: log_entries.append(f"Em {hoje_str} por {usuario_logado}: Etapa(s) desmarcada(s): {', '.join(sorted(list(desmarcadas)))}.")
            new_links = db_updates_raw.get('links_referencia')
            if new_links is not None and new_links != (current_links or ""): log_entries.append(f"Em {hoje_str} por {usuario_logado}: Links de Referência atualizados.")
            log_final = current_log; 
            if log_entries: log_final += ("\n" if current_log else "") + "\n".join(log_entries)
            db_updates_raw['log_agendamento'] = log_final if log_final else None 
            updates_final = {k: v for k, v in db_updates_raw.items() if v is not None or k == 'log_agendamento' or k == 'links_referencia'} 
            campos_sem_log = {k:v for k,v in updates_final.items() if k != 'log_agendamento'}
            if not campos_sem_log: 
                if log_entries: 
                      query_log = sql.SQL("UPDATE projetos SET log_agendamento = {} WHERE id = {}").format(sql.Placeholder(), sql.Placeholder())
                      cur.execute(query_log, (updates_final['log_agendamento'], project_id))
                else: st.toast("Nenhuma alteração detectada.", icon="ℹ️")
                st.cache_data.clear(); return True 
            set_clause = sql.SQL(', ').join(sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in updates_final.keys())
            query = sql.SQL("UPDATE projetos SET {} WHERE id = {}").format(set_clause, sql.Placeholder())
            vals = list(updates_final.values()) + [project_id]
            cur.execute(query, vals)
        st.cache_data.clear(); return True
    except Exception as e: st.toast(f"Erro CRÍTICO ao atualizar projeto ID {project_id}: {e}", icon="🔥"); conn.rollback(); return False

# (excluir_projeto_db - Sem alterações)
def excluir_projeto_db(project_id):
    if not conn: return False
    try:
        with conn.cursor() as cur: cur.execute("DELETE FROM projetos WHERE id = %s", (project_id,))
        st.cache_data.clear(); return True
    except Exception as e: st.toast(f"Erro ao excluir projeto: {e}", icon="🔥"); return False

# (carregar_config_db - Sem alterações)
@st.cache_data(ttl=600)
def carregar_config_db(tab_name):
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT dados_json FROM configuracoes WHERE aba_nome = %s"
        with conn.cursor() as cur: cur.execute(query, (tab_name.lower(),)); result = cur.fetchone()
        if result is None or result[0] is None: return pd.DataFrame()
        data = result[0]
        if isinstance(data, str): return pd.read_json(data, orient='records')
        elif isinstance(data, list): return pd.DataFrame(data)
        else: return pd.DataFrame()
    except Exception as e: st.error(f"Erro config '{tab_name}': {e}"); return pd.DataFrame()

# (salvar_config_db - Sem alterações)
def salvar_config_db(df, tab_name):
    if not conn: return False
    try:
        dados_json = df.to_json(orient='records'); sql_query = "INSERT INTO configuracoes (aba_nome, dados_json) VALUES (%s, %s) ON CONFLICT (aba_nome) DO UPDATE SET dados_json = EXCLUDED.dados_json;"
        with conn.cursor() as cur: cur.execute(sql_query, (tab_name.lower(), dados_json))
        st.cache_data.clear(); return True
    except Exception as e: st.error(f"Erro salvar config '{tab_name}': {e}"); return False

# (carregar_usuarios_db - Sem alterações)
@st.cache_data(ttl=600)
def carregar_usuarios_db():
    if not conn: return pd.DataFrame(columns=['id', 'nome', 'email', 'senha', 'permissao'])
    try:
        df = pd.read_sql_query("SELECT id, nome, email, senha, permissao FROM usuarios", conn)
        expected_cols = ['id', 'nome', 'email', 'senha', 'permissao']; 
        for col in expected_cols:
             if col not in df.columns: 
                  if col == 'permissao': df[col] = 'Usuario' 
                  else: df[col] = None 
        df['permissao'] = df['permissao'].fillna('Usuario').replace(['', None], 'Usuario')
        return df[expected_cols] 
    except Exception as e: 
        st.error(f"Erro ao carregar usuários: {e}"); 
        return pd.DataFrame(columns=['id', 'nome', 'email', 'senha', 'permissao'])

# (salvar_usuario_db - Sem alterações)
def salvar_usuario_db(df):
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios") 
            if not df.empty:
                df_to_save = df.copy()
                if 'Nome' not in df_to_save.columns: df_to_save['Nome'] = None
                if 'Email' not in df_to_save.columns: df_to_save['Email'] = None
                if 'Senha' not in df_to_save.columns: df_to_save['Senha'] = None
                if 'Permissao' not in df_to_save.columns: df_to_save['Permissao'] = 'Usuario'
                df_to_save['Permissao'] = df_to_save['Permissao'].fillna('Usuario').replace(['', None], 'Usuario')
                for _, row in df_to_save.iterrows():
                    cur.execute(
                        "INSERT INTO usuarios (nome, email, senha, permissao) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO NOTHING", 
                        (row.get('Nome'), row.get('Email'), row.get('Senha'), row.get('Permissao'))
                    )
        st.cache_data.clear(); return True
    except Exception as e: st.error(f"Erro ao salvar usuários: {e}"); return False
        
# (validar_usuario - Sem alterações)
def validar_usuario(nome, email):
    if not nome or not email: return False, None
    df = carregar_usuarios_db()
    if df.empty or 'nome' not in df.columns or 'email' not in df.columns or 'permissao' not in df.columns:
        return False, None
    cond = (df["nome"].astype(str).str.lower().eq(nome.lower()) & df["email"].astype(str).str.lower().eq(email.lower()))
    user_data = df[cond]
    if not user_data.empty:
        permissao = user_data.iloc[0]['permissao']
        return True, permissao 
    else:
        return False, None

# (generate_excel_template_bytes - Sem alterações)
def generate_excel_template_bytes():
    template_columns = ["Projeto", "Descrição", "Agência", "Técnico", "Agendamento", "Demanda", "Observação", "Analista", "Gestor", "Prioridade", "Links de Referência"] 
    df_template = pd.DataFrame(columns=template_columns)
    df_template.loc[0] = ['Ex: Projeto Exemplo', 'Descrição...', 'AG 0001', 'Nome do Técnico', '2025-11-07', 'Instalação', 'Observações...', 'Nome Analista', 'Nome Gestor', 'Média', 'http://link.com'] 
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df_template.to_excel(writer, index=False, sheet_name='Projetos')
    return output.getvalue()

# (bulk_insert_projetos_db - Sem alterações)
def bulk_insert_projetos_db(df: pd.DataFrame, usuario_logado: str):
    if not conn: return False, 0
    column_map = {'Projeto': 'projeto', 'Descrição': 'descricao', 'Agência': 'agencia', 'Técnico': 'tecnico', 'Demanda': 'demanda', 'Observação': 'observacao', 'Analista': 'analista', 'Gestor': 'gestor', 'Prioridade': 'prioridade', 'Agendamento': 'agendamento', 'Links de Referência': 'links_referencia' }
    if 'Projeto' not in df.columns or 'Agência' not in df.columns: st.error("Erro: Planilha deve conter 'Projeto' e 'Agência'."); return False, 0
    if df[['Projeto', 'Agência']].isnull().values.any(): st.error("Erro: 'Projeto' e 'Agência' não podem ser vazios."); return False, 0
    df_to_insert = df.rename(columns=column_map)
    if 'agendamento' in df_to_insert.columns: df_to_insert['agendamento'] = pd.to_datetime(df_to_insert['agendamento'], errors='coerce')
    else: df_to_insert['agendamento'] = None 
    df_to_insert['status'] = 'NÃO INICIADA'; df_to_insert['data_abertura'] = date.today() 
    if 'analista' not in df_to_insert or df_to_insert['analista'].isnull().all(): df_to_insert['analista'] = usuario_logado
    else: df_to_insert['analista'] = df_to_insert['analista'].fillna(usuario_logado)
    if 'prioridade' not in df_to_insert: df_to_insert['prioridade'] = 'Média'
    else:
        df_to_insert['prioridade'] = df_to_insert['prioridade'].astype(str).replace(['', 'nan', 'None'], 'Média').fillna('Média')
        allowed_priorities = ['alta', 'média', 'baixa']; df_to_insert['prioridade'] = df_to_insert['prioridade'].str.lower()
        invalid_priorities = df_to_insert[~df_to_insert['prioridade'].isin(allowed_priorities)]
        if not invalid_priorities.empty: st.warning(f"Prioridades inválidas (linhas: {invalid_priorities.index.tolist()}) substituídas por 'Média'."); df_to_insert.loc[invalid_priorities.index, 'prioridade'] = 'média'
        df_to_insert['prioridade'] = df_to_insert['prioridade'].str.capitalize()
    cols_to_insert = ['projeto', 'descricao', 'agencia', 'tecnico', 'status','data_abertura', 'observacao', 'demanda', 'analista', 'gestor','prioridade', 'agendamento', 'links_referencia'] 
    df_final = df_to_insert[[col for col in cols_to_insert if col in df_to_insert.columns]]
    if 'agendamento' in df_final.columns:
        df_final['agendamento'] = df_final['agendamento'].apply(lambda x: x.date() if pd.notna(x) and isinstance(x, (pd.Timestamp, datetime)) else None)
    values = []
    for record in df_final.to_records(index=False):
        processed_record = [None if pd.isna(cell) else cell for cell in record]
        values.append(tuple(processed_record))
    cols_sql = sql.SQL(", ").join(map(sql.Identifier, df_final.columns)); placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(df_final.columns))
    query = sql.SQL("INSERT INTO projetos ({}) VALUES ({})").format(cols_sql, placeholders)
    try:
        with conn.cursor() as cur: cur.executemany(query, values) 
        st.cache_data.clear(); return True, len(values)
    except Exception as e: st.error(f"Erro ao salvar no banco: {e}"); conn.rollback(); return False, 0

# (dataframe_to_excel_bytes - Sem alterações)
def dataframe_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_export = df.copy()
        cols_to_drop = ['Agendamento_str', 'sla_dias_restantes', 'proxima_etapa_calc'] 
        df_to_export.drop(columns=[col for col in cols_to_drop if col in df_to_export.columns], inplace=True, errors='ignore')
        if 'Prioridade' not in df_to_export.columns: df_to_export['Prioridade'] = 'Média' 
        if 'Links de Referência' not in df_to_export.columns: df_to_export['Links de Referência'] = None 
        df_to_export.to_excel(writer, index=False, sheet_name='Projetos')
    return output.getvalue()

# (load_css - Sem alterações)
def load_css():
   try:
        with open("style.css") as f: st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
   except FileNotFoundError: st.warning("Arquivo 'style.css' não encontrado.")

# (autenticar_direto - Sem alterações)
def autenticar_direto(email):
    df_users = carregar_usuarios_db()
    if not df_users.empty and 'email' in df_users.columns:
        user = df_users[df_users["email"].astype(str).str.lower() == str(email).lower()]
        if not user.empty: return user.iloc[0]["nome"] if "nome" in user.columns else None 
    return None

# (clean_key - Sem alterações)
def clean_key(text):
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(text).lower())

# (get_status_color - Sem alterações)
def get_status_color(status):
    s = str(status or "").strip().lower()
    if 'finalizad' in s: return "#66BB6A" 
    elif 'pendencia' in s or 'pendência' in s: return "#FFA726" 
    elif 'nao iniciad' in s or 'não iniciad' in s: return "#B0BEC5" 
    elif 'cancelad' in s: return "#EF5350" 
    elif 'pausad' in s: return "#FFEE58" 
    else: return "#64B5F6"  

# (calcular_sla - Sem alterações)
def calcular_sla(projeto_row, df_sla):
    data_agendamento = pd.to_datetime(projeto_row.get("Agendamento"), errors='coerce')
    data_finalizacao = pd.to_datetime(projeto_row.get("Data de Finalização"), errors='coerce')
    projeto_nome = str(projeto_row.get("Projeto", "")).upper(); demanda = projeto_row.get("Demanda", "")
    if pd.isna(data_agendamento): return "SLA: N/D", "gray"
    if df_sla.empty: return "SLA: N/A", "gray"
    if "Nome do Projeto" not in df_sla.columns or "Demanda" not in df_sla.columns or "Prazo (dias)" not in df_sla.columns:
         st.warning("Arquivo SLA sem colunas esperadas."); return "SLA: Config Inválida", "gray"
    df_sla_upper = df_sla.copy(); df_sla_upper["Nome do Projeto"] = df_sla_upper["Nome do Projeto"].astype(str).str.upper(); df_sla_upper["Demanda"] = df_sla_upper["Demanda"].astype(str)
    rule = df_sla_upper[(df_sla_upper["Nome do Projeto"] == projeto_nome) & (df_sla_upper["Demanda"] == str(demanda))]
    if rule.empty: rule = df_sla_upper[(df_sla_upper["Nome do Projeto"] == projeto_nome) & (df_sla_upper["Demanda"].isin(['', 'nan', 'None']))]
    if rule.empty: return "SLA: N/A (Regra ñ enc.)", "gray"
    try: prazo_raw = rule.iloc[0]["Prazo (dias)"]; prazo_dias = int(float(prazo_raw)) 
    except (ValueError, TypeError, IndexError): return "SLA: Inválido", "red"
    start_date = data_agendamento.date(); hoje = date.today() 
    if pd.notna(data_finalizacao):
        end_date = data_finalizacao.date(); dias_corridos = (end_date - start_date).days
        if dias_corridos <= prazo_dias: return f"Finalizado Prazo ({dias_corridos}d)", "#66BB6A" 
        else: atraso = dias_corridos - prazo_dias; return f"Finalizado Atraso ({atraso}d)", "#EF5350" 
    else: 
        dias_corridos = (hoje - start_date).days; dias_restantes = prazo_dias - dias_corridos
        if dias_restantes < 0: return f"Atrasado {-dias_restantes}d", "#EF5350" 
        elif dias_restantes == 0: return "SLA Vence Hoje!", "#FFA726" 
        else: return f"SLA: {dias_restantes}d restantes", "#66BB6F" 

# (get_color_for_name - Sem alterações)
def get_color_for_name(name_str):
    """Gera uma cor consistente de uma lista com base em um nome."""
    COLORS_LIST = ["#D32F2F", "#1976D2", "#388E3C", "#F57C00", "#7B1FA2", "#00796B", "#C2185B", "#5D4037", "#455A64"]
    if name_str is None or name_str == "N/A": return "#555" 
    name_normalized = str(name_str).strip().upper() 
    if not name_normalized: return "#555"
    try:
        hash_val = hash(name_normalized); color_index = hash_val % len(COLORS_LIST)
        return COLORS_LIST[color_index]
    except Exception: return "#555"
    
    
# --- Funções para a Tabela de Chamados ---
@st.cache_data(ttl=60)
def carregar_chamados_db(agencia_id_filtro=None):
    """ Carrega chamados, opcionalmente filtrados por ID de agência. """
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT * FROM chamados"
        params = []
        if agencia_id_filtro and agencia_id_filtro != "Todas":
            query += " WHERE agencia_id = %s"
            params.append(agencia_id_filtro)
        query += " ORDER BY data_abertura DESC"
        df = pd.read_sql_query(query, conn, params=params if params else None)
        rename_map = {
            'id': 'ID', 'chamado_id': 'Nº Chamado', 'agencia_id': 'Cód. Agência', 
            'agencia_nome': 'Nome Agência', 'agencia_uf': 'UF', 'servico': 'Serviço',
            'projeto_nome': 'Projeto', 'data_agendamento': 'Agendamento',
            'sistema': 'Sistema', 'cod_equipamento': 'Cód. Equip.', 'nome_equipamento': 'Equipamento',
            'quantidade': 'Qtd.', 'gestor': 'Gestor',
            'descricao': 'Descrição', 'data_abertura': 'Abertura', 'data_fechamento': 'Fechamento',
            'status_chamado': 'Status', 'valor_chamado': 'Valor (R$)',
            'status_financeiro': 'Status Financeiro'
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        return df
    except Exception as e:
        st.error(f"Erro ao carregar chamados: {e}"); return pd.DataFrame()

# --- >>> AQUI ESTÁ A CORREÇÃO FINAL <<< ---
def bulk_insert_chamados_db(df: pd.DataFrame):
    """ Importa um DataFrame de chamados para o banco (UPSERT). """
    if not conn: return False, 0
    
    column_map = {
        'Chamado': 'chamado_id', 'Codigo_Ponto': 'agencia_id', 'Nome': 'agencia_nome',
        'UF': 'agencia_uf', 'Servico': 'servico', 'Projeto': 'projeto_nome',
        'Data_Agendamento': 'data_agendamento', 'Tipo_De_Solicitacao': 'sistema',
        'Sistema': 'cod_equipamento', 'Codigo_Equipamento': 'nome_equipamento',
        'Nome_Equipamento': 'quantidade', 'Substitui_Outro_Equipamento_(Sim/Não)': 'gestor'
        # Você pode adicionar mais colunas do Excel aqui se precisar
        # 'Descricao': 'descricao', 
        # 'Data_Abertura': 'data_abertura',
        # 'Data_Fechamento': 'data_fechamento',
        # 'Status_Chamado': 'status_chamado',
        # 'Valor_Chamado': 'valor_chamado'
    }
    
    df_to_insert = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    if 'chamado_id' not in df_to_insert.columns:
        st.error("Erro: A planilha deve conter a coluna 'Chamado' (ID do chamado).")
        return False, 0
    if 'agencia_id' not in df_to_insert.columns:
        st.error("Erro: A planilha deve conter a coluna 'Codigo_Ponto' (ID da Agência).")
        return False, 0

    # --- Tratamento de Tipos ---
    cols_data = ['data_abertura', 'data_fechamento', 'data_agendamento']
    for col in cols_data:
        if col in df_to_insert.columns:
            df_to_insert[col] = pd.to_datetime(df_to_insert[col], errors='coerce')
        else:
            df_to_insert[col] = None 

    if 'valor_chamado' in df_to_insert.columns:
         df_to_insert['valor_chamado'] = pd.to_numeric(df_to_insert['valor_chamado'], errors='coerce').fillna(0.0)
    if 'quantidade' in df_to_insert.columns:
         df_to_insert['quantidade'] = pd.to_numeric(df_to_insert['quantidade'], errors='coerce').fillna(0).astype('Int64') # Usa Int64 para aceitar nulos

    # Lista final de colunas do BD
    cols_to_insert = [
        'chamado_id', 'agencia_id', 'agencia_nome', 'agencia_uf', 'servico', 'projeto_nome', 
        'data_agendamento', 'sistema', 'cod_equipamento', 'nome_equipamento', 'quantidade', 'gestor',
        'descricao', 'data_abertura', 'data_fechamento', 'status_chamado', 'valor_chamado'
    ]
                      
    df_final = df_to_insert[[col for col in cols_to_insert if col in df_to_insert.columns]]
    
    # --- Conversão de Tipos para o Banco (Robusta) ---
    values = []
    for record in df_final.to_records(index=False):
        processed_record = []
        for cell in record:
            if pd.isna(cell):
                processed_record.append(None) # Converte NaT, NaN, etc. para None
            elif isinstance(cell, (np.int64, np.int32, np.int16)):
                processed_record.append(int(cell)) # Converte numpy int para python int
            elif isinstance(cell, (np.float64, np.float32)):
                processed_record.append(float(cell)) # Converte numpy float para python float
            elif isinstance(cell, (pd.Timestamp, datetime)):
                processed_record.append(cell.date()) # Converte datetime para date
            else:
                processed_record.append(cell) # Mantém outros tipos (str, date, etc.)
        values.append(tuple(processed_record))
    # --- Fim da Correção ---
    
    cols_sql = sql.SQL(", ").join(map(sql.Identifier, df_final.columns)); placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(df_final.columns))
    
    update_clause = sql.SQL(', ').join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
        for col in df_final.columns if col != 'chamado_id' 
    )
    query = sql.SQL("INSERT INTO chamados ({}) VALUES ({}) ON CONFLICT (chamado_id) DO UPDATE SET {}").format(cols_sql, placeholders, update_clause)

    try:
        with conn.cursor() as cur: cur.executemany(query, values) 
        st.cache_data.clear(); return True, len(values)
    except Exception as e: 
        st.error(f"Erro ao salvar chamados no banco: {e}"); conn.rollback(); return False, 0
