import streamlit as st
import pandas as pd
from datetime import date, datetime 
import re
import html
import psycopg2
from psycopg2 import sql
import numpy as np 
import sqlite3

# --- 1. GERENCIAMENTO DE CONEXÃO ROBUSTO (POSTGRESQL) ---

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
    
# --- 1. DEFINIÇÃO DAS COLUNAS ---
colunas_necessarias = {
    # ID e Identificadores
    'id_projeto': 'INTEGER',             
    'chamado_id': 'TEXT UNIQUE',         
    'agencia_id': 'TEXT',                
    'agencia_nome': 'TEXT',              
    'agencia_uf': 'TEXT',                
    
    # Projeto e Serviço
    'projeto_nome': 'TEXT',              
    'sistema': 'TEXT',                   
    'servico': 'TEXT',                   
    'status_chamado': 'TEXT',            
    'sub_status': 'TEXT',                
    
    # Equipamento
    'cod_equipamento': 'TEXT',           
    'nome_equipamento': 'TEXT',          
    'quantidade': 'INTEGER',             
    'observacao_equipamento': 'TEXT',    
    
    # Datas
    'data_abertura': 'DATE',             
    'data_agendamento': 'DATE',          
    'data_reagendamento': 'DATE',        
    'data_fechamento': 'DATE',           
    'data_envio': 'DATE',                
    'prazo': 'TEXT',                     
    
    # Pessoas
    'gestor': 'TEXT',                    
    'analista': 'TEXT',                  
    'tecnico': 'TEXT',                   
    
    # Detalhes
    'observacao': 'TEXT',                
    'log_chamado': 'TEXT',               
    'descricao_projeto': 'TEXT',         
    'observacao_pendencias': 'TEXT',     
    
    # Links e Protocolos
    'link_externo': 'TEXT',              
    'protocolo': 'TEXT',                 
    'numero_pedido': 'TEXT',             
    
    # Checkboxes Operacionais
    'chk_cancelado': "TEXT DEFAULT 'FALSE'",
    'chk_pendencia_equipamento': "TEXT DEFAULT 'FALSE'",
    'chk_pendencia_infra': "TEXT DEFAULT 'FALSE'",
    'chk_alteracao_chamado': "TEXT DEFAULT 'FALSE'",
    'chk_envio_parcial': "TEXT DEFAULT 'FALSE'",
    'chk_equipamento_entregue': "TEXT DEFAULT 'FALSE'",
    'chk_status_enviado': "TEXT DEFAULT 'FALSE'",
    'chk_financeiro_banco': "TEXT DEFAULT 'FALSE'",
    'book_enviado': "TEXT DEFAULT 'FALSE'"
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
                    cur.execute(f"ALTER TABLE chamados ADD COLUMN {coluna} {tipo_coluna};")
            conn.commit()
            
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao verificar tabela: {e}")

# --- 3. FUNÇÃO PARA CARREGAR CHAMADOS ---
@st.cache_data(ttl=60)
def carregar_chamados_db(agencia_id_filtro=None):
    """ Carrega chamados com tratamento de queda de conexão. """
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
        st.cache_resource.clear()
        st.error(f"Erro ao ler banco (tente recarregar a página): {e}")
        return pd.DataFrame()

# --- 4. FUNÇÃO PARA IMPORTAR CHAMADOS ---

def bulk_insert_chamados_db(df: pd.DataFrame):
    """
    Recebe um DataFrame tratado pelo importador e salva no Banco PostgreSQL.
    """
    conn = get_valid_conn()
    if not conn:
        return False, 0

    # MAPEAMENTO DE IMPORTAÇÃO (Excel -> Banco Postgres)
    # Lado Esquerdo: Nome que vem do Excel (pós-tratamento do importador)
    # Lado Direito: Nome da coluna na tabela 'chamados' do Postgres
    MAP_IMPORT = {
        "Nº Chamado": "chamado_id",
        "Cód. Agência": "agencia_id",
        "Nome Agência": "agencia_nome",
        "Analista": "analista",
        "Gestor": "gestor",
        "Serviço": "servico",
        "Projeto": "projeto_nome",
        "Agendamento": "data_agendamento",
        "Sistema": "sistema",
        "Qtd": "quantidade",
        "Status": "status_chamado",
        "Observações e Pendencias": "observacao_pendencias",
        "Abertura": "data_abertura",
        "Prazo": "prazo"
    }

    # 1. Renomeia colunas do DF para os nomes do Postgres
    df_to_insert = df.copy()
    
    # Filtra o mapa para usar apenas colunas que existem no DF
    mapa_valido = {k: v for k, v in MAP_IMPORT.items() if k in df_to_insert.columns}
    df_to_insert = df_to_insert.rename(columns=mapa_valido)

    # 2. VALIDAÇÕES BÁSICAS
    if 'chamado_id' not in df_to_insert.columns:
        st.error("Erro interno: Coluna 'Nº Chamado' se perdeu no mapeamento.")
        return False, 0

    # 3. TRATA DATAS (Para formato SQL YYYY-MM-DD)
    cols_data_banco = ['data_abertura', 'data_fechamento', 'data_agendamento']
    for col in cols_data_banco:
        if col in df_to_insert.columns:
            df_to_insert[col] = pd.to_datetime(df_to_insert[col], errors='coerce').dt.date
            # Converte NaT em None para o SQL
            df_to_insert[col] = df_to_insert[col].where(pd.notnull(df_to_insert[col]), None)

    # 4. SELECIONA APENAS COLUNAS QUE EXISTEM NO BANCO
    # Pega apenas as colunas que renomeamos e que sabemos que existem na tabela
    colunas_finais = [c for c in df_to_insert.columns if c in colunas_necessarias.keys() or c == 'chamado_id']
    df_final = df_to_insert[colunas_finais]

    # 5. MONTA A QUERY (UPSERT)
    # INSERT ... ON CONFLICT (chamado_id) DO UPDATE SET ...
    
    cols_sql = sql.SQL(", ").join(map(sql.Identifier, df_final.columns))
    placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(df_final.columns))

    # Monta a cláusula de atualização (para atualizar se já existir)
    update_clause = sql.SQL(", ").join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
        for col in df_final.columns if col != 'chamado_id'
    )

    query = sql.SQL(
        "INSERT INTO chamados ({}) VALUES ({}) "
        "ON CONFLICT (chamado_id) DO UPDATE SET {}"
    ).format(cols_sql, placeholders, update_clause)

    # 6. EXECUTA
    try:
        # Converte para lista de tuplas (formato exigido pelo psycopg2)
        # Substitui NaN por None explicitamente para evitar erro de float no SQL
        values = [tuple(x if pd.notna(x) else None for x in row) for row in df_final.values]
        
        with conn.cursor() as cur:
            cur.executemany(query, values)
        
        conn.commit()
        st.cache_data.clear()
        return True, len(values)

    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao salvar no banco: {e}")
        return False, 0

