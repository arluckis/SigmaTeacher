from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import whisper
import shutil
import os
import uuid
import json
import string  
import random  
from datetime import datetime
from pydantic import BaseModel
from typing import List
from backend import its

SQLALCHEMY_DATABASE_URL = "sqlite:///./sigma_teacher.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Turma(Base):
    __tablename__ = "turmas"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    professor_nome = Column(String)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    alunos = relationship("Aluno", back_populates="turma")
    audios = relationship("AudioLog", back_populates="turma")

class Aluno(Base):
    __tablename__ = "alunos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    codigo_acesso = Column(String, unique=True, index=True) 
    turma_id = Column(Integer, ForeignKey("turmas.id"))
    turma = relationship("Turma", back_populates="alunos")
    sessoes = relationship("TutoriaSession", back_populates="aluno")

class AudioLog(Base):
    __tablename__ = "audios"
    id = Column(Integer, primary_key=True, index=True)
    filename_original = Column(String)
    caminho_arquivo = Column(String)
    transcricao = Column(Text)
    transcricao_editada = Column(Text, nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    turma_id = Column(Integer, ForeignKey("turmas.id"), nullable=True)
    turma = relationship("Turma", back_populates="audios")

class TutoriaSession(Base):
    __tablename__ = "sessoes_tutoria"
    id = Column(Integer, primary_key=True, index=True)
    modelo_dominio = Column(Text)
    modelo_aluno = Column(Text)
    historico_chat = Column(Text)
    topico_atual = Column(String)
    status = Column(String) 
    audio_ids = Column(String, default="[]")
    aluno_id = Column(Integer, ForeignKey("alunos.id"))
    aluno = relationship("Aluno", back_populates="sessoes")
    data_criacao = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
print("Carregando modelo Whisper...")
modelo = whisper.load_model("small")
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
os.makedirs("uploads", exist_ok=True)

class TurmaCreate(BaseModel):
    nome: str
    professor_nome: str

class AlunoCreate(BaseModel):
    nome: str
    turma_id: int

class UserResponse(BaseModel):
    session_id: int
    mensagem: str

class CriarAtividadeRequest(BaseModel):
    aluno_id: int
    audio_ids: List[int]
    caminhos_pdf: List[str] = []
    n_topicos: int = 5
    audiencia: str = "Ensino Médio"

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def gerar_codigo_unico():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(6))

def salvar_json(obj): return json.dumps(obj, ensure_ascii=False, default=str)
def carregar_json(json_str): return json.loads(json_str) if json_str else {}

@app.post("/professor/criar-turma")
def criar_turma(turma: TurmaCreate, db: Session = Depends(get_db)):
    nova = Turma(nome=turma.nome, professor_nome=turma.professor_nome)
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova

@app.get("/professor/listar-turmas")
def listar_turmas(db: Session = Depends(get_db)): return db.query(Turma).all()

@app.get("/professor/listar-alunos/{turma_id}")
def listar_alunos(turma_id: int, db: Session = Depends(get_db)): return db.query(Aluno).filter(Aluno.turma_id == turma_id).all()

@app.post("/professor/cadastrar-aluno")
def cad_aluno(aluno: AlunoCreate, db: Session = Depends(get_db)):
    cod = gerar_codigo_unico()
    while db.query(Aluno).filter(Aluno.codigo_acesso == cod).first(): cod = gerar_codigo_unico()
    novo = Aluno(nome=aluno.nome, turma_id=aluno.turma_id, codigo_acesso=cod)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"codigo_acesso": cod, "nome": novo.nome}

@app.post("/transcrever-e-salvar")
async def upload_audio(file: UploadFile = File(...), turma_id: int = None, db: Session = Depends(get_db)):
    path = f"uploads/{uuid.uuid4()}_{file.filename}"
    with open(path, "wb") as f: shutil.copyfileobj(file.file, f)
    
    res = modelo.transcribe(path, language="pt", temperature=0)
    
    novo = AudioLog(
        filename_original=file.filename, 
        caminho_arquivo=path, 
        transcricao=res["text"], 
        turma_id=turma_id
    )
    
    db.add(novo)
    db.commit()
    db.refresh(novo) # <--- OBRIGATÓRIO
    
    return {
        "status": "ok", 
        "transcricao": res["text"], 
        "id_banco": novo.id  # <--- OBRIGATÓRIO: O FRONT PRECISA DISSO
    }

    # --- ADICIONE ESTE BLOCO NO backend/main.py ---

@app.put("/editar-transcricao/{audio_id}")
async def editar_transcricao(audio_id: int, nova_transcricao: dict, db: Session = Depends(get_db)):
    audio = db.query(AudioLog).filter(AudioLog.id == audio_id).first()
    if not audio: 
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    
    # Atualiza o campo transcricao_editada
    # O frontend envia um JSON: {"transcricao": "Texto novo"}
    texto_novo = nova_transcricao.get("transcricao")
    if texto_novo:
        audio.transcricao_editada = texto_novo
        # Opcional: Atualiza também a transcrição original se quiser
        # audio.transcricao = texto_novo 
        
    db.commit()
    return {"status": "sucesso", "id": audio.id}
    
@app.get("/listar-audios-turma/{turma_id}")
def audios_turma(turma_id: int, db: Session = Depends(get_db)): return db.query(AudioLog).filter(AudioLog.turma_id == turma_id).all()

