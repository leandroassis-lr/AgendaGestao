import streamlit as st
import pandas as pd
import utils_chamados  # Para carregar e ATUALIZAR os chamados
import utils_financeiro # Nosso novo arquivo
import re
import time

def formatar_agencia_excel(id_agencia, nome_agencia):
    """Cria o nome combinado da agência (AG XXXX - Nome)"""
    try:
        id_agencia_limpo = str(id_agencia).split('.')[0]
        id_str = f"AG {int(id_agencia_limpo):04d}"
    except (ValueError, TypeError): id_str = str(id_agencia).strip() 
    nome_str = str(nome_agencia).strip()
    if nome_str.startswith(id_agencia_limpo):
          nome_str = nome_str[len(id_agencia_limpo):].strip(" -")
    return f"{id_str} - {nome_str}"

st.set_page_config(page_title="Gestão Financeira", page_icon="💸", layout="wide")

# --- Controle de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

# --- Criar Tabelas (LPU e Books) ---
utils_financeiro.criar_tabelas_lpu()
utils_financeiro.criar_tabela_books() # Adiciona a nova tabela

st.markdown("<h1 style='text-align: center;'>Gestão Financeira e Faturamento</h1>", unsafe_allow_html=True)
st.divider()

# --- SEÇÃO DE IMPORTAÇÃO (AGORA EM ABAS) ---
tab_lpu, tab_books = st.tabs(["⚙️ Importar LPU (Preços)", "📚 Importar Books (Faturamento)"])

with tab_lpu:
    st.info("Use esta seção para carregar ou atualizar a planilha de preços (LPU).")
    uploaded_lpu = st.file_uploader("Selecione a planilha LPU (.xlsx)", type=["xlsx"], key="lpu_uploader")
    
    if uploaded_lpu:
        try:
            with st.spinner("Lendo planilhas LPU..."):
                xls = pd.read_excel(uploaded_lpu, sheet_name=None)
                df_fixo = xls.get('Valores fixo', pd.DataFrame())
                df_servico = xls.get('Serviço', pd.DataFrame())
                df_equip = xls.get('Equipamento', pd.DataFrame())

                if df_fixo.empty and df_servico.empty and df_equip.empty:
                    st.error("Erro: Nenhuma aba válida ('Valores fixo', 'Serviço', 'Equipamento') foi encontrada.")
                else:
                    st.success("Arquivo LPU lido! Pré-visualização:")
                    if not df_fixo.empty: st.dataframe(df_fixo.head(), use_container_width=True)
                    if not df_servico.empty: st.dataframe(df_servico.head(), use_container_width=True)
                    if not df_equip.empty: st.dataframe(df_equip.head(), use_container_width=True)

                    if st.button("🚀 Importar/Atualizar LPU"):
                        with st.spinner("Importando LPU..."):
                            sucesso, msg = utils_financeiro.importar_lpu(df_fixo, df_servico, df_equip)
                            if sucesso: st.success(msg); st.balloons()
                            else: st.error(msg)
        except Exception as e:
            st.error(f"Erro ao processar o arquivo LPU: {e}")