# --- 5. FUNÇÃO PARA ATUALIZAR CHAMADO (CORRIGIDA) ---

def atualizar_chamado_db(chamado_id_interno, updates: dict):
    
    conn = get_valid_conn()
    if not conn: return False
    
    usuario_logado = st.session_state.get('usuario', 'Sistema') 
    
    try:
        with conn.cursor() as cur:
            # 1. Busca dados atuais para comparar (Log)
            cur.execute("""
                SELECT 
                    data_agendamento, data_fechamento, log_chamado, 
                    status_chamado, sub_status, data_envio
                FROM chamados WHERE id = %s
            """, (chamado_id_interno,))
            current_data = cur.fetchone()
            
            if not current_data: return False

            (c_agend, c_fech, c_log, c_status, c_sub_s, c_env) = current_data
            c_log = c_log or "" 

            db_updates = {}

            # 2. Mapeamento EXATO (Chave do Form -> Coluna do Banco)
            mapa_exato = {
                # Mapeamento Campo da Tela -> Coluna do Banco
                'id_projeto': 'id_projeto',
                'nº chamado': 'chamado_id',
                'cód. agência': 'agencia_id',
                'nome agência': 'agencia_nome',
                'uf': 'agencia_uf',
                
                'status': 'status_chamado',
                'sub-status': 'sub_status',
                'projeto': 'projeto_nome',
                'sistema': 'sistema',
                'serviço': 'servico',
                
                'cód. equip.': 'cod_equipamento',
                'equipamento': 'nome_equipamento',
                'qtd.': 'quantidade',
                'obs. equipamento': 'observacao_equipamento',
                
                'abertura': 'data_abertura', 'data abertura': 'data_abertura',
                'agendamento': 'data_agendamento', 'data agendamento': 'data_agendamento',
                'reagendamento': 'data_reagendamento', 'data reagendamento': 'data_reagendamento',
                'conclusão': 'data_fechamento', 'fechamento': 'data_fechamento', 'finalização': 'data_fechamento', 'data finalização': 'data_fechamento',
                'data envio': 'data_envio',
                'prazo': 'prazo',
                
                'gestor': 'gestor',
                'analista': 'analista',
                'técnico': 'tecnico',
                
                'observação': 'observacao',
                'log do chamado': 'log_chamado',
                'descrição': 'descricao_projeto',
                'observações e pendencias': 'observacao_pendencias',
                
                'link externo': 'link_externo',
                'nº protocolo': 'protocolo',
                'nº pedido': 'numero_pedido',
                
                # Checkboxes
                'chk_cancelado': 'chk_cancelado',
                'chk_pendencia_equipamento': 'chk_pendencia_equipamento',
                'chk_pendencia_infra': 'chk_pendencia_infra',
                'chk_alteracao_chamado': 'chk_alteracao_chamado',
                'chk_envio_parcial': 'chk_envio_parcial',
                'chk_equipamento_entregue': 'chk_equipamento_entregue',
                'chk_status_enviado': 'chk_status_enviado',
                
                # Financeiro (Mantido)
                'chk_financeiro_banco': 'chk_financeiro_banco',
                'book_enviado': 'book_enviado',
                'book enviado': 'book_enviado'
            }
            
            for k_orig, v in updates.items():
                k_lower = str(k_orig).strip().lower()
                
                if k_lower in mapa_exato:
                    db_k = mapa_exato[k_lower]
                    
                    # Tratamento de Valores
                    if isinstance(v, (datetime, date)): 
                        db_updates[db_k] = v.strftime('%Y-%m-%d')
                    elif v is None or pd.isna(v) or str(v).strip() == "":
                        db_updates[db_k] = None # Grava NULL
                    else: 
                        db_updates[db_k] = str(v)

            # 3. Geração de Log
            log_entries = []
            hoje = date.today().strftime('%d/%m/%Y')
            
            novo_status = db_updates.get('status_chamado')
            if novo_status is not None and str(novo_status) != str(c_status):
                log_entries.append(f"{hoje} {usuario_logado}: Status '{c_status}' -> '{novo_status}'")

            novo_sub = db_updates.get('sub_status')
            if novo_sub is not None and str(novo_sub or "") != str(c_sub_s or ""):
                log_entries.append(f"{hoje} {usuario_logado}: Ação '{c_sub_s}' -> '{novo_sub}'")

            if log_entries:
                new_log = (c_log + "\n" + "\n".join(log_entries)).strip()
                db_updates['log_chamado'] = new_log

            if not db_updates: return True

            # 4. Executa Update
            set_c = sql.SQL(', ').join(sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in db_updates.keys())
            query = sql.SQL("UPDATE chamados SET {} WHERE id = {}").format(set_c, sql.Placeholder())
            vals = list(db_updates.values()) + [chamado_id_interno]
            
            cur.execute(query, vals)
            conn.commit()
            
        return True
        
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"Erro ao atualizar banco: {e}")
        return False
        
