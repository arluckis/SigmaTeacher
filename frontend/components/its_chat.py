import streamlit as st
import requests
import os
import json
import re
import time
from utils.carregar_sessao import carregar_sessao

API_URL = os.getenv("API_URL", "http://backend:8000")

def extrair_dados_quiz(texto_msg):
    try:
        if not texto_msg: return None
        match = re.search(r'\{.*\}', texto_msg, re.DOTALL)
        if match:
            dados = json.loads(match.group(0))
            # Se for quiz ou conclusão
            if ("pergunta" in dados and "opcoes" in dados) or "status_final" in dados:
                return dados
    except:
        pass
    return None

def render_its_chat(mostrar_audios=True, mostrar_entrada_resposta=True):
    # 1. Config Inicial
    if "session_id" not in st.session_state or not st.session_state.session_id:
        st.error("Sessão não carregada.")
        return

    # 2. Carrega Dados do Quiz Atual (Recuperação)
    if "dados_quiz_atual" not in st.session_state or st.session_state.dados_quiz_atual is None:
        msgs = st.session_state.get("chat_messages", [])
        if msgs:
            for msg in reversed(msgs):
                if msg["role"] in ["assistant", "model"]:
                    quiz_encontrado = extrair_dados_quiz(msg["content"])
                    if quiz_encontrado:
                        st.session_state.dados_quiz_atual = quiz_encontrado
                        break

    # 3. Header e Progresso
    dados_quiz = st.session_state.get("dados_quiz_atual")
    topico = st.session_state.get("topico_atual", "Atividade")
    
    # Se for tela de conclusão, muda o título
    if dados_quiz and dados_quiz.get("status_final") == "concluido":
        topico = "Resultado Final"

    st.markdown(f"## 🎓 {topico}")
    st.divider()

    if not dados_quiz:
        st.warning("Carregando questão...")
        if st.button("Recarregar"):
            carregar_sessao(st.session_state.session_id)
            st.rerun()
        return

    # --- CENÁRIO A: TELA DE CONCLUSÃO ---
    if dados_quiz.get("status_final") == "concluido":
        st.success("🎉 Atividade Finalizada!")
        
        # Placar
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Acertos", dados_quiz.get("score_acertos", 0))
        with col2:
            st.metric("Total de Questões", dados_quiz.get("score_total", 0))
            
        st.markdown(f"### {dados_quiz.get('mensagem_final', '')}")
        st.balloons()
        
        st.divider()
        
        # BOTÃO PARA SAIR
        if st.button("🔙 Voltar para Menu Principal", type="primary", use_container_width=True):
            st.session_state.visualizando_chat_atualmente_aluno = False
            st.session_state.dados_quiz_atual = None
            st.session_state.session_id = None
            st.rerun()
            
        return # Para a execução aqui

    # --- CENÁRIO B: QUESTÃO NORMAL ---
    
    # Pergunta
    with st.container(border=True):
        st.markdown(f"### ❓ {dados_quiz.get('pergunta', 'Erro')}")

    # Controle de Estado da Pergunta
    key_estado = f"quiz_state_{st.session_state.session_id}_{st.session_state.topico_atual}"
    if key_estado not in st.session_state:
        st.session_state[key_estado] = None

    # Botões de Resposta
    if st.session_state[key_estado] is None:
        st.write("Selecione a resposta:")
        opcoes = dados_quiz.get('opcoes', {})
        for letra, texto in opcoes.items():
            if st.button(f"{letra}) {texto}", use_container_width=True, key=f"opt_{letra}"):
                if letra == dados_quiz.get('gabarito'):
                    st.session_state[key_estado] = "correto"
                else:
                    st.session_state[key_estado] = "incorreto"
                st.rerun()

    # Feedback + Botão Próximo
    else:
        gabarito = dados_quiz.get('gabarito')
        texto_gabarito = dados_quiz.get('opcoes', {}).get(gabarito, "")
        
        if st.session_state[key_estado] == "correto":
            st.success(f"✅ **Acertou!** {texto_gabarito}")
            st.markdown(f"_{dados_quiz.get('feedback_acerto', '')}_")
        else:
            st.error(f"❌ **Errou.**")
            st.markdown(f"A resposta certa era: **{gabarito}) {texto_gabarito}**")
            st.info(f"💡 {dados_quiz.get('feedback_erro', '')}")

        st.divider()
        
        if st.button("Próximo Tópico ➡", type="primary", use_container_width=True):
            # Envia flag se acertou para o backend contar pontos
            flag = "AVANCAR_ACERTOU" if st.session_state[key_estado] == "correto" else "AVANCAR_ERROU"
            avancar_topico(flag)

def avancar_topico(flag_msg):
    with st.spinner("Carregando próxima..."):
        try:
            requests.post(
                f"{API_URL}/its/chat",
                json={"session_id": st.session_state.session_id, "mensagem": flag_msg}
            )
            
            # Limpa estado local
            key_estado = f"quiz_state_{st.session_state.session_id}_{st.session_state.topico_atual}"
            if key_estado in st.session_state:
                del st.session_state[key_estado]
            
            st.session_state.dados_quiz_atual = None
            carregar_sessao(st.session_state.session_id)
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")