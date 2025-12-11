import streamlit as st
import requests
from streamlit_mic_recorder import mic_recorder
import pandas as pd
import os
import time

API_URL = os.getenv("API_URL", "http://backend:8000")

# --- FUNÇÕES AUXILIARES ---
def check_backend_status():
    try:
        requests.get(f"{API_URL}/docs", timeout=1)
        return True
    except:
        return False

def buscar_turmas():
    try: return requests.get(f"{API_URL}/professor/listar-turmas", timeout=2).json()
    except: return []

def buscar_alunos_turma(turma_id):
    try: return requests.get(f"{API_URL}/professor/listar-alunos/{turma_id}", timeout=2).json()
    except: return []

def buscar_audios_turma(turma_id):
    try: return requests.get(f"{API_URL}/listar-audios-turma/{turma_id}", timeout=2).json()
    except: return []

def salvar_edicao_transcricao(audio_id, novo_texto):
    """Envia a nova transcrição para o backend salvar no DB"""
    try:
        resp = requests.put(
            f"{API_URL}/editar-transcricao/{audio_id}",
            json={"transcricao": novo_texto}
        )
        if resp.status_code == 200:
            st.success("✅ Transcrição salva!")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Erro ao salvar: {resp.text}")
    except Exception as e:
        st.error(f"Erro de conexão: {e}")

