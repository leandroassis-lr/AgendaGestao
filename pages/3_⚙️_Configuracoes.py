import streamlit as st
import pandas as pd
import utils # Importa nosso arquivo de utilidades

st.set_page_config(page_title="Configurações - GESTÃO", page_icon="⚙️", layout="wide")
utils.load_css()

# Dicionário para mapear nomes de abas a nomes de colunas
CONFIG_TABS = {
    "status": ["Status"], "agencias": ["Agência"], "projetos_nomes": ["Nome do Projeto"],
    "tecnicos": ["Técnico"], "sla": ["Nome do Projeto", "Demanda", "Prazo (dias)"],
    "perguntas": ["Pergunta", "Tipo (texto, numero, data)"],
    "etapas_evolucao": ["Nome do Projeto", "Etapa"]
}

def carregar_lista_segura(nome_aba):
    """Função de ajuda para carregar uma lista de uma coluna, de forma segura."""
    df = utils.carregar_config_db(nome_aba)
    if not df.empty and len(df.columns) > 0:
        return df[df.columns[0]].dropna().tolist()
    return []

def tela_sla():
    st.markdown("### Gerenciar Prazos de SLA")
    st.info("""
    Aqui você define quantos dias de prazo cada tipo de demanda possui.
    - **Nome do Projeto:** Selecione o tipo de projeto.
    - **Demanda:** Especifique uma demanda (ex: "Instalação nova"). Deixe em branco para aplicar a todas.
    - **Prazo (dias):** O número de dias corridos para a conclusão.
    """)
    
    df_sla = utils.carregar_config_db("sla")
    lista_projetos = carregar_lista_segura("projetos_nomes")
    
    # --- CORREÇÃO APLICADA AQUI ---
    # Garante que o DataFrame tenha as colunas esperadas, mesmo se estiver vazio
    colunas_esperadas = CONFIG_TABS["sla"]
    for col in colunas_esperadas:
        if col not in df_sla.columns:
            df_sla[col] = pd.Series(dtype='object') # Adiciona a coluna se ela não existir
    # --- FIM DA CORREÇÃO ---

    if not lista_projetos:
        st.warning("Cadastre primeiro os 'Nomes de Projetos' na aba 'Gerenciar Listas de Opções'.")
        # Mesmo com o aviso, mostramos o editor vazio para permitir a inserção do primeiro item
    
    col_config = {
        "Nome do Projeto": st.column_config.SelectboxColumn("Projeto", options=lista_projetos, required=True),    
        "Demanda": st.column_config.TextColumn("Demanda/Tipo (Opcional)"),    
        "Prazo (dias)": st.column_config.NumberColumn("Prazo (dias)", min_value=1, required=True, step=1)
    }
    
    df_editado = st.data_editor(df_sla, column_config=col_config, hide_index=True, num_rows="dynamic", key="data_editor_sla", use_container_width=True)
    
    if st.button("💾 Salvar Tabela de SLA", key="btn_salvar_sla"):
        df_editado.dropna(subset=["Nome do Projeto", "Prazo (dias)"], how='all', inplace=True)
        if utils.salvar_config_db(df_editado, "sla"):
            st.success("Tabela de SLA salva com sucesso!")
            st.rerun()
        else:
            st.error("Falha ao salvar a tabela de SLA.")

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
            df_lista = utils.carregar_config_db(tab_name)
            
            # Garante que o DataFrame tenha as colunas esperadas
            colunas_esperadas_lista = CONFIG_TABS[tab_name]
            for col in colunas_esperadas_lista:
                if col not in df_lista.columns:
                    df_lista[col] = pd.Series(dtype='object')

            col_config = {}
            if tab_name == "perguntas":
                st.caption("Defina as perguntas do formulário 'Novo Projeto'.")
                col_config = {"Pergunta": st.column_config.TextColumn("Pergunta", required=True), "Tipo (texto, numero, data)": st.column_config.SelectboxColumn("Tipo", options=["texto", "numero", "data"], required=True)}
            elif tab_name == "etapas_evolucao":
                lista_projetos_config = carregar_lista_segura("projetos_nomes")
                st.caption("Defina as etapas da barra de progresso para cada tipo de projeto.")
                col_config = {
                    "Nome do Projeto": st.column_config.SelectboxColumn("Nome do Projeto", options=lista_projetos_config, required=True),
                    "Etapa": st.column_config.TextColumn("Etapa", required=True)
                }
            else:
                coluna = CONFIG_TABS[tab_name][0]
                col_config = {coluna: st.column_config.TextColumn(coluna, required=True)}

            df_editado = st.data_editor(df_lista, column_config=col_config, hide_index=True, num_rows="dynamic", use_container_width=True, key=f"editor_{tab_name}")
            
            if st.button(f"💾 Salvar {tab_title}", key=f"btn_salvar_{tab_name}"):
                coluna_principal = CONFIG_TABS[tab_name][0]
                df_editado.dropna(subset=[coluna_principal], how='all', inplace=True)
                
                if tab_name == "perguntas" and df_editado["Pergunta"].duplicated().any():
                    st.error("Perguntas não podem ter nomes duplicados.")
                else:
                    if utils.salvar_config_db(df_editado, tab_name):
                        st.success(f"Lista de {tab_title} salva com sucesso!")
                        st.rerun()
                    else:
                        st.error(f"Falha ao salvar a lista de {tab_title}.")

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
if st.sidebar.button("Logout", use_container_width=True, key="logout_config"):
    st.session_state.clear()
    st.rerun()

tela_configuracoes()