with tab_books:
    st.info("Importe a planilha de Books para rastrear o faturamento e atualizar os chamados na 'Dados por Agência'.")
    uploaded_books = st.file_uploader("Selecione a planilha de Books (.xlsx)", type=["xlsx", "xls", "csv"], key="books_uploader")

    if uploaded_books:
        try:
            with st.spinner("Lendo planilha Books..."):
                if uploaded_books.name.endswith('.csv'):
                    df_books = pd.read_csv(uploaded_books, sep=';', header=0, encoding='utf-8', keep_default_na=False, dtype=str)
                else:
                    df_books = pd.read_excel(uploaded_books, header=0, keep_default_na=False, dtype=str)
            
            st.success("Arquivo Books lido! Pré-visualização:")
            st.dataframe(df_books.head(), use_container_width=True)

            if st.button("🚀 Importar Books e Atualizar Chamados"):
                
                # --- FUNÇÃO 1: RASTREAMENTO ---
                with st.spinner("Etapa 1/2: Importando registros de faturamento..."):
                    sucesso_books, msg_books = utils_financeiro.importar_planilha_books(df_books)
                
                if not sucesso_books:
                    st.error(msg_books)
                    st.stop()
                st.success(f"Etapa 1/2: {msg_books}")

                # --- FUNÇÃO 2: ATUALIZAÇÃO (WRITE-BACK) ---
                with st.spinner("Etapa 2/2: Atualizando protocolos na página 'Dados por Agência'..."):
                    # Normaliza cabeçalhos (igual ao utils)
                    df_books.columns = [str(col).strip().upper() for col in df_books.columns]
                    
                    # Filtra apenas os que estão prontos
                    df_prontos = df_books[df_books['BOOK PRONTO?'].str.upper().isin(['SIM', 'S'])]
                    
                    if df_prontos.empty:
                        st.warning("Etapa 2/2: Nenhum chamado com 'BOOK PRONTO?' = SIM encontrado. Nenhuma atualização automática foi feita.")
                        st.stop()

                    # Carrega os chamados para pegar o ID interno
                    df_chamados_map = utils_chamados.carregar_chamados_db()
                    if df_chamados_map.empty:
                        st.error("Etapa 2/2: Falha. Não foi possível carregar os chamados existentes para atualização.")
                        st.stop()
                    
                    # Cria o mapa: "GTS-123" -> 45
                    id_map = df_chamados_map.set_index('Nº Chamado')['ID'].to_dict()
                    
                    sucesso_count = 0
                    falha_count = 0
                    
                    for _, row in df_prontos.iterrows():
                        chamado_id_str = row['CHAMADO']
                        protocolo = row.get('PROTOCOLO')
                        data_conc = pd.to_datetime(row.get('DATA CONCLUSAO'), errors='coerce')
                        
                        internal_db_id = id_map.get(chamado_id_str)
                        
                        if internal_db_id:
                            updates = {
                                'Nº Protocolo': protocolo,
                                'Data Finalização': data_conc, # Atualiza a data de fechamento
                                'Status': 'Finalizado' # Força o status
                            }
                            # Atualiza o chamado principal
                            utils_chamados.atualizar_chamado_db(internal_db_id, updates)
                            sucesso_count += 1
                        else:
                            falha_count += 1
                    
                    st.success(f"Etapa 2/2: {sucesso_count} chamados atualizados com protocolo/data.")
                    if falha_count > 0:
                        st.warning(f"{falha_count} chamados da planilha de Book não foram encontrados no banco de dados principal.")
                    
                    st.balloons()
                    # Limpa o cache para forçar recálculo em todas as páginas
                    st.cache_data.clear()
                    st.cache_resource.clear()

        except Exception as e:
            st.error(f"Erro ao processar o arquivo Books: {e}")

st.divider()

# --- SEÇÃO DE CÁLCULO E VISUALIZAÇÃO ---
st.markdown("### 💰 Cálculo de Valores por Chamado (LPU)")

@st.cache_data(ttl=60)
def carregar_dados_completos():
    """Carrega chamados e todos os dicionários de preço."""
    df_chamados = utils_chamados.carregar_chamados_db()
    if 'Cód. Agência' in df_chamados.columns and 'Nome Agência' in df_chamados.columns:
        df_chamados['Agencia_Combinada'] = df_chamados.apply(
            lambda row: formatar_agencia_excel(row['Cód. Agência'], row['Nome Agência']), axis=1
        )    
    lpu_fixo = utils_financeiro.carregar_lpu_fixo()
    lpu_servico = utils_financeiro.carregar_lpu_servico()
    lpu_equip = utils_financeiro.carregar_lpu_equipamento()
    df_books = utils_financeiro.carregar_books_db()
    return df_chamados, lpu_fixo, lpu_servico, lpu_equip, df_books

def calcular_preco(row, lpu_fixo, lpu_servico, lpu_equip):
    """Lógica principal de cálculo de preço para uma linha (chamado)."""
    servico_norm = str(row.get('Serviço', '')).strip().lower()
    equip_norm = str(row.get('Equipamento', '')).strip().lower()
    qtd = pd.to_numeric(row.get('Qtd.'), errors='coerce')

    if servico_norm in lpu_fixo:
        return lpu_fixo[servico_norm] 

    if pd.isna(qtd) or qtd == 0: qtd = 1
        
    if equip_norm in lpu_servico:
        precos_serv = lpu_servico[equip_norm]
        if 'desativação' in servico_norm or 'desinstalação' in servico_norm:
            return precos_serv.get('desativacao', 0.0) * qtd
        if 'reinstalação' in servico_norm or 'reinstalacao' in servico_norm:
            return precos_serv.get('reinstalacao', 0.0) * qtd

    if equip_norm in lpu_equip:
        return lpu_equip.get(equip_norm, 0.0) * qtd
        
    return 0.0

