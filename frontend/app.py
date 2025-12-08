import streamlit as st
import requests
from PIL import Image
from streamlit_mic_recorder import mic_recorder
import os

st.set_page_config(
    page_title="SigmaTeacher",
    page_icon=Image.open("assets/logo_sigma.png"),
)

def listar_audios():
        try:
            resp = requests.get(f"{API_URL}/listar-audios")
            if resp.status_code == 200:
                dados = resp.json()
                # Mostra tabela, mas removemos o caminho do arquivo pra ficar mais limpo
            else:
                st.error("Erro ao buscar dados.")
        except Exception:
            st.warning("Conecte o servidor backend primeiro.")
        return dados

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
aba_gravacao, aba_historico, aba_config_its, aba_chat = st.tabs(["VoiceTeacher", "VoiceTeacher History", "Configuração do ITS", "VoiceTeacher Chat"])

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
    
    dados = listar_audios()
    st.dataframe(dados, column_config={
        "caminho_arquivo": None, 
        "transcricao": "Texto Transcrito"
    })
    if st.button("Atualizar Lista"):
       dados = listar_audios()

with aba_config_its:

    dados = listar_audios()
    
    # TAVA TESTANDO ESSA PARTE, PARA PESSOA SELECIONAR O ÁUDIO QUE QUERIA CONSIDERAR NO ITS
    # DEPOIS TENTO MEXER NISSO DE NOVO
    
    itens_selecionados = st.multiselect(
        '**Selecione os itens para adicionar ao seu carrinho:**',
        options=[ item['id'] for item in dados],
        default=[] # Começa sem itens selecionados por padrão
    )

    st.subheader('Resultado')

    # 3. Exibir a lista de itens selecionados (a 'outra lista')
    if itens_selecionados:
        st.write(itens_selecionados)
    else:
        st.info('Nenhum item foi selecionado ainda.')

    st.data_editor(dados, column_config={
        "caminho_arquivo": None, 
        "transcricao": "Texto Transcrito"
    })

    uploaded_files = st.file_uploader("Escolha um arquivo", type=['pdf', 'jpeg', 'jpg', 'png', 'csv'], accept_multiple_files=True)

    payload_files = []
    for file in uploaded_files:
        payload_files.append(('files', (file.name, file.getvalue(), file.type)))
    

    list_data = [{'Nome': item.name, 'Tipo': file.type} for item in uploaded_files]
    
    print(itens_selecionados)

    if list_data:
        st.write("Arquivos para serem enviados:")
        st.dataframe(list_data, column_config={
                "caminho_arquivo": None, 
                "transcricao": "Texto Transcrito"
        })

    if st.button("Enviar arquivo(s)", type="primary"):
        try:
            requests.post(f"{API_URL}/upload-arquivo", files=payload_files, params=itens_selecionados)
        except Exception as e:
            st.error(f"Erro: {e}")



with aba_chat:

    with st.container():
        st.markdown('<div class="chat">', unsafe_allow_html=True)
           
        # 2. Inicializar e Exibir o Histórico
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": "Chat pronto! Digite sua primeira mensagem."}]

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # --- 3. Criar o Contêiner Fixo e o Input ---
        # Colocamos o st.chat_input dentro da div 'fixed-footer' para aplicar o CSS.
        with st.container():
            st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
            prompt = st.chat_input("Seu prompt agora deve estar FIXO na parte inferior...")
            st.markdown('</div>', unsafe_allow_html=True)


        # 4. Processamento do Prompt (com st.rerun para evitar duplicação)
        if prompt:
            # Adicionar mensagem do usuário e simular resposta
            st.session_state.messages.append({"role": "user", "content": prompt})
            response = f"Você disse: {prompt}. Estou reexecutando o script..."
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Forçar a reexibição do histórico completo (passo 2)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)




