import streamlit as st
import pandas as pd
import utils 

st.set_page_config(page_title="Administração - GESTÃO", page_icon="⚙️", layout="wide")
utils.load_css()

# --- >>> CONTROLE DE PERMISSÃO <<< ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()
if st.session_state.get("permissao") != "Admin":
    st.error("⛔ Acesso Negado! Esta página é restrita a administradores.")
    st.stop()
# --- FIM DO CONTROLE ---

# Dicionário (sem alterações)
CONFIG_TABS = {
    "status": ["Status"], "agencias": ["Agência"], "projetos_nomes": ["Nome do Projeto"],
    "tecnicos": ["Técnico"], "sla": ["Nome do Projeto", "Demanda", "Prazo (dias)"],
    "perguntas": ["Pergunta", "Tipo (texto, numero, data)"],
    "etapas_evolucao": ["Nome do Projeto", "Etapa"]
}

def carregar_lista_segura(nome_aba):
    df = utils.carregar_config_db(nome_aba)
    if not df.empty and len(df.columns) > 0:
        return df.iloc[:, 0].dropna().tolist()
    return []

# --- Tela de Gerenciamento de Usuários (Nova) ---
def tela_gerenciar_usuarios():
    st.markdown("### Gerenciar Usuários")
    st.info("Adicione, remova ou edite as permissões dos usuários do sistema.")
    
    try:
        df_users_raw = utils.carregar_usuarios_db()
        if df_users_raw is None: df_users_raw = pd.DataFrame(columns=['id', 'nome', 'email', 'senha', 'permissao'])

        # Renomeia colunas para o Data Editor
        df_users = df_users_raw.rename(columns={'nome': 'Nome', 'email': 'Email', 'senha': 'Senha', 'permissao': 'Permissao'})
        
        # Garante que as colunas esperadas existam
        for col in ['Nome', 'Email', 'Permissao', 'Senha']:
             if col not in df_users.columns:
                  df_users[col] = None if col != 'Permissao' else 'Usuario'

        cols_to_show = ['Nome', 'Email', 'Permissao'] # Esconde Senha
        
        col_config = {
            "Nome": st.column_config.TextColumn("Nome", required=True),
            "Email": st.column_config.TextColumn("Email", required=True),
            "Permissao": st.column_config.SelectboxColumn("Permissão", options=["Usuario", "Admin"], required=True),
        }
        
        df_editado = st.data_editor(
            df_users[cols_to_show], column_config=col_config, 
            hide_index=True, num_rows="dynamic", key="editor_usuarios",
            use_container_width=True
        )
        
        if st.button("💾 Salvar Alterações de Usuários", key="btn_salvar_usuarios"):
            df_final = df_editado.copy()
            
            # Mescla as senhas originais, pois não foram exibidas
            df_users_com_senha = df_users[['Email', 'Senha']].set_index('Email')
            df_final = df_final.set_index('Email')
            df_final['Senha'] = df_users_com_senha['Senha']
            df_final = df_final.reset_index()

            # Validação simples de email
            if df_final['Email'].isnull().any() or not df_final['Email'].astype(str).str.contains('@').all():
                st.error("Erro: Todos os usuários devem ter um email válido.")
            else:
                if utils.salvar_usuario_db(df_final):
                    st.success("Usuários salvos com sucesso!")
                    st.rerun()
                else: st.error("Falha ao salvar usuários.")
                
    except Exception as e:
        st.error(f"Não foi possível carregar usuários: {e}")


