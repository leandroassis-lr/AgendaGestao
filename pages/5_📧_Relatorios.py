import streamlit as st
import pandas as pd
from datetime import date, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import utils

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
        msg.attach(MIMEText(corpo_html, "html"))

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

def formatar_df_para_html(df, titulo):
    """Formata um DataFrame como uma tabela HTML estilizada."""
    if df.empty:
        return f"<h3>{titulo}</h3><p>Nenhum projeto encontrado.</p>"
    
    html = f"<h3>{titulo}</h3>"
    html += df.to_html(index=False, border=0, classes="styled-table")
    # Adiciona estilo CSS à tabela
    html = f"""
    <style>
        .styled-table {{
            border-collapse: collapse;
            margin: 25px 0;
            font-size: 0.9em;
            font-family: sans-serif;
            min-width: 400px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
        }}
        .styled-table thead tr {{
            background-color: #009879;
            color: #ffffff;
            text-align: left;
        }}
        .styled-table th, .styled-table td {{
            padding: 12px 15px;
        }}
        .styled-table tbody tr {{
            border-bottom: 1px solid #dddddd;
        }}
        .styled-table tbody tr:nth-of-type(even) {{
            background-color: #f3f3f3;
        }}
        .styled-table tbody tr.last-row {{
            border-bottom: 2px solid #009879;
        }}
    </style>
    {html}
    """
    return html

def tela_relatorios():
    st.markdown("<div class='section-title-center'>RELATÓRIOS POR EMAIL</div>", unsafe_allow_html=True)
    st.info("Gere e envie um relatório com os projetos vencidos e os agendados para a próxima semana (de hoje até a próxima segunda-feira).")

    destinatario = st.text_input("Enviar para o email:", placeholder="exemplo@dominio.com")

    if st.button("🚀 Gerar e Enviar Relatório Semanal", use_container_width=True):
        if not destinatario:
            st.error("Por favor, insira um email de destinatário.")
            return

        with st.spinner("Gerando relatório e enviando email..."):
            df = utils.carregar_projetos_db()
            
            # Converte datas para o formato correto, tratando erros
            df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.date

            hoje = date.today()
            # O nome correto da variável
            proxima_segunda = hoje + timedelta(days=(7 - hoje.weekday())) 
            
            # 1. Projetos Vencidos
            df_vencidos = df[
                (df['Agendamento'] < hoje) &
                (~df['Status'].str.contains("Finalizada|Cancelada", na=False, case=False))
            ].copy()
            
            # 2. Projetos da Próxima Semana
            df_proxima_semana = df[
                (df['Agendamento'] >= hoje) &
                # --- CORREÇÃO AQUI ---
                (df['Agendamento'] <= proxima_segunda) 
                # ---------------------
            ].copy()

            # Seleciona e formata colunas para o email
            colunas_relatorio = ['Projeto', 'Analista', 'Agência', 'Agendamento', 'Status']
            df_vencidos_html = df_vencidos[colunas_relatorio]
            df_proxima_semana_html = df_proxima_semana[colunas_relatorio]
            
            # Cria o corpo do email em HTML
            corpo_html = f"""
            <html>
                <body>
                    <h2>Relatório Semanal de Projetos - {hoje.strftime('%d/%m/%Y')}</h2>
                    <p>Este é um resumo automático dos projetos com pendências e agendamentos futuros.</p>
                    {formatar_df_para_html(df_vencidos_html, 'Projetos Vencidos')}
                    {formatar_df_para_html(df_proxima_semana_html, f'Projetos Agendados até {proxima_segunda.strftime("%d/%m/%Y")}')}
                    <br>
                    <p><em>Relatório gerado pelo Sistema de Gestão de Projetos.</em></p>
                </body>
            </html>
            """

            # Envia o email
            sucesso, mensagem = enviar_email(destinatario, f"Relatório Semanal de Projetos - {hoje.strftime('%d/%m/%Y')}", corpo_html)

            if sucesso:
                st.success(mensagem)
                st.balloons()
            else:
                st.error(mensagem)

# --- Controle Principal ---
# (O seu código de verificação de login permanece o mesmo)
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal.")
    st.stop()

tela_relatorios()
