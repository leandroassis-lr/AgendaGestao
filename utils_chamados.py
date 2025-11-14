import streamlit as st
import pandas as pd
from datetime import date, datetime 
import re
import html
import psycopg2
from psycopg2 import sql
import numpy as np 

# --- 1. GERENCIAMENTO DE CONEXÃO ROBUSTO ---

@st.cache_resource
def _get_cached_connection():
    """
    Cria a conexão bruta e armazena em cache. 
    NÃO chame esta função diretamente. Use get_valid_conn().
    """
    try:
        secrets = st.secrets["postgres"]
        conn = psycopg2.connect(
            host=secrets["PGHOST"], 
            port=secrets["PGPORT"], 
            user=secrets["PGUSER"], 
            password=secrets["PGPASSWORD"], 
            dbname=secrets["PGDATABASE"],
            connect_timeout=10
        )
        conn.autocommit = False 
        return conn
    except Exception as e: 
        st.error(f"Erro ao conectar ao PostgreSQL: {e}")
        return None

def get_valid_conn():
    """
    Verifica se a conexão em cache está ativa. 
    Se caiu (closed != 0), limpa o cache e reconecta.
    """
    conn = _get_cached_connection()
    
    # Se a conexão for None ou estiver fechada (0 = aberta, >0 = fechada)
    if conn is None or conn.closed != 0:
        st.cache_resource.clear() # Limpa o cache antigo
        conn = _get_cached_connection() # Tenta criar nova
        
    return conn

# --- VARIÁVEL GLOBAL DE COLUNAS ---
colunas_necessarias = {
    'agencia_id': 'TEXT', 'agencia_nome': 'TEXT', 'agencia_uf': 'TEXT',
    'servico': 'TEXT', 'projeto_nome': 'TEXT', 'data_agendamento': 'DATE',
    'sistema': 'TEXT', 'cod_equipamento': 'TEXT', 'nome_equipamento': 'TEXT',
    'quantidade': 'INTEGER', 'gestor': 'TEXT', 
    'data_abertura': 'DATE', 'data_fechamento': 'DATE',
    'status_chamado': 'TEXT', 'valor_chamado': 'NUMERIC(10, 2) DEFAULT 0.00',
    'status_financeiro': "TEXT DEFAULT 'Pendente'",
    'observacao': 'TEXT', 
    'log_chamado': 'TEXT',
    'analista': 'TEXT',
    'tecnico': 'TEXT',
    'prioridade': "TEXT DEFAULT 'Média'",
    'link_externo': 'TEXT',
    'protocolo': 'TEXT',
    'numero_pedido': 'TEXT',
    'data_envio': 'DATE',
    'observacao_equipamento': 'TEXT',
    'prazo': 'TEXT',
    'descricao_projeto': 'TEXT', 
    'observacao_pendencias': 'TEXT',
    'sub_status': 'TEXT'
}

