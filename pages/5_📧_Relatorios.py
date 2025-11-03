import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta # Adicionado datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import utils
import html # Importar html para escapar

st.set_page_config(page_title="Relatórios - GESTÃO", page_icon="📧", layout="wide")

def enviar_email(destinatario, assunto, corpo_html):
    """Envia um email usando as credenciais dos Secrets."""
    try:
        # Pega as credenciais do st.secrets
        email_config = st.secrets["email"]
        remetente = email_config["user"]
        senha = email_config["password"]
        smtp_server = email_config["smtp_server"]
        smtp_port = email_config["smtp_port"]

        # Cria a mensagem
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destinatario
        msg["Subject"] = assunto
        msg.attach(MIMEText(corpo_html, "html", "utf-8")) # Definido utf-8

        # Envia o email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(remetente, senha)
            server.send_message(msg)
        
        return True, "Email enviado com sucesso!"
    except KeyError:
        return False, "Erro: As credenciais de email não foram configuradas nos 'Secrets' do Streamlit."
    except Exception as e:
        return False, f"Erro ao enviar email: {e}"

# --- 1. FUNÇÃO DE ESTILO ATUALIZADA ---

def formatar_df_para_html(df, titulo):
    """
    Formata um DataFrame como uma tabela HTML estilizada com CSS INLINE
    para máxima compatibilidade com clientes de email (Gmail, Outlook).
    """
    if df.empty:
        return f"<h4 style='color:#34495E; font-family: Arial, sans-serif;'>{titulo}</h4><p style='font-family:Arial, sans-serif; color: #555;'>Nenhum projeto encontrado.</p>"

    # --- Estilos Inline (A única forma 100% garantida) ---
    # Cores do seu tema
    cor_header_bg = "#004D38"  # Verde Escuro
    cor_header_texto = "#FFFFFF"
    cor_borda_header = "#006A4E" # Verde Principal
    cor_linha_par = "#f3f3f3"
    cor_linha_impar = "#ffffff"
    cor_borda_linha = "#dddddd"
    cor_titulo_h4 = "#34495E"     # Cinza-ardósia
    familia_fonte = "'Arial', sans-serif" # Fonte segura para email
    
    # --- Título ---
    html_output = f"<h4 style='color:{cor_titulo_h4}; font-family: {familia_fonte};'>{titulo}</h4>"
    
    # --- Tabela ---
    html_output += f"""
    <table style='border-collapse: collapse; width: 100%; font-family: {familia_fonte}; font-size: 0.9em; min-width: 400px; box-shadow: 0 0 10px rgba(0,0,0,0.1);'>
    """
    
    # --- Cabeçalho (th) ---
    html_output += "<thead><tr>"
    for col in df.columns:
        col_escapada = html.escape(str(col))
        html_output += f"<th style='background-color: {cor_header_bg}; color: {cor_header_texto}; text-align: left; padding: 12px 15px; border-bottom: 2px solid {cor_borda_header};'>{col_escapada}</th>"
    html_output += "</tr></thead>"
    
    # --- Corpo (td) ---
    html_output += "<tbody>"
    
    for i, row in df.iterrows():
        # Define a cor da linha (par ou ímpar)
        current_row_style = cor_linha_par if i % 2 == 0 else cor_linha_impar
        html_output += f"<tr style='background-color: {current_row_style};'>"
        
        for col in df.columns:
            val = row[col]
            # Trata valores Nulos/NaN/NaT
            if pd.isna(val) or val is None:
                display_val = "N/A"
            else:
                # Escapa o valor para segurança
                display_val = html.escape(str(val))
                
            html_output += f"<td style='padding: 12px 15px; text-align: left; border-bottom: 1px solid {cor_borda_linha};'>{display_val}</td>"
        html_output += "</tr>"
    
    html_output += "</tbody></table><br>" 
    
    return html_output
    
# Retorna o CSS, o Título e a Tabela
    return f"{css_style}<h4 style='color:#34495E;'>{titulo}</h4>{html_table}"