# --- RENDERIZAÇÃO PRINCIPAL ---
def render_professor_area():
    if "novo_aluno_criado" not in st.session_state:
        st.session_state.novo_aluno_criado = None
    
    # Variável para guardar o resultado da transcrição
    if "ultima_transcricao" not in st.session_state:
        st.session_state.ultima_transcricao = {"id": None, "texto": None}

    if not check_backend_status():
        st.error(f"🚨 Sem conexão com o Backend: {API_URL}")
        if st.button("🔄 Tentar Novamente"): st.rerun()
        return

    tabs = st.tabs(["🏫 Gestão", "🎙️ Gravar Aula", "📝 Criar Atividade (ITS)"])

    # ==========================================================
    # ABA 1: GESTÃO
    # ==========================================================
    with tabs[0]:
        st.header("Gestão Escolar")

        if st.session_state.novo_aluno_criado:
            d = st.session_state.novo_aluno_criado
            st.success("✅ Aluno cadastrado com sucesso!")
            st.info(f"### 🔑 CÓDIGO: `{d['codigo']}`")
            if st.button("Fechar"): 
                st.session_state.novo_aluno_criado = None
                st.rerun()
            st.divider()

        c1, c2 = st.columns(2)
        
        # --- CRIAR TURMA (CORREÇÃO DO FALSO ERRO) ---
        with c1:
            st.subheader("1. Criar Turma")
            with st.form("form_turma"):
                nome_t = st.text_input("Nome da Turma")
                prof_t = st.text_input("Professor Responsável")
                
                if st.form_submit_button("Criar Turma"):
                    try:
                        resp = requests.post(f"{API_URL}/professor/criar-turma", json={"nome": nome_t, "professor_nome": prof_t})
                        
                        if resp.status_code == 200:
                            st.success("Turma criada!") # Mensagem clara de sucesso
                            time.sleep(1)
                            st.rerun()
                        else:
                            # Se o status code não é 200, é um erro real do servidor
                            st.error(f"Erro do Servidor: {resp.status_code} - {resp.text}")
                    except requests.exceptions.ConnectionError:
                        st.error("Erro de Conexão: Verifique se o backend está rodando.")
                    except Exception as e:
                        st.error(f"Erro Inesperado: {e}")

        # --- MATRICULAR ALUNO ---
        with c2:
            st.subheader("2. Matricular Aluno")
            turmas = buscar_turmas()
            if turmas:
                opts = {t['nome']: t['id'] for t in turmas}
                sel = st.selectbox("Turma", list(opts.keys()))
                nome_a = st.text_input("Nome Aluno")
                if st.button("Matricular", type="primary"):
                    try:
                        res = requests.post(f"{API_URL}/professor/cadastrar-aluno", json={"nome": nome_a, "turma_id": opts[sel]})
                        if res.status_code == 200:
                            ret = res.json()
                            st.session_state.novo_aluno_criado = {"codigo": ret['codigo_acesso'], "nome": ret['nome'], "turma": sel}
                            st.rerun()
                        else: st.error(f"Erro: {res.text}")
                    except Exception as e: st.error(f"Erro: {e}")

        st.divider()
        st.subheader("📋 Lista de Alunos")
        # ... (Lista de alunos continua igual) ...
        turmas = buscar_turmas()
        if turmas:
            opts = {t['nome']: t['id'] for t in turmas}
            sel_v = st.selectbox("Ver alunos de:", list(opts.keys()), key="v_turma")
            alunos = buscar_alunos_turma(opts[sel_v])
            if alunos:
                df = pd.DataFrame(alunos)
                if not df.empty:
                    st.dataframe(df[['nome', 'codigo_acesso']], use_container_width=True, hide_index=True)
            else: st.info("Sem alunos.")


    # ==========================================================
    # ABA 2: GRAVAR AULA (EDIÇÃO DE TRANSCRIÇÃO)
    # ==========================================================
    with tabs[1]:
        st.header("🎙️ Gravar Aula & Revisão")
        turmas = buscar_turmas()
        
        # 1. UPLOAD SECTION
        with st.container(border=True):
            st.subheader("1. Gravar e Transcrever")
            if turmas:
                opts = {t['nome']: t['id'] for t in turmas}
                t_audio = st.selectbox("Para qual turma?", list(opts.keys()), key="sel_audio")
                
                audio = mic_recorder(start_prompt="🎙️ Iniciar Gravação", stop_prompt="⏹️ Parar Gravação", key="recorder")
                
                if audio:
                    st.audio(audio["bytes"])
                    nome_aula = st.text_input("Título da Aula", value="Nova Aula")
                    if st.button("Salvar e Transcrever"):
                        with st.spinner("Processando e transcrevendo..."):
                            try:
                                files = {"file": (f"{nome_aula}.wav", audio["bytes"], "audio/wav")}
                                resp = requests.post(f"{API_URL}/transcrever-e-salvar", params={"turma_id": opts[t_audio]}, files=files)
                                
                                if resp.status_code == 200:
                                    dados = resp.json()
                                    st.session_state.ultima_transcricao = {
                                        "id": dados.get("id_banco"),
                                        "texto": dados.get("transcricao"),
                                    }
                                    st.success("Transcrição completa!")
                                    st.rerun() # Recarrega para mostrar a área de edição
                                else:
                                    st.error(f"Erro na transcrição: {resp.text}")
                            except Exception as e:
                                st.error(f"Erro de conexão: {e}")
            else:
                st.warning("Crie uma turma primeiro.")

        st.divider()

        # 2. EDIÇÃO SECTION (SÓ APARECE SE HOUVER TRANSCRIÇÃO NA MEMÓRIA)
        if st.session_state.ultima_transcricao["texto"] is not None:
            st.subheader("2. Revisar e Editar Transcrição")
            
            audio_id = st.session_state.ultima_transcricao["id"]
            texto_inicial = st.session_state.ultima_transcricao["texto"]
            
            nova_transcricao = st.text_area(
                "Edite o texto aqui (corrija erros do áudio):",
                value=texto_inicial,
                height=300,
                key="editor_transcricao"
            )
            
            if st.button(f"💾 Salvar Edição no Banco de Dados (ID: {audio_id})", type="primary"):
                # Chamamos a função de salvar
                salvar_edicao_transcricao(audio_id, nova_transcricao)
            
            st.caption("Esta transcrição será usada para gerar as perguntas de quiz.")
        
        elif st.button("Listar Transcrições Salvas"):
            st.info("Para editar, vá na aba Histórico e encontre a aula.")


    # ==========================================================
    # ABA 3: CRIAR ATIVIDADE
    # ==========================================================
    with tabs[2]:
        st.header("Criar Atividade")
        turmas = buscar_turmas()
        if turmas:
            opts_t = {t['nome']: t['id'] for t in turmas}
            t_sel = st.selectbox("1. Turma", list(opts_t.keys()), key="its_t")
            id_t = opts_t[t_sel]
            
            alunos = buscar_alunos_turma(id_t)
            if alunos:
                opts_a = {a['nome']: a['id'] for a in alunos}
                a_sel = st.selectbox("2. Aluno Alvo", list(opts_a.keys()))
                
                audios = buscar_audios_turma(id_t)
                if audios:
                    st.write("3. Selecione o Material Base:")
                    ids_audio = []
                    for au in audios:
                        # Se houver transcrição editada, usa o nome do arquivo + (EDITADO)
                        nome_exibido = au['filename_original']
                        if au.get('transcricao_editada'):
                            nome_exibido += " (EDITADO)"
                            
                        if st.checkbox(f"{nome_exibido}", key=f"chk_{au['id']}"):
                            ids_audio.append(au['id'])
                    
                    st.divider()
                    
                    # Controles de Configuração
                    col_conf1, col_conf2 = st.columns(2)
                    with col_conf1:
                        n_topicos = st.slider("4. Número de Questões:", 3, 10, 5)
                    with col_conf2:
                        publico = st.selectbox(
                            "5. Nível de Ensino:",
                            ["Ensino Fundamental", "Ensino Médio", "Ensino Superior", "Pós-Graduação/Técnico"],
                            index=1
                        )
                    
                    if st.button("🚀 Gerar Atividade", type="primary"):
                        if not ids_audio:
                            st.error("Escolha pelo menos uma aula.")
                        else:
                            with st.spinner("IA criando plano de estudos..."):
                                try:
                                    payload = {
                                        "aluno_id": opts_a[a_sel],
                                        "audio_ids": ids_audio,
                                        "n_topicos": n_topicos,
                                        "audiencia": publico
                                    }
                                    res = requests.post(f"{API_URL}/professor/criar-atividade", json=payload)
                                    if res.status_code == 200:
                                        st.success("Atividade enviada para o aluno!")
                                    else:
                                        st.error(f"Erro: {res.text}")
                                except Exception as e:
                                    st.error(f"Erro de conexão: {e}")
                else:
                    st.warning("Grave uma aula nesta turma primeiro.")
            else:
                st.warning("Cadastre alunos nesta turma primeiro.")