import streamlit as st
import requests
from PIL import Image
from streamlit_mic_recorder import mic_recorder
import os
import json

st.set_page_config(
    page_title="SigmaTeacher",
    page_icon=Image.open("assets/logo_sigma.png"),
    layout="wide",
)

# --- CONFIGURAÇÕES ---
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# --- FUNÇÕES AUXILIARES ---
def listar_audios():
    """Lista todos os áudios gravados"""
    try:
        resp = requests.get(f"{API_URL}/listar-audios")
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error("Erro ao buscar áudios.")
            return []
    except Exception as e:
        st.warning(f"Conecte o servidor backend primeiro. Erro: {e}")
        return []


# --- LOGO PRINCIPAL ---
try:
    logo_principal = Image.open("assets/logo_sigma.png")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(logo_principal, use_container_width=True)
except FileNotFoundError:
    st.title("🎙️ Sigma Teacher")

st.divider()

# --- ABAS PRINCIPAIS ---
aba_gravacao, aba_historico, aba_config_its, aba_chat = st.tabs(
    ["🎙️ VoiceTeacher", "📚 VoiceTeacher History", "⚙️ Configuração do ITS", "💬 VoiceTeacher Chat"]
)

# ====================================================================
# ABA 1: VOICETEACHER (Gravação e Processamento)
# ====================================================================
with aba_gravacao:
    st.header("🎙️ VoiceTeacher")
    st.markdown("""
    Use o **VoiceTeacher** para gravar suas aulas e aumentar o desempenho de seus alunos.
    O áudio será transcrito automaticamente usando IA avançada.
    """)
    
    st.divider()
    
    # Coluna para centralizar o gravador
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        audio_do_botao = mic_recorder(
            start_prompt="🎙️ Iniciar Gravação",
            stop_prompt="⏹️ Encerrar Gravação",
            just_once=False,
            use_container_width=True,
            key='gravador_voiceteacher'
        )
    
    if audio_do_botao:
        st.success("✅ Aula gravada com sucesso!")
        
        # Nome da aula
        nome_aula = st.text_input(
            "Nome da aula:",
            value="aula_voiceteacher.wav",
            key="nome_aula_input"
        )
        
        # Player para conferir
        st.audio(audio_do_botao['bytes'], format="audio/wav")
        
        # Botão de envio
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 Processar Aula no Sigma Teacher", type="primary", use_container_width=True):
                with st.spinner("⏳ Enviando áudio para inteligência artificial..."):
                    files = {"file": (nome_aula, audio_do_botao['bytes'], "audio/wav")}
                    
                    try:
                        response = requests.post(f"{API_URL}/transcrever-e-salvar", files=files)
                        if response.status_code == 200:
                            dados = response.json()
                            st.balloons()
                            st.success("✅ Transcrição Concluída!")
                            st.session_state.ultima_transcricao = dados['transcricao']
                            st.session_state.ultimo_id = dados['id_banco']
                            
                            with st.expander("📄 Ver Transcrição Completa", expanded=True):
                                st.text_area(
                                    "Transcrição:",
                                    value=dados['transcricao'],
                                    height=250,
                                    disabled=True
                                )
                        else:
                            st.error("❌ Erro ao conectar com o servidor.")
                    except Exception as e:
                        st.error(f"❌ Erro: {e}")
        
        with col2:
            if st.button("🔄 Gravar Novamente", use_container_width=True):
                st.rerun()


# ====================================================================
# ABA 2: VOICETEACHER HISTORY (Listagem e Edição)
# ====================================================================
with aba_historico:
    st.header("📚 VoiceTeacher History")
    st.write("Veja todas as aulas transcritas. Você pode editar as transcrições se necessário.")
    
    st.divider()
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 Atualizar Lista", use_container_width=True):
            st.rerun()
    
    # Listar áudios
    audios = listar_audios()
    
    if audios:
        # Exibir cada áudio em um container expansível
        for idx, audio in enumerate(audios):
            with st.expander(f"📝 {audio['filename_original']} - ID: {audio['id']}", expanded=False):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write(f"**Data:** {audio.get('data_criacao', 'N/A')}")
                
                with col2:
                    st.write(f"**ID:** {audio['id']}")
                
                # Área de edição da transcrição
                transcricao_editada = st.text_area(
                    f"Editar transcrição:",
                    value=audio['transcricao'],
                    height=200,
                    key=f"transcricao_edit_{audio['id']}"
                )
                
                # Botão para salvar edição
                if st.button(f"💾 Salvar Edição", key=f"salvar_edit_{audio['id']}", use_container_width=True):
                    try:
                        response = requests.put(
                            f"{API_URL}/editar-transcricao/{audio['id']}",
                            json={"transcricao": transcricao_editada}
                        )
                        if response.status_code == 200:
                            st.success("✅ Transcrição atualizada com sucesso!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao atualizar transcrição.")
                    except Exception as e:
                        st.error(f"❌ Erro: {e}")
                
                st.divider()
    else:
        st.info("📭 Nenhuma aula gravada ainda. Comece pela aba VoiceTeacher!")


