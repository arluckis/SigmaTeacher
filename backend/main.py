from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import whisper
import shutil
import os
import uuid
import json
from datetime import datetime
from pydantic import BaseModel
from typing import List
from backend import its

# --- 1. CONFIGURAÇÃO DO BANCO DE DADOS (SQLite) ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./sigma_teacher.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Define a tabela do banco
class AudioLog(Base):
    __tablename__ = "audios"

    id = Column(Integer, primary_key=True, index=True)
    filename_original = Column(String)  # Nome que o usuário mandou
    caminho_arquivo = Column(String)  # Onde salvamos no disco
    transcricao = Column(Text)  # O texto gerado pelo Whisper
    transcricao_editada = Column(
        Text, nullable=True
    )  # Transcrição editada pelo usuário
    data_criacao = Column(DateTime, default=datetime.utcnow)


# Define a tabela para sessões de tutoria
class TutoriaSession(Base):
    __tablename__ = "sessoes_tutoria"

    id = Column(Integer, primary_key=True, index=True)
    # Guardamos estruturas complexas como TEXT (JSON stringfied)
    modelo_dominio = Column(Text)  # O que deve ser ensinado
    modelo_aluno = Column(Text)  # O nível atual do aluno
    historico_chat = Column(Text)  # Lista de mensagens para o contexto do LLM
    topico_atual = Column(String)  # O tópico sendo ensinado agora
    status = Column(String)  # "ativo", "concluido"
    audio_ids = Column(String, default="[]")
    data_criacao = Column(DateTime, default=datetime.utcnow)


# Cria o arquivo do banco de dados se não existir
Base.metadata.create_all(bind=engine)

# --- 2. CONFIGURAÇÃO DO WHISPER ---
print("Carregando modelo...")
modelo = whisper.load_model("small")  # Usando o Medium como você validou

# --- 3. CONFIGURAÇÃO DO APP ---
app = FastAPI()

# Adicionar CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cria a pastinha para salvar os arquivos físicos
os.makedirs("uploads", exist_ok=True)