# --- 6. Funções de Cor ---
def get_color_for_name(nome):
    """ Gera uma cor consistente baseada no nome. """
    if pd.isna(nome) or str(nome).strip() == "" or str(nome).lower() in ["nan", "none", "n/d", "sem analista"]:
        return "#9E9E9E"

    cores = ["#1976D2", "#388E3C", "#D32F2F", "#7B1FA2", "#F57C00", "#0097A7", "#C2185B", "#512DA8", "#0288D1", "#689F38"]
    idx = hash(str(nome)) % len(cores)
    return cores[idx]

def get_status_color(status):
    """ Retorna a cor HEX baseada no texto do status. """
    st_lower = str(status).lower().strip()
    
    if st_lower in ['concluído', 'finalizado', 'fechado', 'resolvido', 'equipamento entregue']:
        return "#2E7D32" # Verde Escuro
    elif 'cancelado' in st_lower:
        return "#C62828" # Vermelho Forte
    elif 'pendência' in st_lower or 'pausado' in st_lower:
        return "#EF6C00" # Laranja
    elif 'em andamento' in st_lower or 'iniciado' in st_lower:
        return "#1565C0" # Azul
    elif st_lower == 'não iniciado':
        return "#78909C" # Cinza Azulado
    
    return "#9E9E9E" # Cinza Default

# --- FUNÇÃO DE LIMPEZA TOTAL (PARA TESTES) ---
def resetar_tabela_chamados():
    conn = get_valid_conn()
    if not conn: return False, "Erro de conexão"
    
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE chamados RESTART IDENTITY CASCADE;")
        conn.commit()
        return True, "Base de chamados zerada com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao limpar banco: {e}"
