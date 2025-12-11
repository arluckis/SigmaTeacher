import json
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
genai.configure(api_key=API_KEY)

# Configuração robusta do modelo
MODEL_NAME = os.getenv("MODEL_NAME", "models/gemini-1.5-flash")
print(f"Inicializando LLM com modelo: {MODEL_NAME}")
llm = genai.GenerativeModel(MODEL_NAME)

def generate_with_retry(llm_obj, conteudo, max_attempts=5, base_delay=2):
    """
    Tenta chamar `llm_obj.generate_content` com retry exponencial em caso de quota/429.
    Levanta uma exceção ao esgotar todas as tentativas para evitar retorno `None`.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = llm_obj.generate_content(conteudo)
            if result is None:
                raise RuntimeError("Empty response from generate_content")
            return result
        except Exception as e:
            last_exc = e
            msg = str(e)
            if "quota" in msg.lower() or "429" in msg or "resource exhausted" in msg.lower():
                delay = base_delay * (2 ** (attempt - 1))
                print(f"⚠️ Quota/429 recebido. Tentando novamente em {delay}s (tentativa {attempt}/{max_attempts})...")
                time.sleep(delay)
                continue
            raise
    # se chegou aqui, todas as tentativas falharam
    raise last_exc if last_exc is not None else RuntimeError("generate_with_retry: tentativas esgotadas")

def upload_e_processar_arquivo(caminho_arquivo):
    print(f"--- Uploading: {caminho_arquivo} ---")
    try:
        arquivo = genai.upload_file(caminho_arquivo)
        while arquivo.state.name == "PROCESSING":
            time.sleep(2)
            arquivo = genai.get_file(arquivo.name)
        return arquivo
    except Exception as e:
        print(f"Erro no upload do arquivo: {e}")
        return None

def etapa_0_prep_modelo_dominio(transcricao_audio="", caminhos_pdf=None, n_topicos=5, audiencia="Ensino Médio"):
    if caminhos_pdf is None: caminhos_pdf = []
    
    arquivos_processados = []
    for c in caminhos_pdf:
        try: 
            arq = upload_e_processar_arquivo(c)
            if arq: arquivos_processados.append(arq)
        except: pass

    # --- PROMPT ATUALIZADO COM DICAS ITS ---
    prompt_dominio = f"""
    ATENÇÃO: Você é um Tutor Inteligente (ITS) especialista em educação.
    
    REGRA DE OURO: Crie o conteúdo baseando-se EXCLUSIVAMENTE no texto/áudio fornecido abaixo.
    
    Público Alvo: {audiencia}.
    Quantidade de Tópicos: {n_topicos}.
    
    Sua tarefa é estruturar o conhecimento em tópicos e, para cada um, gerar uma questão e uma DICA PEDAGÓGICA (Dica ITS).
    
    Retorne um JSON com esta estrutura EXATA (sem markdown):
    {{
        "topicos": [
            {{
                "nome": "Título do Tópico",
                "explicacao": "Resumo do conceito conforme mencionado no texto.",
                "dica_its": "Uma dica de estudo prática ou mnemônica sobre este assunto para ajudar o aluno a fixar.",
                "dados_quiz": {{
                    "pergunta": "Enunciado da questão (baseado apenas no texto)?",
                    "opcoes": {{
                        "A": "Alternativa A",
                        "B": "Alternativa B",
                        "C": "Alternativa C",
                        "D": "Alternativa D",
                        "E": "Alternativa E"
                    }},
                    "gabarito": "A", 
                    "feedback_acerto": "Correto! Como visto no texto...",
                    "feedback_erro": "Incorreto. A explicação correta segundo o texto é..."
                }},
                "dificuldade": "iniciante"
            }}
        ],
        "sequencia_recomendada": ["Título do Tópico 1", "Título do Tópico 2"]
    }}
    """

    try:
        conteudo = [prompt_dominio]
        if transcricao_audio: 
            # Limita tamanho para evitar erro de payload se for muito grande
            conteudo.append(f"--- TEXTO BASE ---\n{transcricao_audio[:30000]}\n--- FIM DO TEXTO ---")
        conteudo.extend(arquivos_processados)

        print("--- Enviando para IA (Gerando Dicas ITS)... ---")
        resp = generate_with_retry(llm, conteudo)
        
        # Limpeza do JSON (remove ```json se houver)
        txt = resp.text.strip()
        if txt.startswith("```"):
            txt = re.sub(r"^```[a-zA-Z]*\n", "", txt)
            txt = re.sub(r"\n```$", "", txt)
            
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        if not match: 
            print("Erro: JSON não encontrado na resposta da IA.")
            return None
        
        modelo_dict = json.loads(match.group(0))
        
        modelo_formatado = {}
        if "topicos" not in modelo_dict:
            print("Erro: Chave 'topicos' ausente no JSON.")
            return None

        for t in modelo_dict["topicos"]:
            quiz_json_str = json.dumps(t["dados_quiz"], ensure_ascii=False)
            
            modelo_formatado[t["nome"]] = {
                "explicacao": t.get("explicacao", ""),
                "dica_its": t.get("dica_its", "Revise este tópico com atenção."), # Salva a dica
                "exercicio": quiz_json_str, 
                "dificuldade": t.get("dificuldade", "iniciante")
            }
        
        nomes_reais = list(modelo_formatado.keys())
        modelo_formatado["_sequencia"] = modelo_dict.get("sequencia_recomendada", nomes_reais)
        
        # Fallback de segurança para garantir que a sequência bata com as chaves
        if not all(item in modelo_formatado for item in modelo_formatado["_sequencia"]):
             modelo_formatado["_sequencia"] = nomes_reais

        return modelo_formatado
    
    except Exception as e:
        print(f"Erro Geral no ITS: {e}")
        return None

def etapa_0_inicializar_aluno(modelo_dominio):
    if not modelo_dominio: return None
    topicos = modelo_dominio.get("_sequencia", [])
    return {
        "topicos_status": {t: {"status": "nao_iniciado", "acertos": 0} for t in topicos},
        "progresso_total": 0
    }

def etapa_1_selecao_proximo_topico(modelo_aluno, modelo_dominio):
    for t in modelo_dominio.get("_sequencia", []):
        status = modelo_aluno["topicos_status"].get(t, {}).get("status")
        if status != "compreendido":
            return t
    return None

# Funções auxiliares (mantidas para compatibilidade)
def etapa_3_avaliacao_interacao_inicial(historico, modelo_aluno, topico_atual, modelo_dominio):
    return {"acertou": True}, modelo_aluno

def etapa_45_decidir_e_gerar_feedback(exercicio, resposta, dominio, topico, acertou):
    return {"mensagem_ao_aluno": "", "proxima_acao": "avancar"}

def etapa_7_atualizacao_pos_feedback(hist, modelo_aluno, dominio):
    total = len(modelo_aluno["topicos_status"])
    comp = sum(1 for t in modelo_aluno["topicos_status"].values() if t.get("status") == "compreendido")
    modelo_aluno["progresso_total"] = (comp/total)*100 if total else 0
    return modelo_aluno