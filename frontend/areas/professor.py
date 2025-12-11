from datetime import datetime
import streamlit as st
import requests
from streamlit_mic_recorder import mic_recorder
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


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


def render_professor_area():
    # --- ABAS PRINCIPAIS ---
    aba_gravacao, aba_historico, aba_config_its, aba_chat = st.tabs(
        [
            "🎙️ VoiceTeacher",
            "📚 Histórico de áudios",
            "⚙️ Configuração do ITS",
            "📖 Lista de sessões disponíveis",
        ]
    )

    with aba_gravacao:
        st.header("🎙️ VoiceTeacher")
        st.markdown("""
        Use o **VoiceTeacher** para gravar suas aulas e aumentar o desempenho de seus alunos.
        O áudio será transcrito automaticamente usando IA Speech-to-Text.
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
                key="gravador_voiceteacher",
            )

        if audio_do_botao:
            st.success("✅ Aula gravada com sucesso!")

            # Nome da aula
            nome_aula = st.text_input(
                "Nome da aula:", value="Nome da aula gravada", key="nome_aula_input"
            )

            # Player para conferir
            st.audio(audio_do_botao["bytes"], format="audio/wav")

            if st.button(
                "🚀 Processar Aula no Sigma Teacher", type="primary", width="stretch"
            ):
                with st.spinner("⏳ Enviando áudio para inteligência artificial..."):
                    files = {"file": (nome_aula, audio_do_botao["bytes"], "audio/wav")}

                    try:
                        response = requests.post(
                            f"{API_URL}/transcrever-e-salvar", files=files
                        )
                        if response.status_code == 200:
                            dados = response.json()
                            st.balloons()
                            st.success("✅ Transcrição Concluída!")
                            st.session_state.ultima_transcricao = dados["transcricao"]
                            st.session_state.ultimo_id = dados["id_banco"]

                            with st.expander(
                                "📄 Ver Transcrição Completa", expanded=True
                            ):
                                st.text_area(
                                    "Transcrição:",
                                    value=dados["transcricao"],
                                    height=250,
                                    disabled=True,
                                )
                        else:
                            st.error("❌ Erro ao conectar com o servidor.")
                    except Exception as e:
                        st.error(f"❌ Erro: {e}")

    with aba_historico:
        st.header("📚 Histórico de áudios")
        st.write(
            "Veja todas as aulas transcritas. Você pode editar as transcrições se necessário."
        )

        st.divider()

        _, col2 = st.columns([4, 1])

        with col2:
            if st.button("🔄 Atualizar Lista", use_container_width=True):
                st.rerun()

        # Listar áudios
        audios = listar_audios()

        if audios:
            # Exibir cada áudio em um container expansível
            for _, audio in enumerate(audios):
                with st.expander(
                    f"📝 {audio['filename_original']} - ID: {audio['id']}",
                    expanded=False,
                ):
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        st.write(f"**Data:** {audio.get('data_criacao', 'N/A')}")

                    with col2:
                        st.write(f"**ID:** {audio['id']}")

                    # Área de edição da transcrição
                    transcricao_editada = st.text_area(
                        "Editar transcrição:",
                        value=audio["transcricao"],
                        height=200,
                        key=f"transcricao_edit_{audio['id']}",
                    )

                    # Botão para salvar edição
                    if st.button(
                        "💾 Salvar Edição",
                        key=f"salvar_edit_{audio['id']}",
                        width="stretch",
                    ):
                        try:
                            response = requests.put(
                                f"{API_URL}/editar-transcricao/{audio['id']}",
                                json={"transcricao": transcricao_editada},
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

    with aba_config_its:
        st.header("⚙️ Configuração do ITS")
        st.write(
            "Selecione as aulas e materiais de apoio para iniciar a sessão de tutoria inteligente."
        )

        st.divider()

        # Seção 1: Seleção de Aulas
        st.subheader("1️⃣ Selecione as Aulas")

        audios = listar_audios()

        if audios:
            # Criar opções de seleção
            opcoes_audios = {
                f"{a['filename_original']} (ID: {a['id']})": a["id"] for a in audios
            }

            audios_selecionados = st.multiselect(
                "Aulas a incluir na sessão:",
                options=list(opcoes_audios.keys()),
                key="audios_config_its",
            )

            audio_ids_selecionados = [opcoes_audios[opt] for opt in audios_selecionados]

            # Exibir resumo das aulas selecionadas
            if audio_ids_selecionados:
                st.info(f"✅ {len(audio_ids_selecionados)} aula(s) selecionada(s)")

                # Mostrar tabela das aulas selecionadas
                audios_filtrados = [
                    a for a in audios if a["id"] in audio_ids_selecionados
                ]
                st.dataframe(
                    [
                        {"ID": a["id"], "Nome": a["filename_original"]}
                        for a in audios_filtrados
                    ],
                    width="stretch",
                    hide_index=True,
                )
        else:
            st.warning(
                "⚠️ Nenhuma aula disponível. Grave uma aula primeiro na aba VoiceTeacher."
            )
            audio_ids_selecionados = []

        st.divider()

        # Seção 2: Upload de PDFs
        st.subheader("2️⃣ Carregue PDFs (Opcional)")

        uploaded_files = st.file_uploader(
            "Selecione PDFs para complementar as aulas:",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_uploader_its",
        )

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
                key="n_topicos_its",
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
                    "Adultos em geral",
                ],
                index=2,
                key="audiencia_its",
            )

        st.divider()

        # Seção 4: Botão de Iniciar
        st.subheader("4️⃣ Iniciar Sessão")

        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            if st.button(
                "🚀 Iniciar Sessão de Tutoria",
                type="primary",
                width="stretch",
                key="iniciar_tutoria_btn",
            ):
                # Validação
                if not audio_ids_selecionados:
                    st.error("❌ Selecione pelo menos uma aula!")
                else:
                    with st.spinner(
                        "⏳ Processando conteúdo e gerando modelo de domínio..."
                    ):
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
                                "audiencia": audiencia,
                            }

                            response = requests.post(
                                f"{API_URL}/its/iniciar",
                                json=payload,
                                timeout=120,
                            )

                            if response.status_code == 200:
                                dados = response.json()
                                st.balloons()
                                st.success("✅ Sessão de tutoria criada com sucesso!")

                                st.info(f"📌 Sessão ID: {dados['session_id']}")
                                st.write(
                                    f"**Primeira mensagem do tutor:**\n\n{dados['mensagem_bot']}"
                                )
                            else:
                                error_msg = response.json().get(
                                    "detail", "Erro desconhecido"
                                )
                                st.error(f"❌ Erro ao iniciar sessão: {error_msg}")
                        except requests.exceptions.Timeout:
                            st.error(
                                "⏱️ Timeout: O processamento demorou muito. Tente novamente com menos tópicos."
                            )
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")

    with aba_chat:
        st.header("📖 Lista de sessões disponíveis")
        st.write("Abaixo as sessões que os alunos podem entrar.")

        st.divider()

        _, col_top_2 = st.columns([4, 1])
        with col_top_2:
            if st.button(
                "🔄 Atualizar Lista",
                key="btn_atualizar_sessoes",
                use_container_width=True,
            ):
                st.rerun()

        # Busca sessões no backend
        try:
            resp = requests.get(f"{API_URL}/its/sessoes")
            if resp.status_code == 200:
                sessoes = resp.json()
            else:
                sessoes = []
                st.error("Não foi possível buscar as sessões.")
        except Exception:
            sessoes = []
            st.warning("Conecte o backend para ver as sessões.")

        if not sessoes:
            st.info("Nenhuma sessão encontrada. Peça ao professor para criar uma nova!")
        else:
            c1, c2, c3 = st.columns([0.5, 4, 2])
            c1.markdown("**ID**")
            c2.markdown("**Tópico / Data**")
            c3.markdown("**Status**")

            st.divider()

            for sessao in sessoes:
                c1, c2, c3 = st.columns([0.5, 4, 2])

                with c1:
                    st.write(f"#{sessao['id']}")

                with c2:
                    st.markdown(f"**{sessao['topico']}**")

                    data_raw = sessao.get("data_criacao")
                    if data_raw:
                        try:
                            dt_obj = datetime.fromisoformat(data_raw)
                            data_fmt = dt_obj.strftime("%d/%m/%Y %H:%M")
                        except ValueError:
                            data_fmt = data_raw
                    else:
                        data_fmt = "Data desconhecida"

                    st.caption(f"📅 {data_fmt}")

                with c3:
                    if sessao["status"] == "concluido":
                        st.markdown(":green[✅ **Concluído**]")
                    else:
                        st.markdown(":blue[⏳ **Em andamento**]")