def tela_sla():
    st.markdown("### Gerenciar Prazos de SLA")
    df_sla = utils.carregar_config_db("sla")
    colunas_esperadas = CONFIG_TABS["sla"]
    for col in colunas_esperadas:
        if col not in df_sla.columns: df_sla[col] = None
    df_sla['Nome do Projeto'] = df_sla['Nome do Projeto'].astype(str).replace('None', '')
    df_sla['Demanda'] = df_sla['Demanda'].astype(str).replace('None', '')
    df_sla['Prazo (dias)'] = pd.to_numeric(df_sla['Prazo (dias)'], errors='coerce')
    lista_projetos = carregar_lista_segura("projetos_nomes")
    if not lista_projetos: st.warning("Cadastre 'Nomes de Projetos' na aba 'Gerenciar Listas'.")
    col_config = {"Nome do Projeto": st.column_config.SelectboxColumn("Projeto", options=lista_projetos, required=True), "Demanda": st.column_config.TextColumn("Demanda/Tipo (Opcional)"), "Prazo (dias)": st.column_config.NumberColumn("Prazo (dias)", min_value=1, required=True, step=1)}
    df_editado = st.data_editor(df_sla, column_config=col_config, hide_index=True, num_rows="dynamic", key="data_editor_sla", use_container_width=True)
    if st.button("💾 Salvar Tabela de SLA", key="btn_salvar_sla"):
        df_final = df_editado.dropna(subset=["Nome do Projeto", "Prazo (dias)"], how='any')
        if utils.salvar_config_db(df_final, "sla"): st.success("Tabela de SLA salva!"); st.rerun()
        else: st.error("Falha ao salvar a tabela de SLA.")

def tela_gerenciar_listas():
    st.markdown("### Gerenciar Listas de Opções")
    tab_titles = ["Status", "Agências", "Nomes de Projetos", "Técnicos", "Perguntas Customizadas", "Etapas de Evolução"]
    tabs = st.tabs(tab_titles)
    tab_map = {"Status": "status", "Agências": "agencias", "Nomes de Projetos": "projetos_nomes", "Técnicos": "tecnicos", "Perguntas Customizadas": "perguntas", "Etapas de Evolução": "etapas_evolucao"}
    for tab_title, tab in zip(tab_titles, tabs):
        tab_name = tab_map[tab_title]
        with tab:
            df_lista = utils.carregar_config_db(tab_name)
            colunas_esperadas = CONFIG_TABS[tab_name]
            for col in colunas_esperadas:
                if col not in df_lista.columns: df_lista[col] = None
            col_config = {}
            if tab_name == "perguntas":
                col_config = {"Pergunta": st.column_config.TextColumn("Pergunta", required=True), "Tipo (texto, numero, data)": st.column_config.SelectboxColumn("Tipo", options=["texto", "numero", "data"], required=True)}
            elif tab_name == "etapas_evolucao":
                lista_projetos_config = carregar_lista_segura("projetos_nomes")
                col_config = {"Nome do Projeto": st.column_config.SelectboxColumn("Nome do Projeto", options=lista_projetos_config, required=True), "Etapa": st.column_config.TextColumn("Etapa", required=True)}
            else:
                coluna_principal = CONFIG_TABS[tab_name][0]; col_config = {coluna_principal: st.column_config.TextColumn(coluna_principal, required=True)}
            df_editado = st.data_editor(df_lista, column_config=col_config, hide_index=True, num_rows="dynamic", use_container_width=True, key=f"editor_{tab_name}")
            if st.button(f"💾 Salvar {tab_title}", key=f"btn_salvar_{tab_name}"):
                coluna_principal = CONFIG_TABS[tab_name][0]; df_final = df_editado.dropna(subset=[coluna_principal], how='any')
                if utils.salvar_config_db(df_final, tab_name): st.success(f"Lista de {tab_title} salva!"); st.rerun()
                else: st.error(f"Falha ao salvar a lista de {tab_title}.")

def tela_configuracoes_principal():
    st.title("⚙️ Painel de Administração")
    
    # --- Menu de Abas ---
    config_options = {
        "Gerenciar Usuários": tela_gerenciar_usuarios, 
        "Gerenciar Listas de Opções": tela_gerenciar_listas, 
        "Gerenciar Prazos de SLA": tela_sla
    }
    menu_tabs = st.tabs(list(config_options.keys()))
    
    for i, tab_title in enumerate(config_options.keys()):
        with menu_tabs[i]:
            config_options[tab_title]()

# --- Controle Principal ---
st.sidebar.divider()
if st.sidebar.button("Logout", use_container_width=True, key="logout_config"):
    st.session_state.clear(); st.rerun()

tela_configuracoes_principal()
