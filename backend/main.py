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
from typing import List, Optional
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
    transcricao_editada = Column(Text, nullable=True)  # Transcrição editada pelo usuário
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
    audio_id: int, 
    nova_transcricao: dict, 
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db),
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
            "detalhe": "Selecione pelo menos uma aula para iniciar o ITS"
        }
    
    return {
        "status": "sucesso",
        "arquivos_salvos": caminhos_salvos,
        "audio_ids": audio_ids,
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
    """
    1. Pega transcrições do banco.
    2. Processa PDFs enviados agora.
    3. Gera Modelo de Domínio.
    4. Seleciona 1º Tópico.
    5. Cria Sessão no Banco.
    """
    
    # Validar entrada
    if not request.audio_ids:
        raise HTTPException(
            status_code=400,
            detail="Selecione pelo menos uma aula"
        )

    # 1. Recuperar Transcrições dos Áudios
    texto_completo_audios = ""
    if request.audio_ids:
        registros = db.query(AudioLog).filter(AudioLog.id.in_(request.audio_ids)).all()
        for reg in registros:
            # Usar transcrição editada se existir
            texto = reg.transcricao_editada or reg.transcricao
            texto_completo_audios += f"\n--- Aula: {reg.filename_original} ---\n{texto}"

    if not texto_completo_audios:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma transcrição encontrada para as aulas selecionadas"
        )

    # 3. Gerar Modelo de Domínio (Etapa 0)
    print("--- Gerando Modelo de Domínio baseado nos arquivos/áudio... ---")
    modelo_dominio = its.etapa_0_prep_modelo_dominio(
        transcricao_audio=texto_completo_audios,
        caminhos_pdf=request.caminhos_pdf,
        n_topicos=request.n_topicos,
        audiencia=request.audiencia,
    )

    if not modelo_dominio:
        raise HTTPException(
            status_code=500,
            detail="Erro ao gerar Modelo de Domínio. Verifique o conteúdo da aula."
        )

    # Limpeza: Remover PDFs temporários
    for path in request.caminhos_pdf:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Erro ao remover arquivo temporário: {e}")

    # 4. Inicializar Modelo do Aluno
    modelo_aluno = its.etapa_0_inicializar_aluno(modelo_dominio)
    
    if not modelo_aluno:
        raise HTTPException(
            status_code=500,
            detail="Erro ao inicializar Modelo do Aluno"
        )

    # 5. Selecionar primeiro tópico
    topico_inicial = its.etapa_1_selecao_proximo_topico(modelo_aluno, modelo_dominio)
    
    if not topico_inicial:
        raise HTTPException(
            status_code=500,
            detail="Erro ao selecionar tópico inicial"
        )

    # 6. Criar sessão no banco
    sessao = TutoriaSession(
        modelo_dominio=salvar_json(modelo_dominio),
        modelo_aluno=salvar_json(modelo_aluno),
        historico_chat=salvar_json([]),
        topico_atual=topico_inicial,
        status="ativo"
    )

    db.add(sessao)
    db.commit()
    db.refresh(sessao)

    topico_info = modelo_dominio.get(topico_inicial, {})

    return {
        "status": "sucesso",
        "session_id": sessao.id,
        "topico_atual": topico_inicial,
        "exercicio": topico_info.get("exercicio", ""),
        "explicacao": topico_info.get("explicacao", ""),
        "dificuldade": topico_info.get("dificuldade", "intermediario"),
        "mensagem_bot": f"**Tópico: {topico_inicial}**\n\n{topico_info.get('explicacao', '')}\n\n**Exercício:** {topico_info.get('exercicio', '')}"
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


# --- Funções Auxiliares ---
def salvar_json(obj):
    """Converte objeto para JSON string"""
    import json
    return json.dumps(obj, ensure_ascii=False, default=str)


def carregar_json(json_str):
    """Converte JSON string para objeto"""
    import json
    if not json_str:
        return {}
    return json.loads(json_str)