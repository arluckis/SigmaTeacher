import streamlit as st
import requests
from PIL import Image
from streamlit_mic_recorder import mic_recorder
import os

# --- LOGO PRINCIPAL ---
try:
    # Carrega a imagem
    logo_principal = Image.open("assets/logo_sigma.png")
    
    # Cria colunas para centralizar a logo (truque de layout)
    col1, col2, col3 = st.columns([1, 2, 1]) 
    with col2:
        # Mostra a imagem no meio. 
        # use_column_width=True faz ela se ajustar ao tamanho da coluna
        # width=300 força um tamanho específico em pixels
        st.image(logo_principal, use_container_width=True)
except FileNotFoundError:
    st.title("🎙️ Sigma Teacher") # Título texto se não tiver imagem

# Tenta pegar do Docker, se não achar, usa localhost
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# Criando abas para organizar a tela
aba_gravacao, aba_historico = st.tabs(["VoiceTeacher", "VoiceTeacher History"])

# --- ABA 2: VOICETEACHER (Gravação) ---
with aba_gravacao:
    # 1. Seu novo Cabeçalho e Texto
    st.header("VoiceTeacher")
    
    # Dica: Usei st.markdown para deixar o texto mais bonito e justificado
    st.markdown("""
    Use o **VoiceTeacher** para gravar suas aulas e aumentar o desempenho de seus alunos. 
    Clique no botão abaixo para começar.
    """)
    
    st.divider() 

    c1, c2, c3 = st.columns([1, 2, 1]) # Coluna do meio mais larga para o botão

    with c2:
        audio_do_botao = mic_recorder(
            start_prompt="🎙️ Iniciar Aula",  # Personalizei com ícone
            stop_prompt="⏹️ Encerrar Aula", 
            just_once=False,
            use_container_width=True,
            key='gravador_voiceteacher'
        )

    # 3. Lógica de Envio (Só aparece depois que gravar)
    if audio_do_botao:
        st.success("Aula gravada com sucesso!")
        
        # Player para conferir
        st.audio(audio_do_botao['bytes'], format="audio/wav")
        
        # Botão de envio
        if st.button("Processar Aula no Sigma Teacher", type="primary"):
            st.info("Enviando áudio para inteligência artificial...")
            
            files = {"file": ("aula_voice_teacher.wav", audio_do_botao['bytes'], "audio/wav")}
            
            try:
                response = requests.post(f"{API_URL}/transcrever-e-salvar", files=files)
                if response.status_code == 200:
                    dados = response.json()
                    st.balloons() # Efeito visual de sucesso!
                    st.success("Transcrição Concluída!")
                    
                    with st.expander("Ver Transcrição Completa", expanded=True):
                        st.write(dados['transcricao'])
                else:
                    st.error("Erro ao conectar com o servidor.")
            except Exception as e:
                st.error(f"Erro: {e}")
                
with aba_historico:
    st.header("VoiceTeacher History")
    st.write("Encontre a gravação da linda voz do seu professor novamente por aqui, para que você aluno possa revisitar o conteúdo quantas vezes precisar!")
    
    if st.button("Atualizar Lista"):
        try:
            resp = requests.get(f"{API_URL}/listar-audios")
            if resp.status_code == 200:
                dados = resp.json()
                # Mostra tabela, mas removemos o caminho do arquivo pra ficar mais limpo
                st.dataframe(dados, column_config={
                    "caminho_arquivo": None, 
                    "transcricao": "Texto Transcrito"
                })
            else:
                st.error("Erro ao buscar dados.")
        except:
            st.warning("Conecte o servidor backend primeiro.")