# ====================================================================
# ABA 3: CONFIGURAÇÃO DO ITS
# ====================================================================
with aba_config_its:
    st.header("⚙️ Configuração do ITS")
    st.write("Selecione as aulas e materiais de apoio para iniciar a sessão de tutoria inteligente.")
    
    st.divider()
    
    # Seção 1: Seleção de Aulas
    st.subheader("1️⃣ Selecione as Aulas")
    
    audios = listar_audios()
    
    if audios:
        # Criar opções de seleção
        opcoes_audios = {f"{a['filename_original']} (ID: {a['id']})": a['id'] for a in audios}
        
        audios_selecionados = st.multiselect(
            "Aulas a incluir na sessão:",
            options=list(opcoes_audios.keys()),
            key="audios_config_its"
        )
        
        audio_ids_selecionados = [opcoes_audios[opt] for opt in audios_selecionados]
        
        # Exibir resumo das aulas selecionadas
        if audio_ids_selecionados:
            st.info(f"✅ {len(audio_ids_selecionados)} aula(s) selecionada(s)")
            
            # Mostrar tabela das aulas selecionadas
            audios_filtrados = [a for a in audios if a['id'] in audio_ids_selecionados]
            st.dataframe(
                [{"ID": a["id"], "Nome": a["filename_original"]} for a in audios_filtrados],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning("⚠️ Nenhuma aula disponível. Grave uma aula primeiro na aba VoiceTeacher.")
        audio_ids_selecionados = []
    
    st.divider()
    
    # Seção 2: Upload de PDFs
    st.subheader("2️⃣ Carregue PDFs (Opcional)")
    
    uploaded_files = st.file_uploader(
        "Selecione PDFs para complementar as aulas:",
        type=['pdf'],
        accept_multiple_files=True,
        key="pdf_uploader_its"
    )
    
    caminhos_pdf = []
    if uploaded_files:
        st.write(f"📄 {len(uploaded_files)} arquivo(s) selecionado(s):")
        for file in uploaded_files:
            st.write(f"  • {file.name}")
    
    st.divider()
    
    # Seção 3: Configurações do ITS
    st.subheader("3️⃣ Configurações da Sessão")
    
    col1, col2 = st.columns(2)
    
    with col1:
        n_topicos = st.slider(
            "Número de tópicos:",
            min_value=3,
            max_value=15,
            value=5,
            key="n_topicos_its"
        )
    
    with col2:
        audiencia = st.selectbox(
            "Público-alvo:",
            options=[
                "1° ano do ensino fundamental",
                "5° ano do ensino fundamental",
                "1° ano do ensino médio",
                "2° ano do ensino médio",
                "3° ano do ensino médio",
                "Ensino superior",
                "Adultos em geral"
            ],
            index=2,
            key="audiencia_its"
        )
    
    st.divider()
    
    # Seção 4: Botão de Iniciar
    st.subheader("4️⃣ Iniciar Sessão")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button(
            "🚀 Iniciar Sessão de Tutoria",
            type="primary",
            use_container_width=True,
            key="iniciar_tutoria_btn"
        ):
            # Validação
            if not audio_ids_selecionados:
                st.error("❌ Selecione pelo menos uma aula!")
            else:
                with st.spinner("⏳ Processando conteúdo e gerando modelo de domínio..."):
                    try:
                        # Salvar PDFs temporários
                        caminhos_pdf_temp = []
                        for file in uploaded_files:
                            caminho_temp = f"uploads/temp_{file.name}"
                            with open(caminho_temp, "wb") as f:
                                f.write(file.getbuffer())
                            caminhos_pdf_temp.append(caminho_temp)
                        
                        # Fazer requisição para iniciar tutoria
                        payload = {
                            "audio_ids": audio_ids_selecionados,
                            "caminhos_pdf": caminhos_pdf_temp,
                            "n_topicos": n_topicos,
                            "audiencia": audiencia
                        }
                        
                        response = requests.post(
                            f"{API_URL}/its/iniciar",
                            json=payload,
                            timeout=120  # Timeout aumentado para processamento
                        )
                        
                        if response.status_code == 200:
                            dados = response.json()
                            st.balloons()
                            st.success("✅ Sessão de tutoria iniciada com sucesso!")
                            
                            # Salvar na sessão
                            st.session_state.session_id = dados['session_id']
                            st.session_state.mensagem_bot = dados['mensagem_bot']
                            st.session_state.topico_atual = dados['topico']
                            st.session_state.chat_iniciado = True
                            
                            st.info(f"📌 Sessão ID: {dados['session_id']}")
                            st.write(f"**Primeira mensagem do tutor:**\n\n{dados['mensagem_bot']}")
                            
                            st.success("✨ Navegue até a aba 'VoiceTeacher Chat' para começar a aprender!")
                        else:
                            error_msg = response.json().get('detail', 'Erro desconhecido')
                            st.error(f"❌ Erro ao iniciar sessão: {error_msg}")
                    except requests.exceptions.Timeout:
                        st.error("⏱️ Timeout: O processamento demorou muito. Tente novamente com menos tópicos.")
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")


# ====================================================================
# ABA 4: VOICETEACHER CHAT (Sessão de Tutoria)
# ====================================================================
with aba_chat:
    st.header("💬 VoiceTeacher Chat - Sessão de Tutoria")
    
    # Inicializar estado da sessão
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    
    if "chat_iniciado" not in st.session_state:
        st.session_state.chat_iniciado = False
    
    # Se não há sessão iniciada, mostrar mensagem
    if not st.session_state.chat_iniciado or not st.session_state.session_id:
        st.info("📌 Nenhuma sessão ativa. Configure e inicie uma sessão na aba 'Configuração do ITS'.")
    else:
        # Exibir informações da sessão
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Session ID:** {st.session_state.session_id}")
        with col2:
            st.write(f"**Tópico:** {st.session_state.topico_atual}")
        with col3:
            if st.button("🔄 Nova Sessão", key="nova_sessao_btn"):
                st.session_state.chat_iniciado = False
                st.session_state.session_id = None
                st.session_state.chat_messages = []
                st.rerun()
        
        st.divider()
        
        # Container para o chat
        chat_container = st.container(height=400, border=True)
        
        with chat_container:
            # Exibir mensagens do histórico
            for message in st.session_state.chat_messages:
                if message["role"] == "user":
                    with st.chat_message("user", avatar="👤"):
                        st.markdown(message["content"])
                else:
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(message["content"])
            
            # Se é a primeira mensagem, mostrar a mensagem inicial do bot
            if not st.session_state.chat_messages and "mensagem_bot" in st.session_state:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(st.session_state.mensagem_bot)
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": st.session_state.mensagem_bot
                })
        
        # Input do usuário
        st.divider()
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            user_input = st.text_input(
                "Sua resposta:",
                placeholder="Digite sua resposta aqui...",
                key="user_input_its"
            )
        
        with col2:
            send_button = st.button("📤 Enviar", type="primary", use_container_width=True)
        
        # Processar resposta do usuário
        if send_button and user_input:
            # Adicionar mensagem do usuário
            st.session_state.chat_messages.append({
                "role": "user",
                "content": user_input
            })
            
            # Enviar para backend
            with st.spinner("⏳ Processando resposta..."):
                try:
                    response = requests.post(
                        f"{API_URL}/its/chat",
                        json={
                            "session_id": st.session_state.session_id,
                            "mensagem": user_input
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        dados = response.json()
                        
                        # Adicionar resposta do bot
                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": dados['mensagem_bot']
                        })
                        
                        # Atualizar status
                        st.session_state.topico_atual = dados.get('topico_atual', st.session_state.topico_atual)
                        
                        # Se a sessão foi concluída
                        if dados.get('status_atual') == 'concluido':
                            st.success("🎉 Parabéns! Você completou a sessão de tutoria!")
                            st.balloons()
                        
                        st.rerun()
                    else:
                        erro_msg = response.json().get('detail', 'Erro desconhecido')
                        st.error(f"❌ Erro: {erro_msg}")
                except requests.exceptions.Timeout:
                    st.error("⏱️ Timeout: A resposta demorou muito.")
                except Exception as e:
                    st.error(f"❌ Erro ao enviar resposta: {str(e)}")

st.divider()
st.caption("🎓 SigmaTeacher - Plataforma de Tutoria Inteligente")




