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
    'data_abertura': 'DATE', 'data_fechamento': 'DATE', 'data_faturamento': 'DATE',
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

        df_insert = df_insert.rename(columns={
            'Nº Chamado': 'CHAMADO',
            'Cód. Agência': 'N° AGENCIA'
        })
        
        df_update = df_update.rename(columns={
            'Nº Chamado': 'CHAMADO',
            'Cód. Agência': 'N° AGENCIA'
        })

DB_PATH = "dados_projeto.db" 

def bulk_insert_chamados_db(df: pd.DataFrame):
    """
    Recebe um DataFrame tratado pelo importador e salva no Banco de Dados SQLite.
    Faz INSERT (se novo) ou UPDATE (se já existe).
    """
    if df.empty:
        return False, 0

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. MAPEAMENTO DE NOMES
        # Lado Esquerdo: Como está no DataFrame (Vindo do Importador)
        # Lado Direito:  Como é o nome da COLUNA NO SEU BANCO DE DADOS (SQLite)
        map_db = {
            'Nº Chamado': 'CHAMADO',
            'Cód. Agência': 'N° AGENCIA',
            'Nome Agência': 'NOME DA AGÊNCIA',
            'Analista': 'RESPONSÁVEL',
            'Gestor': 'GESTOR ITAU',
            'Serviço': 'TIPO DO SERVIÇO',
            'Projeto': 'NOME DO PROJETO',
            'Agendamento': 'AGENDAMENTO',
            'Sistema': 'SISTEMA',
            'Qtd': 'QTD',
            'Status': 'STATUS',
            'Observações e Pendencias': 'OBSERVAÇÃO',
            'Abertura': 'DATA_ABERTURA',
            'Prazo': 'DATA_FECHAMENTO'
        }
        
        # 2. PREPARAÇÃO DOS DADOS
        df_save = df.copy()
        
        # Garante tratamento de datas para o padrão do banco (YYYY-MM-DD)
        cols_data = ['Agendamento', 'Abertura', 'Prazo']
        for col in cols_data:
            if col in df_save.columns:
                # Converte para datetime e extrai apenas a data (sem hora)
                df_save[col] = pd.to_datetime(df_save[col], errors='coerce').dt.date
                # Transforma NaT (erro de data) em None (NULL no SQL)
                df_save[col] = df_save[col].astype(object).where(df_save[col].notnull(), None)

        # Renomeia as colunas do DF para os nomes do Banco
        # (Filtra apenas as colunas que realmente existem no DF para não dar erro)
        cols_to_rename = {k: v for k, v in map_db.items() if k in df_save.columns}
        df_save = df_save.rename(columns=cols_to_rename)
        
        # Mantém apenas as colunas que foram mapeadas (Segurança para não tentar salvar lixo)
        cols_finais = list(cols_to_rename.values())
        df_save = df_save[cols_finais]

        if 'CHAMADO' not in df_save.columns:
            st.error("Erro interno: Coluna CHAMADO se perdeu no mapeamento.")
            return False, 0

        # 3. CONSTRUÇÃO DO SQL (UPSERT - Inserir ou Atualizar)
        # Monta a lista de colunas: "CHAMADO", "N° AGENCIA", "RESPONSÁVEL"...
        colunas_str = ", ".join([f'"{c}"' for c in cols_finais]) 
        placeholders = ", ".join(["?"] * len(cols_finais))
        
        # Monta a parte de atualização (SET NOME=Excluded.NOME...)
        # Isso diz: "Se o CHAMADO já existe, atualize os outros campos"
        update_clause = ", ".join([f'"{col}" = excluded."{col}"' for col in cols_finais if col != 'CHAMADO'])

        sql = f"""
            INSERT INTO Chamados ({colunas_str}) 
            VALUES ({placeholders})
            ON CONFLICT(CHAMADO) DO UPDATE SET {update_clause}
        """
        
        # Converte o DataFrame para lista de listas (formato que o SQLite aceita)
        dados = df_save.values.tolist()
        
        # Executa
        cursor.executemany(sql, dados)
        conn.commit()
        
        return True, len(dados)

    except Exception as e:
        if conn: conn.rollback()
        st.error(f"Erro ao salvar no banco de dados: {e}")
        return False, 0
    finally:
        if conn: conn.close()
            
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
            # Este mapa resolve o erro "column does not exist"
            mapa_exato = {
                # Datas
                'data finalização': 'data_fechamento',
                'data finalizacao': 'data_fechamento',
                'finalização': 'data_fechamento',
                'fechamento': 'data_fechamento',
                'data fechamento': 'data_fechamento',
                'data faturamento': 'data_faturamento',
                'faturamento': 'data_faturamento',
                
                'data abertura': 'data_abertura',
                'abertura': 'data_abertura',
                
                'data agendamento': 'data_agendamento',
                'agendamento': 'data_agendamento',
                
                'data envio': 'data_envio',
                
                # Campos Texto
                'status': 'status_chamado',
                'sub-status': 'sub_status',
                'sistema': 'sistema',
                'serviço': 'servico',
                'analista': 'analista',
                'técnico': 'tecnico',
                'agência': 'agencia_id',
                'projeto': 'projeto_nome',
                'gestor': 'gestor',
                'prazo': 'prazo',
                'prioridade': 'prioridade',
                
                # Links e Observações
                'link externo': 'link_externo',
                'nº protocolo': 'protocolo',
                'nº pedido': 'numero_pedido',
                'obs. equipamento': 'observacao_equipamento',
                'observações e pendencias': 'observacao_pendencias',
                'descrição': 'descricao_projeto'
            }
            
            for k_orig, v in updates.items():
                k_lower = str(k_orig).strip().lower()
                
                # CORREÇÃO 2: Só adiciona se existir no mapa. Chega de adivinhar nomes!
                if k_lower in mapa_exato:
                    db_k = mapa_exato[k_lower]
                    
                    # Tratamento de Valores
                    if isinstance(v, (datetime, date)): 
                        db_updates[db_k] = v.strftime('%Y-%m-%d')
                    elif v is None or pd.isna(v) or str(v).strip() == "":
                        db_updates[db_k] = None # Grava NULL
                    else: 
                        db_updates[db_k] = str(v)

            # 3. Geração de Log Simplificada
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
    """
    Gera uma cor consistente baseada no nome da pessoa.
    """
    if pd.isna(nome) or str(nome).strip() == "" or str(nome).lower() in ["nan", "none", "n/d", "sem analista"]:
        return "#9E9E9E"

    cores = [
        "#1976D2", "#388E3C", "#D32F2F", "#7B1FA2", "#F57C00", 
        "#0097A7", "#C2185B", "#512DA8", "#0288D1", "#689F38"
    ]
    idx = hash(str(nome)) % len(cores)
    return cores[idx]

def get_status_color(status):
    """
    Retorna a cor HEX baseada no texto do status.
    """
    st_lower = str(status).lower().strip()
    
    if st_lower in ['concluído', 'finalizado', 'fechado', 'resolvido', 'equipamento entregue', 'equipamento entregue - concluído']:
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
            # TRUNCATE apaga tudo instantaneamente e reseta o ID para 1
            cur.execute("TRUNCATE TABLE chamados RESTART IDENTITY CASCADE;")
        conn.commit()
        return True, "Base de chamados zerada com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao limpar banco: {e}"