@app.get("/aluno/login/{codigo}")
def login(codigo: str, db: Session = Depends(get_db)):
    aluno = db.query(Aluno).filter(Aluno.codigo_acesso == codigo).first()
    if not aluno: raise HTTPException(404, "Não encontrado")
    turma = db.query(Turma).filter(Turma.id == aluno.turma_id).first()
    sessoes = db.query(TutoriaSession).filter(TutoriaSession.aluno_id == aluno.id).order_by(TutoriaSession.data_criacao.desc()).all()
    lista = [{"id": s.id, "topico": s.topico_atual, "status": s.status, "data": s.data_criacao.isoformat()} for s in sessoes]
    return {"aluno_nome": aluno.nome, "turma_nome": turma.nome, "atividades": lista}

@app.get("/its/sessao/{session_id}")
def get_sessao(session_id: int, db: Session = Depends(get_db)):
    s = db.query(TutoriaSession).filter(TutoriaSession.id == session_id).first()
    hist = carregar_json(s.historico_chat)
    msgs = [{"role": "user" if h["role"]=="user" else "assistant", "content": h["parts"][0]["text"]} for h in hist]
    return {"id": s.id, "mensagens": msgs, "topico_atual": s.topico_atual, "status": s.status}

@app.post("/professor/criar-atividade")
async def criar_atividade(req: CriarAtividadeRequest, db: Session = Depends(get_db)):
    audios = db.query(AudioLog).filter(AudioLog.id.in_(req.audio_ids)).all()
    texto = "\n".join([f"Aula: {a.filename_original}\n{a.transcricao}" for a in audios])
    
    print(f"--- Criando atividade para: {req.audiencia} ---")
    mod_dominio = its.etapa_0_prep_modelo_dominio(
        transcricao_audio=texto, 
        n_topicos=req.n_topicos,
        audiencia=req.audiencia
    )
    if not mod_dominio: raise HTTPException(500, "Erro na IA")
    
    mod_aluno = its.etapa_0_inicializar_aluno(mod_dominio)
    topico_inicial = its.etapa_1_selecao_proximo_topico(mod_aluno, mod_dominio) 
    if not topico_inicial: topico_inicial = list(mod_dominio.keys())[0] if mod_dominio else "Geral"
    
    msg_json = mod_dominio.get(topico_inicial, {}).get("exercicio", "{}")
    historico = [{"role": "model", "parts": [{"text": msg_json}]}]
    
    sessao = TutoriaSession(
        modelo_dominio=salvar_json(mod_dominio),
        modelo_aluno=salvar_json(mod_aluno),
        historico_chat=salvar_json(historico),
        topico_atual=topico_inicial,
        status="ativa",
        audio_ids=salvar_json(req.audio_ids),
        aluno_id=req.aluno_id
    )
    db.add(sessao)
    db.commit()
    return {"status": "ok", "session_id": sessao.id}

@app.post("/its/chat")
async def chat(dados: UserResponse, db: Session = Depends(get_db)):
    sessao = db.query(TutoriaSession).filter(TutoriaSession.id == dados.session_id).first()
    mod_dominio = carregar_json(sessao.modelo_dominio)
    mod_aluno = carregar_json(sessao.modelo_aluno)
    historico = carregar_json(sessao.historico_chat)
    
    historico.append({"role": "user", "parts": [{"text": dados.mensagem}]})
    
    # --- CORREÇÃO DO LOOP INFINITO ---
    if "AVANCAR" in dados.mensagem.upper() or "AVANCAR" in dados.mensagem:
        topico_velho = sessao.topico_atual
        
        # 1. MARCAR COMO COMPREENDIDO
        if topico_velho in mod_aluno["topicos_status"]:
            mod_aluno["topicos_status"][topico_velho]["status"] = "compreendido"
            if "ACERTOU" in dados.mensagem:
                mod_aluno["topicos_status"][topico_velho]["acertos"] += 1
            
        # 2. SELECIONAR PRÓXIMO
        novo_topico = its.etapa_1_selecao_proximo_topico(mod_aluno, mod_dominio)
        
        if not novo_topico or novo_topico == topico_velho:
            # FIM
            total = len(mod_aluno["topicos_status"])
            acertos = sum(1 for v in mod_aluno["topicos_status"].values() if v.get("acertos", 0) > 0)
            
            resp_bot = json.dumps({
                "status_final": "concluido",
                "score_acertos": acertos,
                "score_total": total,
                "mensagem_final": f"Você acertou {acertos} de {total} questões."
            })
            sessao.status = "concluido"
            sessao.topico_atual = "Relatório Final"
        else:
            # PRÓXIMA QUESTÃO
            sessao.topico_atual = novo_topico
            resp_bot = mod_dominio.get(novo_topico, {}).get("exercicio", "{}")
            
    else:
        # LOG
        resp_bot = json.dumps({"status": "log_registrado"})

    historico.append({"role": "model", "parts": [{"text": resp_bot}]})
    sessao.historico_chat = salvar_json(historico)
    sessao.modelo_aluno = salvar_json(mod_aluno)
    db.commit()
    
    return {
        "mensagem_bot": resp_bot,
        "topico_atual": sessao.topico_atual,
        "status_atual": sessao.status
    }