# --- Execução Principal da Página ---
try:
    with st.spinner("Carregando chamados, LPU e Books..."):
        df_chamados_raw, lpu_fixo, lpu_servico, lpu_equip, df_books = carregar_dados_completos()
    
    if df_chamados_raw.empty:
        st.warning("Nenhum chamado encontrado. Importe os chamados na página 'Dados por Agência'.")
        st.stop()
        
    if not lpu_fixo and not lpu_servico and not lpu_equip:
        st.warning("Nenhum preço (LPU) foi importado. Use a aba acima para importar a planilha LPU.")

    # --- Aplica o cálculo de preço a cada linha ---
    with st.spinner("Calculando valores..."):
        df_chamados_raw['Valor_Calculado'] = df_chamados_raw.apply(
            calcular_preco, args=(lpu_fixo, lpu_servico, lpu_equip), axis=1
        )

    # --- NOVO RELATÓRIO DE CONCILIAÇÃO ---
    st.markdown("### 📈 Conciliação (Finalizados vs. Faturados)")
    
    # 1. Pegar chamados 'Finalizados' do banco principal
    status_fechamento_kpi = ['fechado', 'concluido', 'resolvido', 'cancelado', 'encerrado', 'equipamento entregue - concluído', 'finalizado']
    df_chamados_finalizados = df_chamados_raw[
        df_chamados_raw['Status'].astype(str).str.lower().isin(status_fechamento_kpi)
    ]
    
    # 2. Pegar chamados 'Book Pronto' = SIM da tabela de books
    df_books_prontos = df_books[df_books['book_pronto'].str.upper().isin(['SIM', 'S'])]
    
    # 3. Cruzar (Left Join)
    df_conciliacao = df_chamados_finalizados.merge(
        df_books_prontos[['chamado']], 
        left_on='Nº Chamado', 
        right_on='chamado', 
        how='left', 
        indicator=True
    )
    
    # 4. Filtrar pelos que estão 'Finalizados' mas NÃO têm book pronto ('left_only')
    df_pendente_faturar = df_conciliacao[df_conciliacao['_merge'] == 'left_only']
    
    total_pendente_valor = df_pendente_faturar['Valor_Calculado'].sum()
    
    conc1, conc2 = st.columns(2)
    conc1.metric("Chamados Finalizados (Pendentes de Faturar)", len(df_pendente_faturar))
    conc2.metric("Valor Pendente de Faturar (R$)", f"{total_pendente_valor:,.2f}")

    with st.expander("Ver Chamados Pendentes de Faturar"):
        st.dataframe(df_pendente_faturar[[
            'Nº Chamado', 'Agencia_Combinada', 'Serviço', 'Equipamento', 'Valor_Calculado', 'Status', 'Fechamento'
        ]], use_container_width=True)
    
    st.divider()

    # --- VISUALIZAÇÃO DOS DADOS (TABELA COMPLETA) ---
    st.markdown("#### 💰 Detalhamento Financeiro (Todos os Chamados)")
    
    # Colunas para exibir
    colunas_para_ver = [
        'Nº Chamado', 'Serviço', 'Equipamento', 'Qtd.', 'Valor_Calculado', 'Status', 'Nº Protocolo', 'Fechamento'
    ]
    if 'Agencia_Combinada' in df_chamados_raw.columns:
        colunas_para_ver.insert(1, 'Agencia_Combinada')
    
    colunas_finais = [col for col in colunas_para_ver if col in df_chamados_raw.columns]
    df_display = df_chamados_raw[colunas_finais].copy()
    
    # Formatando a coluna de valor
    df_display['Valor_Calculado'] = df_display['Valor_Calculado'].map('R$ {:,.2f}'.format)
    
    st.dataframe(df_display, use_container_width=True)

except Exception as e:
    st.error(f"Ocorreu um erro ao gerar a página: {e}")

