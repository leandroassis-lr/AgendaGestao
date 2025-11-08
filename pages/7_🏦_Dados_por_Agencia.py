import streamlit as st
import pandas as pd
import utils # Importa nosso arquivo de utilidades
from datetime import date, datetime

# Configuração da Página
st.set_page_config(page_title="Dados por Agência - GESTÃO", page_icon="🏦", layout="wide")
try:
    utils.load_css() # Tenta carregar o CSS
except:
    pass # Ignora se falhar

# --- Controle Principal de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

# --- Tela Principal da Página ---
def tela_dados_agencia():
    st.markdown("<div class='section-title-center'>GESTÃO POR AGÊNCIA</div>", unsafe_allow_html=True)
    st.write(" ")

    # --- 1. Importador de Chamados ---
    with st.expander("📥 Importar Novos Chamados do Excel"):
        st.info("""
            Arraste seu arquivo Excel de chamados aqui. O arquivo deve conter colunas com os nomes:
            `Agência`, `Número do Chamado`, `Descrição`, `Data Abertura`, `Data Fechamento`, `Status`, `Valor`.
            
            Se um `Número do Chamado` já existir, ele será **atualizado** com os novos dados.
        """)
        uploaded_file = st.file_uploader("Selecione o arquivo Excel de chamados", type=["xlsx", "xls"], key="chamado_uploader")

        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file, dtype={'Número do Chamado': str}) # Força o ID do chamado como texto
                st.success("Arquivo carregado. Pré-visualização:")
                st.dataframe(df.head(), use_container_width=True)

                if st.button("▶️ Iniciar Importação de Chamados"):
                    if df.empty:
                        st.error("Planilha vazia.")
                    else:
                        with st.spinner("Importando e atualizando chamados..."):
                            sucesso, num_importados = utils.bulk_insert_chamados_db(df)
                            if sucesso:
                                st.success(f"🎉 {num_importados} chamados importados/atualizados com sucesso!")
                                st.balloons()
                            else:
                                st.error("A importação de chamados falhou.")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")

    st.divider()

    # --- 2. Carregar e Combinar Dados ---
    with st.spinner("Carregando dados de projetos e chamados..."):
        df_projetos_raw = utils.carregar_projetos_db() 
        df_chamados_raw = utils.carregar_chamados_db()

    if df_projetos_raw.empty and df_chamados_raw.empty:
        st.info("Nenhum dado de projeto ou chamado encontrado no sistema.")
        st.stop()

    # Pega uma lista única de todas as agências
    agencias_projetos = df_projetos_raw['Agência'].dropna().astype(str).unique()
    agencias_chamados = df_chamados_raw['Agência'].dropna().astype(str).unique()
    lista_agencias_completa = sorted(list(set(agencias_projetos) | set(agencias_chamados)))
    lista_agencias_completa = [a for a in lista_agencias_completa if a not in ["N/A", "None", ""]] # Remove vazios
    lista_agencias_completa.insert(0, "Todas") 

    # --- 3. Filtro Principal por Agência ---
    st.markdown("#### 🏦 Selecionar Agência")
    agencia_selecionada = st.selectbox(
        "Selecione uma Agência para ver o histórico completo:",
        options=lista_agencias_completa,
        key="filtro_agencia_principal",
        label_visibility="collapsed"
    )

    st.divider()

    # --- 4. Exibição dos Dados ---
    if agencia_selecionada == "Todas":
        df_projetos_filtrado = df_projetos_raw
        df_chamados_filtrado = df_chamados_raw
    else:
        df_projetos_filtrado = df_projetos_raw[df_projetos_raw['Agência'].astype(str) == agencia_selecionada]
        df_chamados_filtrado = df_chamados_raw[df_chamados_raw['Agência'].astype(str) == agencia_selecionada]

    # --- 5. Painel Financeiro e KPIs ---
    total_projetos = len(df_projetos_filtrado)
    total_chamados = len(df_chamados_filtrado)
    
    valor_total_chamados = 0.0
    chamados_abertos_count = 0
    
    if not df_chamados_filtrado.empty:
        if 'Valor (R$)' in df_chamados_filtrado.columns:
            valor_total_chamados = pd.to_numeric(df_chamados_filtrado['Valor (R$)'], errors='coerce').fillna(0).sum()
        
        if 'Status' in df_chamados_filtrado.columns:
            # Conta chamados que NÃO estão em status de fechamento
            status_fechamento = ['fechado', 'concluido', 'resolvido', 'cancelado']
            chamados_abertos_count = len(df_chamados_filtrado[
                ~df_chamados_filtrado['Status'].astype(str).str.lower().isin(status_fechamento)
            ])

    st.markdown(f"### 📊 Resumo da Agência: {agencia_selecionada}")
    cols_kpi = st.columns(4) # Adicionada 4ª coluna
    cols_kpi[0].metric("Total de Projetos", total_projetos)
    cols_kpi[1].metric("Total de Chamados", total_chamados)
    cols_kpi[2].metric("Chamados Abertos", chamados_abertos_count)
    cols_kpi[3].metric("Financeiro Chamados (R$)", f"{valor_total_chamados:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')) 

    # --- 6. Abas de Detalhes ---
    tab_projetos, tab_chamados = st.tabs(["Projetos", "Chamados"])

    with tab_projetos:
        st.markdown("#### 📋 Histórico de Projetos")
        colunas_projetos_visiveis = ['ID', 'Projeto', 'Status', 'Analista', 'Gestor', 'Prioridade', 'Agendamento', 'Data de Abertura', 'Data de Finalização']
        colunas_projetos = [col for col in colunas_projetos_visiveis if col in df_projetos_filtrado.columns]
        st.dataframe(df_projetos_filtrado[colunas_projetos], use_container_width=True, hide_index=True)

    with tab_chamados:
        st.markdown("#### 🎫 Histórico de Chamados")
        colunas_chamados_visiveis = ['Nº Chamado', 'Descrição', 'Status', 'Abertura', 'Fechamento', 'Valor (R$)']
        colunas_chamados = [col for col in colunas_chamados_visiveis if col in df_chamados_filtrado.columns]
        
        if chamados_abertos_count > 0:
            st.warning(f"**Atenção:** {chamados_abertos_count} chamado(s) ainda estão abertos ou sem status de fechamento.")
        elif total_chamados > 0:
            st.success("Todos os chamados listados estão fechados.")

        st.dataframe(df_chamados_filtrado[colunas_chamados], use_container_width=True, hide_index=True)


# --- Ponto de Entrada ---
tela_dados_agencia()