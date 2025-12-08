from fastapi import FastAPI, UploadFile, File, Depends
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import whisper
import shutil
import os
import uuid
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


# Cria o arquivo do banco de dados se não existir
Base.metadata.create_all(bind=engine)

# --- 2. CONFIGURAÇÃO DO WHISPER ---
print("Carregando modelo...")
modelo = whisper.load_model("small")  # Usando o Medium como você validou

# --- 3. CONFIGURAÇÃO DO APP ---
app = FastAPI()

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
    return audios


@app.post("/upload-arquivo")
async def upload_arquivos(
    files: List[UploadFile] = File(...),
    listAudios: List[int] = [],
    db: Session = Depends(get_db),
):
    for file in files:
        print(file.name)
    for id in listAudios:
        print(id)


class UserResponse(BaseModel):
    session_id: int
    mensagem: str


@app.post("/its/iniciar")
async def iniciar_tutoria(
    files: List[UploadFile] = File(default=[]),
    audio_ids: List[int] = [],
    db: Session = Depends(get_db),
):
    """
    1. Pega transcrições do banco.
    2. Processa PDFs enviados agora.
    3. Gera Modelo de Domínio.
    4. Seleciona 1º Tópico.
    5. Cria Sessão no Banco.
    """

    # 1. Recuperar Transcrições dos Áudios
    texto_completo_audios = ""
    if audio_ids:
        registros = db.query(AudioLog).filter(AudioLog.id.in_(audio_ids)).all()
        for reg in registros:
            texto_completo_audios += f"\nTranscr: {reg.transcricao}"

    # 2. Salvar PDFs Temporários para Enviar ao Gemini
    caminhos_pdf = []
    for file in files:
        if file.filename.endswith(".pdf"):
            temp_path = f"uploads/temp_{uuid.uuid4()}_{file.filename}"
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            caminhos_pdf.append(temp_path)

    # 3. Gerar Modelo de Domínio (Etapa 0)
    try:
        modelo_dominio = its.etapa_0_prep_modelo_dominio(
            transcricao_audio=texto_completo_audios,
            caminhos_pdf=caminhos_pdf,
            n_topicos=5,  # Menos tópicos para teste rápido
        )
    finally:
        # Limpeza: Remover PDFs temporários
        for path in caminhos_pdf:
            if os.path.exists(path):
                os.remove(path)

    if not modelo_dominio or "ERRO" in modelo_dominio:
        return {"status": "erro", "detalhe": "Falha ao gerar domínio via LLM"}

    # 4. Inicializar Aluno e Selecionar 1º Tópico
    modelo_aluno = its.etapa_0_inicializar_aluno(modelo_dominio)
    decisao = its.etapa_1_selecao_proximo_topico(modelo_aluno)
    topico_atual = decisao.get("proximo_topico")

    # Preparar primeira mensagem do sistema
    explicacao = modelo_dominio[topico_atual]["explicacao"]
    exercicio = modelo_dominio[topico_atual]["exercicio"]
    msg_sistema = f"Olá! Vamos começar. \nTópico: {topico_atual}\nExplicação: {explicacao}\n\nExercício: {exercicio}"

    # Histórico inicial (formato do Gemini)
    historico = [{"role": "model", "parts": [{"text": msg_sistema}]}]

    # 5. Salvar Sessão no Banco
    nova_sessao = TutoriaSession(
        modelo_dominio=its.salvar_json(modelo_dominio),
        modelo_aluno=its.salvar_json(modelo_aluno),
        historico_chat=its.salvar_json(historico),
        topico_atual=topico_atual,
        status="aguardando_resposta_exercicio",
    )
    db.add(nova_sessao)
    db.commit()
    db.refresh(nova_sessao)

    return {
        "session_id": nova_sessao.id,
        "mensagem_bot": msg_sistema,
        "topico": topico_atual,
    }


@app.post("/its/chat")
async def responder_chat(dados: UserResponse, db: Session = Depends(get_db)):
    """
    Recebe a resposta do aluno e roda o ciclo do ITS (Etapas 3 a 7).
    """
    sessao = (
        db.query(TutoriaSession).filter(TutoriaSession.id == dados.session_id).first()
    )
    if not sessao:
        return {"erro": "Sessão não encontrada"}

    # Carregar estado do banco (Deserializar JSON)
    mod_dominio = its.carregar_json(sessao.modelo_dominio)
    mod_aluno = its.carregar_json(sessao.modelo_aluno)
    historico = its.carregar_json(sessao.historico_chat)
    topico_atual = sessao.topico_atual

    # Adicionar mensagem do usuário ao histórico
    historico.append({"role": "user", "parts": [{"text": dados.mensagem}]})

    resposta_final_bot = ""

    # LÓGICA DO FLUXO

    if sessao.status == "aguardando_resposta_exercicio":
        # --- O aluno respondeu o exercício. Avaliar (Etapa 3) ---

        avaliacao, mod_aluno = its.etapa_3_avaliacao_interacao_inicial(
            historico, mod_aluno, topico_atual
        )

        # Gerar Feedback (Etapa 4/5)
        exercicio_atual = mod_dominio[topico_atual]["exercicio"]
        feedback = its.etapa_45_decidir_e_gerar_feedback(
            exercicio_atual, dados.mensagem
        )

        resposta_final_bot = feedback + "\n\n(Diga se entendeu ou se ainda tem dúvidas)"

        sessao.status = "aguardando_reacao_feedback"

    elif sessao.status == "aguardando_reacao_feedback":
        # --- O aluno reagiu ao feedback. Ajuste fino (Etapa 7) ---

        # Verificar se avançamos
        nivel_atual = mod_aluno.get(topico_atual)

        if nivel_atual == "avançado" or nivel_atual == "intermediário":
            # Tentar pegar próximo tópico
            decisao = its.etapa_1_selecao_proximo_topico(mod_aluno)
            novo_topico = decisao.get("proximo_topico")

            if novo_topico and novo_topico != topico_atual:
                # Mudança de Tópico
                topico_atual = novo_topico
                explicacao = mod_dominio[topico_atual]["explicacao"]
                exercicio = mod_dominio[topico_atual]["exercicio"]

                resposta_final_bot = f"Ótimo! Vamos avançar.\n\nNovo Tópico: {topico_atual}\n{explicacao}\n\nExercício: {exercicio}"
                sessao.status = "aguardando_resposta_exercicio"
            else:
                # Acabou ou deve continuar no mesmo (revisão)
                if all(v == "avançado" for v in mod_aluno.values()):
                    resposta_final_bot = (
                        "Parabéns! Você dominou todos os tópicos deste material."
                    )
                    sessao.status = "concluido"
                else:
                    resposta_final_bot = f"Vamos tentar fixar mais o tópico {topico_atual}. Tente explicar com suas palavras."
                    sessao.status = "aguardando_resposta_exercicio"
        else:
            resposta_final_bot = (
                "Vamos continuar neste tópico. Tente novamente o exercício anterior."
            )
            sessao.status = "aguardando_resposta_exercicio"

    # Adicionar resposta do bot ao histórico e salvar tudo
    historico.append({"role": "model", "parts": [{"text": resposta_final_bot}]})

    sessao.modelo_aluno = its.salvar_json(mod_aluno)
    sessao.historico_chat = its.salvar_json(historico)
    sessao.topico_atual = topico_atual

    db.commit()

    return {
        "session_id": sessao.id,
        "mensagem_bot": resposta_final_bot,
        "status_atual": sessao.status,
        "modelo_aluno": mod_aluno,
    }