# --- 2. FUNÇÃO PARA CRIAR/ATUALIZAR A TABELA ---
def criar_tabela_chamados():
    """Cria a tabela e verifica colunas."""
    global colunas_necessarias
    conn = get_valid_conn() # Pega conexão validada
    if not conn: return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chamados (
                    id SERIAL PRIMARY KEY,
                    chamado_id TEXT UNIQUE
                );
            """)
            
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'chamados';")
            colunas_existentes = [row[0] for row in cur.fetchall()]
            
            for coluna, tipo_coluna in colunas_necessarias.items():
                if coluna not in colunas_existentes:
                    # st.warning(f"Atualizando BD: Adicionando '{coluna}'...") # Comentado para limpar a tela
                    cur.execute(f"ALTER TABLE chamados ADD COLUMN {coluna} {tipo_coluna};")
            conn.commit()
            
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao verificar tabela: {e}")


# --- 3. FUNÇÃO PARA CARREGAR CHAMADOS ---
@st.cache_data(ttl=60)
def carregar_chamados_db(agencia_id_filtro=None):
    """ Carrega chamados com tratamento de queda de conexão. """
    # Não usamos get_valid_conn aqui diretamente pois st.cache_data não gosta de objetos de conexão
    # Precisamos recriar a lógica para garantir que o dado venha fresco
    
    conn = get_valid_conn()
    if not conn: return pd.DataFrame()

    try:
        query = "SELECT * FROM chamados"
        params = []
        if agencia_id_filtro and agencia_id_filtro != "Todas":
            match = re.search(r'(\d+)', agencia_id_filtro)
            agencia_id_num = match.group(1).lstrip('0') if match else agencia_id_filtro
            query += " WHERE agencia_id = %s"
            params.append(agencia_id_num)
        query += " ORDER BY data_agendamento DESC, id DESC"
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        
        rename_map = {
            'id': 'ID', 'chamado_id': 'Nº Chamado', 'agencia_id': 'Cód. Agência', 
            'agencia_nome': 'Nome Agência', 'agencia_uf': 'UF', 'servico': 'Serviço',
            'projeto_nome': 'Projeto', 'data_agendamento': 'Agendamento',
            'sistema': 'Sistema', 'cod_equipamento': 'Cód. Equip.', 'nome_equipamento': 'Equipamento',
            'quantidade': 'Qtd.', 'gestor': 'Gestor',
            'data_abertura': 'Abertura', 'data_fechamento': 'Fechamento',
            'status_chamado': 'Status', 'valor_chamado': 'Valor (R$)',
            'status_financeiro': 'Status Financeiro',
            'observacao': 'Observação', 'log_chamado': 'Log do Chamado',
            'analista': 'Analista', 'tecnico': 'Técnico', 'prioridade': 'Prioridade',
            'link_externo': 'Link Externo', 'protocolo': 'Nº Protocolo',
            'numero_pedido': 'Nº Pedido', 'data_envio': 'Data Envio',
            'observacao_equipamento': 'Obs. Equipamento',
            'prazo': 'Prazo', 'descricao_projeto': 'Descrição',
            'observacao_pendencias': 'Observações e Pendencias',
            'sub_status': 'Sub-Status'
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        
        # Colunas garantidas
        cols_text = ['Analista', 'Técnico', 'Link Externo', 'Nº Protocolo', 'Nº Pedido', 'Obs. Equipamento', 'Prazo', 'Descrição', 'Observações e Pendencias', 'Sub-Status']
        for col in cols_text:
             if col not in df.columns: df[col] = None
        
        if 'Prioridade' not in df.columns: df['Prioridade'] = 'Média'
        if 'Data Envio' not in df.columns: df['Data Envio'] = pd.NaT

        return df
    except Exception as e:
        # Se der erro de conexão aqui, forçamos limpeza do cache de conexão para a próxima tentativa
        st.cache_resource.clear()
        st.error(f"Erro ao ler banco (tente recarregar a página): {e}")
        return pd.DataFrame()

# --- 4. FUNÇÃO PARA IMPORTAR CHAMADOS ---

def bulk_insert_chamados_db(df: pd.DataFrame):
    """ Importa um DataFrame (UPSERT) lendo pelos Nomes de Cabeçalho. """
    conn = get_valid_conn()
    if not conn: return False, 0
    
    # Mapeia do "Nome no Excel" (em maiúsculo) para o "Nome no BD"
    NEW_COLUMN_MAP = {
        'CHAMADO': 'chamado_id',
        'N° AGENCIA': 'agencia_id',
        'NOME AGÊNCIA': 'agencia_nome',
        'UF': 'agencia_uf',
        'TIPO DO SERVIÇO': 'servico',
        'NOME DO PROJETO': 'projeto_nome',
        'AGENDAMENTO': 'data_agendamento',
        
        # Mapeamento do Equipamento (baseado na sua lista)
        'TIPO DE SOLICITAÇÃO': 'sistema',           # Ex: "Sistema de Alarme"
        'CODIGO': 'cod_equipamento',                # Ex: "437"
        'DESCRIÇÃO EQUIPAMENTO': 'nome_equipamento', # Ex: "SENSOR..."
        
        'QTD': 'quantidade',
        'GESTOR ITAU': 'gestor',
        'RESPONSÁVEL': 'analista'            
    }

    # Renomear colunas do DataFrame baseado no mapa (de forma robusta)
    df_renamed = df.copy()
    # Normaliza os cabeçalhos (Tira espaços, põe em maiúsculo)
    df_renamed.columns = [str(col).strip().upper() for col in df_renamed.columns]
    
    # Filtra o mapa para conter apenas colunas que realmente existem no DF
    headers_no_excel = df_renamed.columns
    map_para_renomear = {
        excel_header: db_col 
        for excel_header, db_col in NEW_COLUMN_MAP.items() 
        if excel_header in headers_no_excel
    }
    
    df_to_insert = df_renamed.rename(columns=map_para_renomear)

    # Verificar colunas obrigatórias
    if 'chamado_id' not in df_to_insert.columns:
        st.error("Erro: A planilha deve conter um cabeçalho 'CHAMADO'.")
        return False, 0
    if 'agencia_id' not in df_to_insert.columns:
        st.error("Erro: A planilha deve conter um cabeçalho 'N° AGENCIA'.")
        return False, 0

    # O resto da função (processamento de datas, upsert) continua igual...
    df_to_insert['data_abertura'] = date.today()
    
    cols_data = ['data_abertura', 'data_fechamento', 'data_agendamento']
    for col in cols_data:
        if col in df_to_insert.columns:
            df_to_insert[col] = pd.to_datetime(df_to_insert[col], errors='coerce', dayfirst=True)
        else:
            df_to_insert[col] = None 

    if 'valor_chamado' in df_to_insert.columns:
         df_to_insert['valor_chamado'] = pd.to_numeric(df_to_insert['valor_chamado'], errors='coerce').fillna(0.0)
    if 'quantidade' in df_to_insert.columns:
         df_to_insert['quantidade'] = pd.to_numeric(df_to_insert['quantidade'], errors='coerce').astype('Int64')

    # Lista de colunas do DB que queremos inserir/atualizar
    # (Pega da variável global 'colunas_necessarias' definida no topo do utils_chamados)
    global colunas_necessarias
    cols_db_validas = list(colunas_necessarias.keys()) + ['chamado_id']
    
    # Pega apenas as colunas que agora têm nomes de DB válidos
    df_final = df_to_insert[[col for col in df_to_insert.columns if col in cols_db_validas]]
    
    values = []
    for record in df_final.to_records(index=False):
        processed = []
        for cell in record:
            if pd.isna(cell) or cell is pd.NaT: processed.append(None)
            elif isinstance(cell, (np.integer, int)): processed.append(int(cell))
            elif isinstance(cell, (np.floating, float)): processed.append(float(cell))
            elif isinstance(cell, (pd.Timestamp, datetime, np.datetime64)): processed.append(pd.to_datetime(cell).date())
            else: processed.append(str(cell) if cell is not None else None) 
        values.append(tuple(processed))
    
    cols_sql = sql.SQL(", ").join(map(sql.Identifier, df_final.columns))
    placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(df_final.columns))
    
    update_clause = sql.SQL(', ').join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
        for col in df_final.columns if col != 'chamado_id' and col != 'data_abertura'
    )
    query = sql.SQL("INSERT INTO chamados ({}) VALUES ({}) ON CONFLICT (chamado_id) DO UPDATE SET {}").format(cols_sql, placeholders, update_clause)

    try:
        with conn.cursor() as cur: 
            cur.executemany(query, values) 
        conn.commit()
        st.cache_data.clear()
        return True, len(values)
    except Exception as e: 
        conn.rollback()
        st.error(f"Erro ao salvar no banco: {e}")
        return False, 0
        
# --- 5. FUNÇÃO PARA ATUALIZAR CHAMADO ---
def atualizar_chamado_db(chamado_id_interno, updates: dict):
    conn = get_valid_conn()
    if not conn: return False
    
    usuario_logado = st.session_state.get('usuario', 'Sistema') 
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    data_agendamento, data_fechamento, log_chamado,
                    sistema, servico,
                    analista, tecnico, prioridade, status_chamado, projeto_nome, gestor,
                    agencia_id, data_abertura,
                    link_externo, protocolo, numero_pedido, data_envio, observacao_equipamento,
                    prazo, descricao_projeto, observacao_pendencias,
                    sub_status
                FROM chamados WHERE id = %s
            """, (chamado_id_interno,))
            current_data = cur.fetchone()
            
            if not current_data: return False

            (c_agend, c_fech, c_log, c_sis, c_serv, c_analista, c_tec, c_prio, c_status, c_proj, c_gest, c_ag_id, c_abert,
             c_link, c_proto, c_ped, c_env, c_obs_eq, c_prazo, c_desc, c_obs_pend, c_sub_s) = current_data
             
            c_log = c_log or "" 

            db_updates = {}
            # Mapeamento simplificado
            mapa = {
                'agendamento': 'data_agendamento', 'fechamento': 'data_fechamento', 'finalização': 'data_fechamento',
                'sistema': 'sistema', 'serviço': 'servico', 'analista': 'analista', 'técnico': 'tecnico',
                'status': 'status_chamado', 'projeto': 'projeto_nome', 'gestor': 'gestor', 'agência': 'agencia_id',
                'abertura': 'data_abertura', 'link_externo': 'link_externo', 'protocolo': 'protocolo',
                'nº_pedido': 'numero_pedido', 'data_envio': 'data_envio', 'obs._equipamento': 'observacao_equipamento',
                'prazo': 'prazo', 'descrição': 'descricao_projeto', 'observações_e_pendencias': 'observacao_pendencias',
                'sub-status': 'sub_status', 'prioridade': 'prioridade'
            }
            
            for k_orig, v in updates.items():
                k_clean = str(k_orig).lower().replace(" ", "_")
                db_k = next((db_col for form_k, db_col in mapa.items() if form_k in k_clean), k_clean)
                
                if isinstance(v, (datetime, date)): db_updates[db_k] = v.strftime('%Y-%m-%d')
                elif pd.isna(v): db_updates[db_k] = None
                else: db_updates[db_k] = str(v)

            # Geração de Log (Resumido)
            log_entries = []
            hoje = date.today().strftime('%d/%m/%Y')
            
            # Helper Log
            def do_log(nome, novo, velho, is_d=False):
                if novo is None: novo = ""
                if velho is None: velho = ""
                if is_d:
                    try: n_d = datetime.strptime(novo, '%Y-%m-%d').date() if novo else None
                    except: n_d = velho
                    if n_d != velho:
                        v_s = velho.strftime('%d/%m') if isinstance(velho, date) else "-"
                        n_s = n_d.strftime('%d/%m') if isinstance(n_d, date) else "-"
                        log_entries.append(f"{hoje} {usuario_logado}: {nome} {v_s}->{n_s}")
                elif str(novo).strip() != str(velho).strip():
                     log_entries.append(f"{hoje} {usuario_logado}: {nome} alterado.")

            # Executa Log para campos críticos
            do_log("Status", db_updates.get('status_chamado'), c_status)
            do_log("Sub", db_updates.get('sub_status'), c_sub_s)
            do_log("Agend", db_updates.get('data_agendamento'), c_agend, True)
            do_log("Envio", db_updates.get('data_envio'), c_env, True)
            
            if log_entries:
                new_log = (c_log + "\n" + "\n".join(log_entries)).strip()
                db_updates['log_chamado'] = new_log

            if not db_updates: return True

            set_c = sql.SQL(', ').join(sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in db_updates.keys())
            query = sql.SQL("UPDATE chamados SET {} WHERE id = {}").format(set_c, sql.Placeholder())
            vals = list(db_updates.values()) + [chamado_id_interno]
            
            cur.execute(query, vals)
            conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao atualizar: {e}")
        return False

# --- 6. Funções de Cor ---
def get_status_color(status):
    s = str(status or "").strip().lower()
    if any(x in s for x in ['finalizad', 'fechado', 'conclui', 'concluí']): return "#66BB6A" 
    if any(x in s for x in ['pendencia', 'pendência']): return "#FFA726" 
    if any(x in s for x in ['nao iniciad', 'não iniciad']): return "#B0BEC5" 
    if 'cancelad' in s: return "#EF5350" 
    if 'pausad' in s: return "#FFEE58" 
    return "#64B5F6"  

def get_color_for_name(name_str):
    COLORS = ["#D32F2F", "#1976D2", "#388E3C", "#F57C00", "#7B1FA2", "#00796B", "#C2185B", "#5D4037", "#455A64"]
    if not name_str or name_str == "N/A": return "#555"
    try: return COLORS[hash(str(name_str).upper()) % len(COLORS)]
    except: return "#555"

