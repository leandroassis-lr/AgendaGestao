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
    
    # Passo 1: Carrega os dados
    df_sla = utils.carregar_config_db("sla")
    
    # --- PASSO DE DEPURAÇÃO ---
    st.write("Dados brutos carregados do banco para 'SLA':")
    st.dataframe(df_sla) # Mostra a tabela crua na tela
    # --- FIM DO PASSO DE DEPURAÇÃO ---

    # Passo 2: Prepara o DataFrame para o editor
    colunas_esperadas = CONFIG_TABS["sla"]
    for col in colunas_esperadas:
        if col not in df_sla.columns:
            df_sla[col] = None # Adiciona colunas ausentes

    # Força os tipos corretos para evitar erros
    df_sla['Nome do Projeto'] = df_sla['Nome do Projeto'].astype(str).replace('None', '')
    df_sla['Demanda'] = df_sla['Demanda'].astype(str).replace('None', '')
    df_sla['Prazo (dias)'] = pd.to_numeric(df_sla['Prazo (dias)'], errors='coerce')

    # Passo 3: Configura e exibe o editor
    lista_projetos = carregar_lista_segura("projetos_nomes")
    if not lista_projetos:
        st.warning("Cadastre primeiro os 'Nomes de Projetos' na aba 'Gerenciar Listas de Opções'.")

    col_config = {
        "Nome do Projeto": st.column_config.SelectboxColumn("Projeto", options=lista_projetos, required=True),
        "Demanda": st.column_config.TextColumn("Demanda/Tipo (Opcional)"),
        "Prazo (dias)": st.column_config.NumberColumn("Prazo (dias)", min_value=1, required=True, step=1)
    }
    
    df_editado = st.data_editor(df_sla, column_config=col_config, hide_index=True, num_rows="dynamic", key="data_editor_sla", use_container_width=True)
    
    if st.button("💾 Salvar Tabela de SLA", key="btn_salvar_sla"):
        df_final = df_editado.dropna(subset=["Nome do Projeto", "Prazo (dias)"], how='any')
        if utils.salvar_config_db(df_final, "sla"):
            st.success("Tabela de SLA salva com sucesso!")
            st.rerun()
        else:
            st.error("Falha ao salvar a tabela de SLA.")

def tela_gerenciar_listas():
    st.markdown("### Gerenciar Listas de Opções")
    
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
            
            # --- PASSO DE DEPURAÇÃO ---
            st.write(f"Dados brutos carregados para '{tab_title}':")
            st.dataframe(df_lista)
            # --- FIM DO PASSO DE DEPURAÇÃO ---

            colunas_esperadas = CONFIG_TABS[tab_name]
            for col in colunas_esperadas:
                if col not in df_lista.columns:
                    df_lista[col] = None
            
            # Prepara a configuração do editor
            col_config = {}
            if tab_name == "perguntas":
                col_config = {"Pergunta": st.column_config.TextColumn("Pergunta", required=True), "Tipo (texto, numero, data)": st.column_config.SelectboxColumn("Tipo", options=["texto", "numero", "data"], required=True)}
            elif tab_name == "etapas_evolucao":
                lista_projetos_config = carregar_lista_segura("projetos_nomes")
                col_config = {
                    "Nome do Projeto": st.column_config.SelectboxColumn("Nome do Projeto", options=lista_projetos_config, required=True),
                    "Etapa": st.column_config.TextColumn("Etapa", required=True)
                }
            else:
                coluna_principal = CONFIG_TABS[tab_name][0]
                col_config = {coluna_principal: st.column_config.TextColumn(coluna_principal, required=True)}

            df_editado = st.data_editor(df_lista, column_config=col_config, hide_index=True, num_rows="dynamic", use_container_width=True, key=f"editor_{tab_name}")
            
            if st.button(f"💾 Salvar {tab_title}", key=f"btn_salvar_{tab_name}"):
                coluna_principal = CONFIG_TABS[tab_name][0]
                df_final = df_editado.dropna(subset=[coluna_principal], how='any')
                
                if utils.salvar_config_db(df_final, tab_name):
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

# --- Controle Principal ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}! 📋")
st.sidebar.divider()
if st.sidebar.button("Logout", use_container_width=True, key="logout_config"):
    st.session_state.clear()
    st.rerun()

tela_configuracoes()
