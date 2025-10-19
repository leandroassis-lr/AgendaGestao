import streamlit as st
import pandas as pd
import utils # Importa nosso arquivo de utilidades

st.set_page_config(page_title="Configurações - GESTÃO", page_icon="⚙️", layout="wide")
utils.load_css()

def tela_sla():
    st.markdown("### Gerenciar Prazos de SLA")
    st.info("""
    Aqui você define quantos dias de prazo cada tipo de demanda possui.
    - **Nome do Projeto:** Selecione o tipo de projeto.
    - **Demanda:** Especifique uma demanda (ex: "Instalação nova"). Deixe em branco para aplicar a todas as demandas daquele projeto.
    - **Prazo (dias):** O número de dias corridos para a conclusão.
    """)
    df_sla = utils.carregar_config("sla")
    lista_projetos = utils.carregar_config("projetos_nomes")["Nome do Projeto"].tolist()
    
    col_config = {
        "Nome do Projeto": st.column_config.SelectboxColumn("Projeto", options=lista_projetos, required=True), 
        "Demanda": st.column_config.TextColumn("Demanda/Tipo (Opcional)"), 
        "Prazo (dias)": st.column_config.NumberColumn("Prazo (dias)", min_value=1, required=True)
    }
    
    df_editado = st.data_editor(df_sla, column_config=col_config, hide_index=True, num_rows="dynamic", key="data_editor_sla", use_container_width=True)
    
    if st.button("💾 Salvar Tabela de SLA", key="btn_salvar_sla"):
        df_editado = df_editado[df_editado["Nome do Projeto"].astype(bool)]
        utils.salvar_config(df_editado, "sla")
        st.success("Tabela de SLA salva com sucesso!")
        st.rerun()

def tela_gerenciar_listas():
    st.markdown("### Gerenciar Listas de Opções")
    st.info("Adicione ou remova itens que aparecerão nos campos de seleção do sistema.")
    
    tab_titles = ["Status", "Agências", "Nomes de Projetos", "Técnicos", "Perguntas Customizadas", "Etapas de Evolução"]
    tabs = st.tabs(tab_titles)
    
    tab_map = {
        "Status": "status", "Agências": "agencias", "Nomes de Projetos": "projetos_nomes",
        "Técnicos": "tecnicos", "Perguntas Customizadas": "perguntas", "Etapas de Evolução": "etapas_evolucao"
    }
    
    for tab_title, tab in zip(tab_titles, tabs):
        tab_name = tab_map[tab_title]
        with tab:
            df_lista = utils.carregar_config(tab_name)
            
            if tab_name == "perguntas":
                st.caption("Defina as perguntas que aparecerão no formulário de 'Novo Projeto'.")
                col_config = {"Pergunta": st.column_config.TextColumn("Pergunta", required=True), "Tipo (texto, numero, data)": st.column_config.SelectboxColumn("Tipo", options=["texto", "numero", "data"], required=True)}
            elif tab_name == "etapas_evolucao":
                lista_projetos_config = utils.carregar_config("projetos_nomes")["Nome do Projeto"].tolist()
                st.caption("Defina as etapas da barra de progresso para cada tipo de projeto.")
                col_config = {
                    "Nome do Projeto": st.column_config.SelectboxColumn("Nome do Projeto", options=lista_projetos_config, required=True),
                    "Etapa": st.column_config.TextColumn("Etapa", required=True)
                }
            else:
                coluna = utils.CONFIG_TABS[tab_name][0]
                col_config = {coluna: st.column_config.TextColumn(coluna, required=True)}

            df_editado = st.data_editor(df_lista, column_config=col_config, hide_index=True, num_rows="dynamic", use_container_width=True, key=f"editor_{tab_name}")
            
            if st.button(f"💾 Salvar {tab_title}", key=f"btn_salvar_{tab_name}"):
                coluna_principal = utils.CONFIG_TABS[tab_name][0]
                df_editado = df_editado[df_editado[coluna_principal].astype(bool)]
                
                if tab_name == "perguntas" and df_editado["Pergunta"].duplicated().any():
                    st.error("Perguntas não podem ter nomes duplicados.")
                else:
                    utils.salvar_config(df_editado, tab_name)
                    st.success(f"Lista de {tab_title} salva com sucesso!")
                    st.rerun()

def tela_configuracoes():
    st.title("⚙️ Configurações do Sistema")
    
    config_options = {"Gerenciar Listas de Opções": tela_gerenciar_listas, "Gerenciar Prazos de SLA": tela_sla}
    menu_tabs = st.tabs(list(config_options.keys()))
    
    for i, tab_title in enumerate(config_options.keys()):
        with menu_tabs[i]:
            config_options[tab_title]()

# --- Controle Principal da Página ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}! 📋")
st.sidebar.divider()
st.sidebar.divider()
st.sidebar.title("Sistema")
if st.sidebar.button("Logout", use_container_width=True, key="logout_config"):
    st.session_state.clear(); st.rerun()

tela_configuracoes()