# --- 2. TELA DE RELATÓRIOS (Atualizada com Aging e Agrupamento) ---
def tela_relatorios():
    st.markdown("<div class='section-title-center'>RELATÓRIOS POR EMAIL</div>", unsafe_allow_html=True)
    st.info("Gere e envie um relatório por analista, com os projetos vencidos e os agendados para a próxima semana.")

    destinatario_default = st.session_state.get('usuario_email', 'exemplo@dominio.com') # Tenta pegar o email do usuário logado
    destinatario = st.text_input("Enviar para o email:", value=destinatario_default)

    if st.button("🚀 Gerar e Enviar Relatório Diario", use_container_width=True):
        if not destinatario or '@' not in destinatario:
            st.error("Por favor, insira um email de destinatário válido.")
            return

        with st.spinner("Gerando relatório e enviando email..."):
            df = utils.carregar_projetos_db()
            
            if df.empty:
                st.error("Não há dados de projetos para gerar o relatório.")
                return

            # --- 3. CÁLCULO DO AGING (Nova Lógica) ---
            hoje = date.today()
            # Converte as colunas de data (necessário para cálculos)
            df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.date
            df['Data de Abertura'] = pd.to_datetime(df['Data de Abertura'], errors='coerce').dt.date
            
            # Calcula o Aging (dias desde a abertura)
            # Usa 'apply' para tratar erros se 'Data de Abertura' for Nula (NaT)
            df['Aging (Dias)'] = (hoje - df['Data de Abertura']).apply(lambda x: x.days if pd.notna(x) else 0).astype(int)
            
            # Preenche Nulos na coluna Analista para o agrupamento
            df['Analista'] = df['Analista'].fillna('Sem Analista Definido')
            # -----------------------------------------------

            proxima_segunda = hoje + timedelta(days=(7 - hoje.weekday()))
            
            # 1. Filtro: Projetos Vencidos
            df_vencidos = df[
                (df['Agendamento'] < hoje) &
                (~df['Status'].str.contains("Finalizada|Cancelada", na=False, case=False))
            ].copy()
            
            # 2. Filtro: Projetos da Próxima Semana
            df_proxima_semana = df[
                (df['Agendamento'] >= hoje) &
                (df['Agendamento'] <= proxima_segunda)
            ].copy()

            # Pega lista única de todos os analistas envolvidos
            lista_analistas = sorted(pd.concat([df_vencidos['Analista'], df_proxima_semana['Analista']]).unique())

            if not lista_analistas:
                st.warning("Nenhum projeto vencido ou agendado para a próxima semana encontrado.")
                st.stop()
                
            # Seleciona colunas para o email (Removido 'Analista', Adicionado 'Aging')
            colunas_relatorio = ['Projeto', 'Agência', 'Agendamento', 'Status', 'Aging (Dias)']

            # --- 4. AGRUPAMENTO POR ANALISTA (Nova Lógica) ---
            
            # Inicia o corpo do email
            corpo_html = f"""
            <html>
                <head>
                 <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                </head>
                <body style="font-family: 'Arial', sans-serif; line-height: 1.6;">
                    <h2 style="color: #004D38; border-bottom: 2px solid #006A4E; padding-bottom: 10px;">
                        Relatório Diario de Projetos - {hoje.strftime('%d/%m/%Y')}
                    </h2>
                    <p style="color: #34495E;">Este é um resumo automático dos projetos com pendências e agendamentos futuros. </p>
            """

            # Loop por cada analista
            for analista in lista_analistas:
                # Escapa o nome do analista para exibição segura
                analista_html = html.escape(analista)
                corpo_html += f"<hr><h3 style='background-color: #F0F2F5; padding: 10px; border-radius: 5px; color: #2C3E50;'>Analista: {analista_html}</h3>"
                
                # Filtra os projetos deste analista
                df_vencidos_analista = df_vencidos[df_vencidos['Analista'] == analista]
                df_proxima_semana_analista = df_proxima_semana[df_proxima_semana['Analista'] == analista]
                
                # Formata as colunas (convertendo data de agendamento de volta para string)
                df_vencidos_html = df_vencidos_analista[colunas_relatorio].copy()
                df_vencidos_html['Agendamento'] = df_vencidos_html['Agendamento'].apply(lambda x: x.strftime('%d/%m/%Y') if x else 'N/D')
                
                df_proxima_semana_html = df_proxima_semana_analista[colunas_relatorio].copy()
                df_proxima_semana_html['Agendamento'] = df_proxima_semana_html['Agendamento'].apply(lambda x: x.strftime('%d/%m/%Y') if x else 'N/D')

                # Adiciona as tabelas HTML ao corpo do email
                corpo_html += formatar_df_para_html(df_vencidos_html, f"🚨 Projetos Vencidos ({len(df_vencidos_html)})")
                corpo_html += formatar_df_para_html(df_proxima_semana_html, f"🗓️ Projetos Agendados até {proxima_segunda.strftime('%d/%m/%Y')} ({len(df_proxima_semana_html)})")
            
            # Fecha o corpo do email
            corpo_html += """
                    <br>
                    <p style="color: #777; font-size: 0.8em;"><em>Relatório gerado pelo Sistema de Gestão de Projetos.</em></p>
                </body>
            </html>
            """
            # --- FIM DO AGRUPAMENTO ---

            # Envia o email (função sem alteração)
            sucesso, mensagem = enviar_email(destinatario, f"Relatório Semanal de Projetos - {hoje.strftime('%d/%m/%Y')}", corpo_html)

            if sucesso:
                st.success(mensagem)
                st.balloons()
            else:
                st.error(mensagem)

# --- Controle Principal ---
if "logado" not in st.session_state:
    # Tenta carregar o usuário logado do app principal (se existir)
    try:
        if st.query_params.get("user_email"):
            st.session_state.logado = True
            st.session_state.usuario_email = st.query_params.get("user_email")
    except:
        pass # Ignora se falhar

if not st.session_state.get("logado", False):
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

# Chama a tela principal
tela_relatorios()


