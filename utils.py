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

# (image_to_base64 - Sem alterações)
def image_to_base64(image):
    """Converte uma imagem PIL em string Base64 para exibição no Streamlit."""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# (get_db_connection - Sem alterações)
@st.cache_resource
def get_db_connection():
    """Cria e gerencia a conexão com o banco de dados PostgreSQL."""
    try:
        secrets = st.secrets["postgres"]
        conn = psycopg2.connect(
            host=secrets["PGHOST"],
            port=secrets["PGPORT"],
            user=secrets["PGUSER"],
            password=secrets["PGPASSWORD"],
            dbname=secrets["PGDATABASE"]
        )
        conn.autocommit = True 
        return conn
    except KeyError as e:
        st.error(f"Erro Crítico: Credencial '{e}' não encontrada nos Secrets.")
        return None
    except Exception as e:
        st.error(f"Erro ao conectar ao DB: {e}")
        return None

conn = get_db_connection() 

# (criar_tabelas_iniciais - Sem alterações, MAS lembre-se da coluna 'prioridade')
def criar_tabelas_iniciais():
    """Cria as tabelas se não existirem."""
    if not conn: return
    try:
        with conn.cursor() as cur:
            # Adicione manualmente: ALTER TABLE projetos ADD COLUMN prioridade TEXT DEFAULT 'Média';
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projetos (
                    id SERIAL PRIMARY KEY, projeto TEXT, descricao TEXT, agencia TEXT, 
                    tecnico TEXT, status TEXT, agendamento DATE, data_abertura DATE, 
                    data_finalizacao DATE, observacao TEXT, demanda TEXT, log_agendamento TEXT,
                    respostas_perguntas JSONB, etapas_concluidas TEXT, analista TEXT, 
                    gestor TEXT, prioridade TEXT DEFAULT 'Média' 
                );
            """)
            cur.execute("CREATE TABLE IF NOT EXISTS configuracoes (aba_nome TEXT PRIMARY KEY, dados_json JSONB);")
            cur.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nome TEXT, email TEXT UNIQUE, senha TEXT);")
    except Exception as e:
        st.error(f"Erro ao criar/verificar tabelas: {e}")

# --- Funções do Banco (Projetos) ---

def _normalize_and_sanitize(data_dict: dict):
    normalized = {}
    for key, value in data_dict.items():
        k = str(key).lower() # Converte para minúsculo

        # --- CORREÇÃO: Substituição de acentos aprimorada ---
        k = re.sub(r'[áàâãä]', 'a', k)
        k = re.sub(r'[éèêë]', 'e', k)
        k = re.sub(r'[íìîï]', 'i', k)
        k = re.sub(r'[óòôõö]', 'o', k)
        k = re.sub(r'[úùûü]', 'u', k)
        k = re.sub(r'[ç]', 'c', k)

        # Remove caracteres especiais restantes (exceto underline) e substitui espaços
        k = re.sub(r'[^a-z0-9_ ]', '', k) # Remove outros caracteres não alfanuméricos
        k = k.replace(' de ', ' ').replace(' ', '_') # Substitui espaços por underline

        # Sanitiza o valor (como antes)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            sanitized_value = None
        elif isinstance(value, (datetime, date)):
            sanitized_value = value.strftime('%Y-%m-%d')
        elif k == 'prioridade' and value == 'N/A': 
             sanitized_value = None 
        else:
            sanitized_value = str(value)
            
        normalized[k] = sanitized_value
    return normalized

# (carregar_projetos_db - Query corrigida, renomeia prioridade)
@st.cache_data(ttl=60) 
def carregar_projetos_db():
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM projetos ORDER BY id DESC", conn) 
        rename_map = {
            'id': 'ID', 'descricao': 'Descrição', 'agencia': 'Agência', 'tecnico': 'Técnico',
            'observacao': 'Observação', 'data_abertura': 'Data de Abertura','data_finalizacao': 'Data de Finalização', 
            'log_agendamento': 'Log Agendamento','etapas_concluidas': 'Etapas Concluidas', 
            'projeto': 'Projeto', 'status': 'Status','agendamento': 'Agendamento', 
            'demanda': 'Demanda', 'analista': 'Analista', 'gestor': 'Gestor', 'prioridade': 'Prioridade' 
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        if 'Agendamento' in df.columns:
            df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
        if 'Prioridade' in df.columns:
             df['Prioridade'] = df['Prioridade'].fillna('Média').replace(['', None], 'Média')
        else:
             df['Prioridade'] = 'Média' 
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos do DB: {e}") 
        return pd.DataFrame() 

# (carregar_projetos_sem_agendamento_db - Query corrigida, renomeia prioridade)
@st.cache_data(ttl=60)
def carregar_projetos_sem_agendamento_db():
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM projetos WHERE agendamento IS NULL ORDER BY id DESC", conn)
        rename_map = {
            'id': 'ID', 'descricao': 'Descrição', 'agencia': 'Agência', 'tecnico': 'Técnico',
            'observacao': 'Observação', 'data_abertura': 'Data de Abertura','data_finalizacao': 'Data de Finalização', 
            'log_agendamento': 'Log Agendamento','etapas_concluidas': 'Etapas Concluidas', 
            'projeto': 'Projeto', 'status': 'Status','agendamento': 'Agendamento', 
            'demanda': 'Demanda', 'analista': 'Analista', 'gestor': 'Gestor', 'prioridade': 'Prioridade' 
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        if 'Agendamento' in df.columns:
            df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
        if 'Prioridade' in df.columns:
             df['Prioridade'] = df['Prioridade'].fillna('Média').replace(['', None], 'Média')
        else:
             df['Prioridade'] = 'Média'
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos do backlog: {e}")
        return pd.DataFrame()

# (adicionar_projeto_db - Inclui Prioridade)
def adicionar_projeto_db(data: dict):
    if not conn: return False
    try:
        if "Prioridade" not in data or data["Prioridade"] == "N/A":
            data["Prioridade"] = "Média" 
        db_data = _normalize_and_sanitize(data)
        cols_with_values = {k: v for k, v in db_data.items() if v is not None}
        if not cols_with_values: 
            st.toast("Erro: Nenhum dado válido para adicionar.", icon="🔥"); return False
        cols = cols_with_values.keys(); vals = list(cols_with_values.values())
        query = sql.SQL("INSERT INTO projetos ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cols)),
            sql.SQL(', ').join(sql.Placeholder() * len(cols)))
        with conn.cursor() as cur: cur.execute(query, vals)
        st.cache_data.clear(); return True
    except Exception as e:
        st.toast(f"Erro ao adicionar projeto: {e}", icon="🔥"); return False

# (atualizar_projeto_db - ATUALIZADO com Log Aprimorado, Prioridade e Correção de Indentação/strftime)
def atualizar_projeto_db(project_id, updates: dict):
    if not conn: return False
    
    usuario_logado = st.session_state.get('usuario', 'Sistema') 
    
    try:
        with conn.cursor() as cur:
            # 1. Buscar dados atuais
            cur.execute("""
                SELECT status, analista, etapas_concluidas, agendamento, log_agendamento, prioridade 
                FROM projetos WHERE id = %s
            """, (project_id,))
            current_data_tuple = cur.fetchone()
            if not current_data_tuple:
                st.error(f"Erro: Projeto com ID {project_id} não encontrado."); return False

            current_status, current_analista, current_etapas, current_agendamento, current_log, current_prioridade = current_data_tuple
            current_log = current_log or "" 
            current_agendamento_date = current_agendamento if isinstance(current_agendamento, date) else None
            current_prioridade_db_val = current_prioridade # Valor como está no BD (pode ser None)

            # Prepara dados da atualização
            db_updates_raw = _normalize_and_sanitize(updates)
            
            # --- Geração do Log ---
            log_entries = []
            hoje_str = date.today().strftime('%d/%m/%Y')

            # Compara Status
            new_status = db_updates_raw.get('status')
            if new_status is not None and new_status != current_status:
                log_entries.append(f"Em {hoje_str} por {usuario_logado}: Status de '{current_status or 'N/A'}' para '{new_status}'.")

            # Compara Analista
            new_analista = db_updates_raw.get('analista')
            if new_analista is not None and new_analista != current_analista:
                 log_entries.append(f"Em {hoje_str} por {usuario_logado}: Analista de '{current_analista or 'N/A'}' para '{new_analista}'.")

            # Compara Prioridade
            new_prioridade_norm = db_updates_raw.get('prioridade') # 'baixa', 'media', 'alta' ou None
            current_prioridade_display = current_prioridade or 'Média' 
            new_prioridade_display = updates.get("Prioridade", 'Média') 
            # Compara valor normalizado (None se N/A) com valor do BD (None ou texto)
            if new_prioridade_norm != (current_prioridade.lower() if current_prioridade else None): 
                 log_entries.append(f"Em {hoje_str} por {usuario_logado}: Prioridade de '{current_prioridade_display}' para '{new_prioridade_display}'.")

            # Compara Agendamento (com checagem de tipo)
            new_agendamento_str = db_updates_raw.get('agendamento') # 'YYYY-MM-DD' ou None
            new_agendamento_date = None
            if new_agendamento_str:
                try:
                    new_agendamento_date = datetime.strptime(new_agendamento_str, '%Y-%m-%d').date()
                except ValueError: 
                     st.warning(f"Formato inválido para Agendamento '{new_agendamento_str}'.")
                     # Mantém o valor antigo se o novo for inválido
                     # E garante que db_updates_raw['agendamento'] seja None para não salvar data inválida
                     new_agendamento_date = current_agendamento_date 
                     db_updates_raw['agendamento'] = current_agendamento_date.strftime('%Y-%m-%d') if isinstance(current_agendamento_date, date) else None


            if new_agendamento_date != current_agendamento_date:
                data_antiga_str = current_agendamento_date.strftime('%d/%m/%Y') if isinstance(current_agendamento_date, date) else "N/A"
                data_nova_str = new_agendamento_date.strftime('%d/%m/%Y') if isinstance(new_agendamento_date, date) else "N/A"
                if data_antiga_str != data_nova_str: # Loga apenas se a representação mudar
                    log_entries.append(f"Em {hoje_str} por {usuario_logado}: Agendamento de '{data_antiga_str}' para '{data_nova_str}'.")

            # Compara Etapas Concluídas
            new_etapas = db_updates_raw.get('etapas_concluidas'); 
            current_etapas_set = set(e.strip() for e in (current_etapas or "").split(',') if e.strip()); 
            new_etapas_set = set(e.strip() for e in (new_etapas or "").split(',') if e.strip())
            if new_etapas_set != current_etapas_set:
                 concluidas = new_etapas_set - current_etapas_set; desmarcadas = current_etapas_set - new_etapas_set
                 if concluidas: log_entries.append(f"Em {hoje_str} por {usuario_logado}: Etapa(s) concluída(s): {', '.join(sorted(list(concluidas)))}.")
                 if desmarcadas: log_entries.append(f"Em {hoje_str} por {usuario_logado}: Etapa(s) desmarcada(s): {', '.join(sorted(list(desmarcadas)))}.")
            
            # Monta log final e adiciona aos updates
            log_final = current_log; 
            if log_entries: log_final += ("\n" if current_log else "") + "\n".join(log_entries)
            db_updates_raw['log_agendamento'] = log_final if log_final else None 

            # Prepara query SQL
            updates_final = {k: v for k, v in db_updates_raw.items() if v is not None or k == 'log_agendamento'}
            
            # Se SÓ o log mudou (ou nada mudou mas o log foi gerado), atualiza só o log
            campos_sem_log = {k:v for k,v in updates_final.items() if k != 'log_agendamento'}
            if not campos_sem_log: 
                if log_entries: # Salva só o log se só ele mudou
                      query_log = sql.SQL("UPDATE projetos SET log_agendamento = {} WHERE id = {}").format(sql.Placeholder(), sql.Placeholder())
                      cur.execute(query_log, (updates_final['log_agendamento'], project_id))
                else: st.toast("Nenhuma alteração detectada.", icon="ℹ️")
                st.cache_data.clear(); return True 
            
            # Se outros campos mudaram, atualiza tudo
            set_clause = sql.SQL(', ').join(sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in updates_final.keys())
            query = sql.SQL("UPDATE projetos SET {} WHERE id = {}").format(set_clause, sql.Placeholder())
            vals = list(updates_final.values()) + [project_id]
            cur.execute(query, vals)

        st.cache_data.clear() 
        return True
        
    except Exception as e:
        st.toast(f"Erro CRÍTICO ao atualizar projeto ID {project_id}: {e}", icon="🔥")
        # print(f"Erro detalhado (atualizar_projeto_db): {e}") # Debug
        conn.rollback() # Garante rollback em caso de erro na transação
        return False


# (excluir_projeto_db - Sem alterações)
def excluir_projeto_db(project_id):
    # ... (código original) ...
    if not conn: return False
    try:
        with conn.cursor() as cur: cur.execute("DELETE FROM projetos WHERE id = %s", (project_id,))
        st.cache_data.clear(); return True
    except Exception as e:
        st.toast(f"Erro ao excluir projeto: {e}", icon="🔥"); return False


# --- Funções do Banco (Configurações e Usuários) ---
# (carregar_config_db - Sem alterações)
@st.cache_data(ttl=600)
def carregar_config_db(tab_name):
    # ... (código original) ...
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
    # ... (código original) ...
    if not conn: return False
    try:
        dados_json = df.to_json(orient='records'); sql_query = "INSERT INTO configuracoes (aba_nome, dados_json) VALUES (%s, %s) ON CONFLICT (aba_nome) DO UPDATE SET dados_json = EXCLUDED.dados_json;"
        with conn.cursor() as cur: cur.execute(sql_query, (tab_name.lower(), dados_json))
        st.cache_data.clear(); return True
    except Exception as e: st.error(f"Erro salvar config '{tab_name}': {e}"); return False

# (carregar_usuarios_db - Sem alterações)
@st.cache_data(ttl=600)
def carregar_usuarios_db():
    # ... (código original) ...
    if not conn: return pd.DataFrame(columns=['id', 'nome', 'email', 'senha'])
    try:
        df = pd.read_sql_query("SELECT id, nome, email, senha FROM usuarios", conn)
        expected_cols = ['id', 'nome', 'email', 'senha']; 
        for col in expected_cols:
             if col not in df.columns: df[col] = None 
        return df[expected_cols] 
    except Exception as e: st.error(f"Erro ao carregar usuários: {e}"); return pd.DataFrame(columns=['id', 'nome', 'email', 'senha'])

# (salvar_usuario_db - Sem alterações)
def salvar_usuario_db(df):
    # ... (código original) ...
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios") 
            if not df.empty:
                df_to_save = df.copy()
                if 'Nome' not in df_to_save.columns: df_to_save['Nome'] = None
                if 'Email' not in df_to_save.columns: df_to_save['Email'] = None
                if 'Senha' not in df_to_save.columns: df_to_save['Senha'] = None
                for _, row in df_to_save.iterrows():
                    cur.execute("INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING", (row.get('Nome'), row.get('Email'), row.get('Senha')))
        st.cache_data.clear(); return True
    except Exception as e: st.error(f"Erro ao salvar usuários: {e}"); return False
        
# (validar_usuario - Sem alterações)
def validar_usuario(nome, email):
    # ... (código original) ...
    if not nome or not email: return False 
    df = carregar_usuarios_db()
    if df.empty or 'nome' not in df.columns or 'email' not in df.columns: return False
    cond = (df["nome"].astype(str).str.lower().eq(nome.lower()) & df["email"].astype(str).str.lower().eq(email.lower())); return cond.any()

# --- Funções de Importação/Exportação ---
# (generate_excel_template_bytes - Com Prioridade)
def generate_excel_template_bytes():
    template_columns = ["Projeto", "Descrição", "Agência", "Técnico", "Demanda", "Observação", "Analista", "Gestor", "Prioridade"] 
    df_template = pd.DataFrame(columns=template_columns)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Projetos')
    return output.getvalue()

# (bulk_insert_projetos_db - Com Prioridade)
def bulk_insert_projetos_db(df: pd.DataFrame, usuario_logado: str):
    # ... (código original com prioridade) ...
    if not conn: return False, 0
    column_map = {'Projeto': 'projeto', 'Descrição': 'descricao', 'Agência': 'agencia', 'Técnico': 'tecnico','Demanda': 'demanda', 'Observação': 'observacao', 'Analista': 'analista', 'Gestor': 'gestor','Prioridade': 'prioridade'}
    if 'Projeto' not in df.columns or 'Agência' not in df.columns: st.error("Erro: Planilha deve conter 'Projeto' e 'Agência'."); return False, 0
    if df[['Projeto', 'Agência']].isnull().any().any(): st.error("Erro: 'Projeto' e 'Agência' não podem ser vazios."); return False, 0
    df_to_insert = df.rename(columns=column_map)
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
    cols_to_insert = ['projeto', 'descricao', 'agencia', 'tecnico', 'status','data_abertura', 'observacao', 'demanda', 'analista', 'gestor','prioridade'] 
    df_final = df_to_insert[[col for col in cols_to_insert if col in df_to_insert.columns]]
    values = [tuple(None if pd.isna(x) else x for x in record) for record in df_final.to_records(index=False)]
    cols_sql = sql.SQL(", ").join(map(sql.Identifier, df_final.columns)); placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(df_final.columns))
    query = sql.SQL("INSERT INTO projetos ({}) VALUES ({})").format(cols_sql, placeholders)
    try:
        with conn.cursor() as cur: cur.executemany(query, values) 
        st.cache_data.clear(); return True, len(values)
    except Exception as e: st.error(f"Erro bulk insert: {e}"); conn.rollback(); return False, 0


# (dataframe_to_excel_bytes - Com Prioridade)
def dataframe_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_export = df.copy()
        cols_to_drop = ['Agendamento_str', 'sla_dias_restantes'] 
        df_to_export.drop(columns=[col for col in cols_to_drop if col in df_to_export.columns], inplace=True, errors='ignore')
        if 'Prioridade' not in df_to_export.columns: df_to_export['Prioridade'] = 'Média' 
        df_to_export.to_excel(writer, index=False, sheet_name='Projetos')
    return output.getvalue()


# --- Funções Utilitárias ---
# (load_css - Sem alterações)
def load_css():
   try:
        with open("style.css") as f: st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
   except FileNotFoundError: st.warning("Arquivo 'style.css' não encontrado.")

# (autenticar_direto - Sem alterações)
def autenticar_direto(email):
    # ... (código original) ...
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
    # ... (código original) ...
    s = str(status or "").strip().lower()
    if 'finalizad' in s: return "#66BB6A" 
    elif 'pendencia' in s or 'pendência' in s: return "#FFA726" 
    elif 'nao iniciad' in s or 'não iniciad' in s: return "#B0BEC5" 
    elif 'cancelad' in s: return "#EF5350" 
    elif 'pausad' in s: return "#FFEE58" 
    else: return "#64B5F6"  

# (calcular_sla - Sem alterações)
def calcular_sla(projeto_row, df_sla):
    # ... (código original) ...
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