# Dependência para pegar a sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/transcrever-e-salvar")
async def processar_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # A. Gerar um nome único (para não sobrescrever arquivos com mesmo nome)
    # Ex: "audio.mp3" vira "f47ac10b-58cc...audio.mp3"
    nome_unico = f"{uuid.uuid4()}_{file.filename}"
    caminho_final = f"uploads/{nome_unico}"

    # B. Salvar o arquivo na pasta 'uploads'
    with open(caminho_final, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # C. Transcrever
    print(f"Transcrevendo {caminho_final}...")
    resultado = modelo.transcribe(caminho_final, language="pt", temperature=0)
    texto_extraido = resultado["text"]

    # D. Salvar no Banco de Dados
    novo_registro = AudioLog(
        filename_original=file.filename,
        caminho_arquivo=caminho_final,
        transcricao=texto_extraido,
    )

    db.add(novo_registro)
    db.commit()  # Confirma a gravação
    db.refresh(novo_registro)  # Atualiza para pegar o ID gerado

    return {
        "status": "sucesso",
        "id_banco": novo_registro.id,
        "transcricao": texto_extraido,
    }


# Rota extra: Listar tudo que já foi salvo
@app.get("/listar-audios")
def listar(db: Session = Depends(get_db)):
    audios = db.query(AudioLog).all()
    return [
        {
            "id": a.id,
            "filename_original": a.filename_original,
            "transcricao": a.transcricao_editada or a.transcricao,
            "data_criacao": a.data_criacao.isoformat() if a.data_criacao else None,
        }
        for a in audios
    ]


# Rota para editar transcrição
@app.put("/editar-transcricao/{audio_id}")
async def editar_transcricao(
    audio_id: int, nova_transcricao: dict, db: Session = Depends(get_db)
):
    """Edita a transcrição de um áudio"""
    audio = db.query(AudioLog).filter(AudioLog.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")

    audio.transcricao_editada = nova_transcricao.get("transcricao", audio.transcricao)
    db.commit()

    return {
        "status": "sucesso",
        "id": audio.id,
        "transcricao": audio.transcricao_editada,
    }


@app.post("/upload-arquivo")
async def upload_arquivos(
    files: List[UploadFile] = File(...),
    audio_ids: List[int] = [],
):
    """
    Valida os arquivos enviados para o ITS.
    Retorna lista de arquivos salvos temporariamente.
    """
    caminhos_salvos = []

    for file in files:
        if file.filename.endswith((".pdf", ".jpeg", ".jpg", ".png", ".csv")):
            temp_path = f"uploads/temp_{uuid.uuid4()}_{file.filename}"
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            caminhos_salvos.append({"arquivo": file.filename, "caminho": temp_path})

    # Validar que pelo menos uma aula foi selecionada
    if not audio_ids:
        return {
            "status": "erro",
            "detalhe": "Selecione pelo menos uma aula para iniciar o ITS",
        }

    return {
        "status": "sucesso",
        "arquivos_salvos": caminhos_salvos,
        "audio_ids": audio_ids,
    }


@app.get("/its/sessoes")
def listar_sessoes(db: Session = Depends(get_db)):
    """Retorna uma lista simplificada das sessões para o aluno selecionar"""
    sessoes = (
        db.query(TutoriaSession).order_by(TutoriaSession.data_criacao.desc()).all()
    )

    lista_retorno = []
    for s in sessoes:
        topico = s.topico_atual or "Geral"

        lista_retorno.append(
            {
                "id": s.id,
                "topico": topico,
                "status": s.status,
                "data_criacao": s.data_criacao.isoformat() if s.data_criacao else None,
            }
        )
    return lista_retorno


@app.get("/its/sessao/{session_id}")
def obter_sessao(session_id: int, db: Session = Depends(get_db)):
    """Retorna o histórico e estado atual de uma sessão para o frontend restaurar"""
    sessao = db.query(TutoriaSession).filter(TutoriaSession.id == session_id).first()
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # Carregar histórico para enviar ao frontend formatado
    historico_bruto = its.carregar_json(sessao.historico_chat)

    # Converter formato do Gemini/LLM para formato do Streamlit (role: user/assistant)
    mensagens_frontend = []
    for h in historico_bruto:
        role = "user" if h.get("role") == "user" else "assistant"
        content = h.get("parts", [{}])[0].get("text", "")
        mensagens_frontend.append({"role": role, "content": content})

    lista_audios = []
    if sessao.audio_ids:
        ids = its.carregar_json(sessao.audio_ids)
        if ids:
            audios_db = db.query(AudioLog).filter(AudioLog.id.in_(ids)).all()
            for a in audios_db:
                lista_audios.append(
                    {
                        "id": a.id,
                        "filename_original": a.filename_original,
                        "transcricao": a.transcricao_editada or a.transcricao,
                        "data_criacao": a.data_criacao.isoformat()
                        if a.data_criacao
                        else None,
                    }
                )

    return {
        "id": sessao.id,
        "topico_atual": sessao.topico_atual,
        "status": sessao.status,
        "mensagens": mensagens_frontend,
        "audios_contexto": lista_audios,
    }


class UserResponse(BaseModel):
    session_id: int
    mensagem: str


class IniciarTutoriaRequest(BaseModel):
    audio_ids: List[int]
    caminhos_pdf: List[str] = []
    n_topicos: int = 5
    audiencia: str = "1° ano do ensino médio"


@app.post("/its/iniciar")
async def iniciar_tutoria(
    request: IniciarTutoriaRequest,
    db: Session = Depends(get_db),
):
    # --- 1. Validações e Recuperação de Áudio (Igual ao anterior) ---
    if not request.audio_ids:
        raise HTTPException(status_code=400, detail="Selecione pelo menos uma aula")

    texto_completo_audios = ""
    registros = db.query(AudioLog).filter(AudioLog.id.in_(request.audio_ids)).all()
    if not registros:
        raise HTTPException(status_code=404, detail="Aulas não encontradas")

    for reg in registros:
        texto = reg.transcricao_editada or reg.transcricao
        texto_completo_audios += f"\n--- Aula: {reg.filename_original} ---\n{texto}"

    # --- 2. Gerar Modelo de Domínio ---
    print("--- Gerando Modelo de Domínio... ---")
    modelo_dominio = its.etapa_0_prep_modelo_dominio(
        transcricao_audio=texto_completo_audios,
        caminhos_pdf=request.caminhos_pdf,
        n_topicos=request.n_topicos,
        audiencia=request.audiencia,
    )

    if not modelo_dominio:
        raise HTTPException(status_code=500, detail="Erro ao gerar Modelo de Domínio.")

    # Limpar PDFs temporários
    for path in request.caminhos_pdf:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # --- 3. Inicializar Aluno ---
    modelo_aluno = its.etapa_0_inicializar_aluno(modelo_dominio)

    # --- 4. Selecionar 1º Tópico ---
    topico_inicial = its.etapa_1_selecao_proximo_topico(modelo_aluno, modelo_dominio)

    if not topico_inicial:
        # Caso raro onde já começa concluído ou erro
        topico_inicial = list(modelo_dominio.keys())[0] if modelo_dominio else "Geral"

    topico_info = modelo_dominio.get(topico_inicial, {})

    mensagem_bot = (
        f"👋 **Bem-vindo à sua tutoria!**\n\n"
        f"Vamos começar estudando: **{topico_inicial}**\n\n"
        f"📖 *Explicação:* {topico_info.get('explicacao', 'Sem explicação disponível.')}\n\n"
        f"✍️ **Exercício:** {topico_info.get('exercicio', '')}"
    )

    # Criar histórico inicial
    historico_inicial = [{"role": "model", "parts": [{"text": mensagem_bot}]}]

    # --- 5. Salvar Sessão ---
    sessao = TutoriaSession(
        modelo_dominio=its.salvar_json(modelo_dominio),
        modelo_aluno=its.salvar_json(modelo_aluno),
        historico_chat=its.salvar_json(historico_inicial),
        topico_atual=topico_inicial,
        status="aguardando_resposta_exercicio",
        audio_ids=its.salvar_json(request.audio_ids),
    )

    db.add(sessao)
    db.commit()
    db.refresh(sessao)

    return {
        "status": "sucesso",
        "session_id": sessao.id,
        "topico_atual": topico_inicial,
        "mensagem_bot": mensagem_bot,
        "exercicio": topico_info.get("exercicio", ""),
    }


@app.post("/its/chat")
async def responder_chat(dados: UserResponse, db: Session = Depends(get_db)):
    """
    Ciclo de feedback e adaptação.
    """
    sessao = (
        db.query(TutoriaSession).filter(TutoriaSession.id == dados.session_id).first()
    )
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # Carregar estruturas
    mod_dominio = its.carregar_json(sessao.modelo_dominio)
    mod_aluno = its.carregar_json(sessao.modelo_aluno)
    historico = its.carregar_json(sessao.historico_chat)
    topico_atual = sessao.topico_atual

    # Adicionar resposta do usuário ao histórico
    historico.append({"role": "user", "parts": [{"text": dados.mensagem}]})

    resposta_final_bot = ""
    proxima_acao = "revisar"  # padrão

    # --- LÓGICA DO ESTADO ---

    if sessao.status == "aguardando_resposta_exercicio":
        # 1. Avaliar a resposta (Etapa 3)
        resultado_avaliacao, mod_aluno = its.etapa_3_avaliacao_interacao_inicial(
            historico, mod_aluno, topico_atual, mod_dominio
        )

        acertou = (
            resultado_avaliacao.get("acertou", False) if resultado_avaliacao else False
        )

        # 2. Gerar Feedback (Etapa 4/5)
        exercicio_atual = mod_dominio.get(topico_atual, {}).get("exercicio", "")

        resultado_feedback = its.etapa_45_decidir_e_gerar_feedback(
            exercicio=exercicio_atual,
            resposta_aluno=dados.mensagem,
            modelo_dominio=mod_dominio,
            topico_atual=topico_atual,
            acertou=acertou,
        )

        feedback_texto = resultado_feedback.get("mensagem_ao_aluno", "")
        proxima_acao = resultado_feedback.get("proxima_acao", "revisar")

        if acertou or proxima_acao == "avancar":
            resposta_final_bot = f"{feedback_texto}\n\n🎉 **Muito bem! Vamos avançar?** (Responda qualquer coisa para continuar)"
            sessao.status = "aguardando_transicao"  # Estado intermediário para o aluno ler o feedback
        else:
            resposta_final_bot = f"{feedback_texto}\n\n🔄 **Tente explicar novamente com suas palavras ou peça uma dica.**"
            sessao.status = (
                "aguardando_resposta_exercicio"  # Mantém no loop de exercício
            )

    elif sessao.status == "aguardando_transicao":
        # O aluno leu o feedback positivo e respondeu "ok", "vamos", etc.
        # Agora selecionamos o próximo tópico (Etapa 7 e 1)

        # Atualiza progresso geral (Etapa 7)
        mod_aluno = its.etapa_7_atualizacao_pos_feedback(
            historico, mod_aluno, mod_dominio
        )

        # Seleciona próximo tópico (Etapa 1)
        novo_topico = its.etapa_1_selecao_proximo_topico(mod_aluno, mod_dominio)

        if not novo_topico:
            # Não há mais tópicos pendentes
            resposta_final_bot = "🎓 **Parabéns! Você concluiu todos os tópicos planejados para esta aula.**"
            sessao.status = "concluido"
        else:
            # Avança para o próximo
            sessao.topico_atual = novo_topico
            topico_info = mod_dominio.get(novo_topico, {})

            resposta_final_bot = (
                f"🚀 **Próximo Tópico: {novo_topico}**\n\n"
                f"📖 {topico_info.get('explicacao', '')}\n\n"
                f"✍️ **Exercício:** {topico_info.get('exercicio', '')}"
            )
            sessao.status = "aguardando_resposta_exercicio"

    elif sessao.status == "concluido":
        resposta_final_bot = (
            "O curso já foi concluído! Você pode iniciar uma nova sessão se desejar."
        )

    else:
        # Fallback para estados desconhecidos
        resposta_final_bot = "Não entendi. Podemos continuar o exercício?"
        sessao.status = "aguardando_resposta_exercicio"

    # --- FINALIZAÇÃO ---
    historico.append({"role": "model", "parts": [{"text": resposta_final_bot}]})

    sessao.modelo_aluno = its.salvar_json(mod_aluno)
    sessao.historico_chat = its.salvar_json(historico)

    db.commit()

    return {
        "session_id": sessao.id,
        "mensagem_bot": resposta_final_bot,
        "status_atual": sessao.status,
        "topico_atual": sessao.topico_atual,
        "progresso": mod_aluno.get("progresso_total", 0),
    }


# --- Funções Auxiliares ---
def salvar_json(obj):
    """Converte objeto para JSON string"""
    return json.dumps(obj, ensure_ascii=False, default=str)


def carregar_json(json_str):
    """Converte JSON string para objeto"""
    if not json_str:
        return {}
    return json.loads(json_str)
