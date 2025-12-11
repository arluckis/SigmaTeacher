import json
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
if API_KEY is not None:
    print("API_KEY carregada com sucesso.")
else:
    print("API_KEY não encontrada nas variáveis de ambiente.")

genai.configure(api_key=API_KEY)
llm = genai.GenerativeModel("models/gemini-2.5-flash")


def carregar_json(json_str):
    if not json_str:
        return {}
    return json.loads(json_str)


def salvar_json(obj_dict):
    return json.dumps(obj_dict, ensure_ascii=False)


def get_text_from_message(message):
    """
    Extrai o texto de uma mensagem no histórico,
    independentemente de ser um objeto 'Content' ou um 'dict'.
    """
    if isinstance(message, dict):
        # É um dicionário
        try:
            return message["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return ""
    else:
        # É um objeto
        try:
            return message.parts[0].text
        except (AttributeError, IndexError):
            return ""


def upload_e_processar_arquivo(caminho_arquivo):
    """Faz o upload do arquivo para a API do Gemini e aguarda o processamento."""
    print(f"--- Uploading: {caminho_arquivo} ---")
    arquivo = genai.upload_file(caminho_arquivo)

    # Aguardar o arquivo estar ativo (processado)
    while arquivo.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        arquivo = genai.get_file(arquivo.name)

    if arquivo.state.name == "FAILED":
        raise ValueError(f"O processamento do arquivo {caminho_arquivo} falhou.")

    print(f"\nArquivo pronto: {arquivo.name}")
    return arquivo


# --- Modelo de Domínio ---
def etapa_0_prep_modelo_dominio(
    transcricao_audio="",
    caminhos_pdf=None,
    n_topicos=10,
    audiencia="1° ano do ensino médio",
):
    """
    Gera o Modelo de Domínio, extraindo informações da transcrição e PDFs fornecidos,
    em tópicos, cada um com explicação, pré-requisito, e exercício.
    """
    if caminhos_pdf is None:
        caminhos_pdf = []

    # 1. Preparar os arquivos PDF (Upload para o Gemini)
    arquivos_processados = []
    for caminho in caminhos_pdf:
        try:
            arq = upload_e_processar_arquivo(caminho)
            arquivos_processados.append(arq)
        except Exception as e:
            print(f"Erro ao processar PDF {caminho}: {e}")

    # 2. Construir o Prompt de Sistema e Instruções
    prompt_dominio = f"""
    Você é um especialista em currículo e pedagogia. 
    Sua tarefa é analisar o CONTEÚDO FORNECIDO (transcrição de áudio e documentos) de uma aula
    e estruturá-lo em um modelo de domínio educacional.
    
    Baseado no seguinte conteúdo de aula:
    
    {transcricao_audio}
    
    Analise o conteúdo fornecido e com base nele, extraia e estruture exatamente {n_topicos} tópicos principais para ensinar a alunos de {audiencia}.
    
    IMPORTANTE: Retorne OBRIGATORIAMENTE um JSON válido com a seguinte estrutura:
    {{
        "topicos": [
            {{
                "nome": "Nome do Tópico",
                "explicacao": "Explicação clara e concisa a respeito do tópico",
                "prerequisito": "Conhecimento necessário antes de aprender este tópico",
                "exercicio": "Uma pergunta de múltipla escolha com 4 alternativas, e apenas 1 correta. 
                    Não centralize as respostas corretas em apenas uma alternativa, varie entre as opções.",
                "dificuldade": "iniciante|intermediario|avancado"
            }},
            ...mais tópicos...
        ],
        "sequencia_recomendada": ["Nome do Tópico 1", "Nome do Tópico 2", ...]
    }}
    
    Certifique-se que:
    1. Limite-se ao escopo do material fornecido. Se o material for insuficiente, infira o mínimo necessário para manter a coerência.
    2. O JSON é válido e bem formado
    3. Todos os campos obrigatórios (nome, explicacao, exercicio e dificuldade) estão preenchidos
    4. Os tópicos são pedagogicamente sequenciados
    5. Cada tópico tem um exercício específico
    6. A sequência recomendada segue ordem de dificuldade
    """

    # 3. Enviar para o Gemini
    try:
        conteudo_envio = [prompt_dominio]
        
        if transcricao_audio:
            conteudo_envio.append(
                f"\n--- INÍCIO DA TRANSCRIÇÃO DO ÁUDIO ---\n{transcricao_audio}\n--- FIM DA TRANSCRIÇÃO ---\n"
            )
        
        # Adicionar os objetos de arquivo PDF
        conteudo_envio.extend(arquivos_processados)

        print("--- Gerando Modelo de Domínio baseado nos arquivos/áudio... ---")

        resposta = llm.generate_content(conteudo_envio)
        texto_resposta = resposta.text
        print(f"Resposta do Gemini: {texto_resposta[:200]}...")
        
        # 4. Extrair JSON da resposta
        match = re.search(r'\{.*\}', texto_resposta, re.DOTALL)
        
        if not match:
            print("ERRO: Nenhum JSON encontrado na resposta")
            return None
        
        json_str = match.group(0)
        modelo_dict = json.loads(json_str)
        
        # 5. Validar estrutura
        if "topicos" not in modelo_dict or not isinstance(modelo_dict["topicos"], list):
            print("ERRO: Estrutura de 'topicos' inválida")
            return None
        
        # 6. Converter para formato esperado (dicionário com nome do tópico como chave)
        modelo_formatado = {}
        for topico in modelo_dict["topicos"]:
            nome_topico = topico.get("nome", "Sem nome")
            modelo_formatado[nome_topico] = {
                "explicacao": topico.get("explicacao", ""),
                "prerequisito": topico.get("prerequisito", ""),
                "exercicio": topico.get("exercicio", ""),
                "dificuldade": topico.get("dificuldade", "intermediario")
            }
        
        modelo_formatado["_sequencia"] = modelo_dict.get("sequencia_recomendada", list(modelo_formatado.keys()))
        
        print(f"Modelo de Domínio gerado com sucesso: {len(modelo_formatado)-1} tópicos")
        return modelo_formatado
    
    except json.JSONDecodeError as e:
        print(f"ERRO ao decodificar JSON: {e}")
        return None
    except Exception as e:
        print(f"ERRO ao gerar modelo de domínio: {e}")
        return None


# --- Modelo do Aluno ---
def etapa_0_inicializar_aluno(modelo_dominio):
    """
        Cria um modelo do aluno inicializado com todos os tópicos em nível 'não iniciado'
    """
    if not modelo_dominio:
        return None
    
    topicos = modelo_dominio.get("_sequencia", [])
    
    modelo_aluno = {
        "topicos_status": {},
        "nivel_geral": "iniciante",
        "progresso_total": 0,
        "topico_atual_idx": 0
    }
    
    for topico in topicos:
        modelo_aluno["topicos_status"][topico] = {
            "status": "nao_iniciado",  # nao_iniciado, em_progresso, compreendido
            "tentativas": 0,
            "acertos": 0,
            "compreensao": 0  # 0-100
        }
    
    return modelo_aluno


# --- Modelo Pedagógico ---
def etapa_1_selecao_proximo_topico(modelo_aluno, modelo_dominio):
    """
        Seleciona o próximo tópico a ser ensinado
    """
    if not modelo_aluno or not modelo_dominio:
        return None
    
    topicos_sequencia = modelo_dominio.get("_sequencia", [])
    topicos_status = modelo_aluno.get("topicos_status", {})
    
    # Encontrar primeiro tópico não compreendido
    for topico in topicos_sequencia:
        if topicos_status.get(topico, {}).get("status") != "compreendido":
            return topico
    
    # Se chegou aqui, todos foram compreendidos
    return None


def etapa_3_avaliacao_interacao_inicial(historico, modelo_aluno, topico_atual, modelo_dominio):
    """
        Analisa a resposta do aluno e atualiza o modelo
    """
    if not historico or len(historico) < 1:
        return None, modelo_aluno
    
    # AJUSTE: Usar a função auxiliar para extrair texto do formato Gemini
    ultima_mensagem = historico[-1]
    texto_resposta = get_text_from_message(ultima_mensagem)
    
    topico_info = modelo_dominio.get(topico_atual, {})
    
    prompt_avaliacao = f"""
    Analise a resposta do aluno para esta pergunta:
    
    Tópico: {topico_atual}
    Pergunta: {topico_info.get('exercicio', '')}
    Resposta do aluno: {texto_resposta}
    
    Retorne um JSON com:
    {{
        "acertou": true|false,
        "compreensao": 0-100,
        "feedback_tecnico": "Breve análise técnica do erro ou acerto"
    }}
    """
    
    try:
        resposta = llm.generate_content(prompt_avaliacao)
        match = re.search(r'\{.*\}', resposta.text, re.DOTALL)
        
        resultado = {}
        if match:
            resultado = json.loads(match.group(0))
            
            # Atualizar modelo do aluno
            if topico_atual in modelo_aluno["topicos_status"]:
                stats = modelo_aluno["topicos_status"][topico_atual]
                stats["tentativas"] += 1
                if resultado.get("acertou"):
                    stats["acertos"] += 1
                
                # Média ponderada simples para nova compreensão ou substituição
                stats["compreensao"] = resultado.get("compreensao", 0)
                
                # Atualizar status baseado na nota
                if stats["compreensao"] >= 70:
                    stats["status"] = "compreendido"
                else:
                    stats["status"] = "em_progresso"
            
        return resultado, modelo_aluno # Retorna a tupla
    except Exception as e:
        print(f"Erro na avaliação: {e}")
        return None, modelo_aluno


def etapa_45_decidir_e_gerar_feedback(exercicio, resposta_aluno, modelo_dominio, topico_atual, acertou):
    """
        Gera feedback para o aluno e decide próximo passo
    """
    
    # Contexto emocional muda se ele acertou ou errou
    tom = ""
    if acertou:
        tom = "Parabenize e avance." 
    else:
        tom = "Seja paciente, dê uma dica e peça para tentar de novo ou explique o conceito."
    
    prompt_feedback = f"""
    Você é um tutor educacional. Avalie a resposta do aluno e forneça um feedback útil.
    Não precisa dizer "Olá" ou qualquer tipo de saudação, você já está inserido no contexto de uma conversa.
    Contexto: O aluno respondeu ao exercício sobre "{topico_atual}".
    Status da resposta: {"Correta" if acertou else "Incorreta"}.
    
    Exercício: {exercicio}
    Resposta do aluno: {resposta_aluno}
    Instrução: {tom}
    
    Retorne um JSON com:
    {{
        "mensagem_ao_aluno": "O texto que será enviado ao aluno (use markdown, negrito, etc).",
        "proxima_acao": "avancar" se acertou else "revisar"
    }}
    """
    
    try:
        resposta = llm.generate_content(prompt_feedback)
        match = re.search(r'\{.*\}', resposta.text, re.DOTALL)
        
        if match:
            return json.loads(match.group(0))
        return {"mensagem_ao_aluno": "Não consegui gerar um feedback específico. Vamos continuar?", "proxima_acao": "revisar"}
    except Exception as e:
        print(f"Erro ao gerar feedback: {e}")
        return {"mensagem_ao_aluno": "Erro interno no feedback.", "proxima_acao": "revisar"}


def etapa_7_atualizacao_pos_feedback(historico, modelo_aluno, modelo_dominio):
    """
        Atualiza modelo do aluno após feedback e calcula progresso geral
    """
    topicos_status = modelo_aluno.get("topicos_status", {})
    
    total_topicos = len(topicos_status)
    topicos_compreendidos = sum(1 for t in topicos_status.values() if t.get("status") == "compreendido")
    
    modelo_aluno["progresso_total"] = (topicos_compreendidos / total_topicos * 100) if total_topicos > 0 else 0
    
    # Atualizar nível geral
    progresso = modelo_aluno["progresso_total"]
    if progresso < 33:
        modelo_aluno["nivel_geral"] = "iniciante"
    elif progresso < 66:
        modelo_aluno["nivel_geral"] = "intermediario"
    else:
        modelo_aluno["nivel_geral"] = "avancado"
    
    return modelo_aluno


def sistema_tutoria_inteligente_genai(modelo_dominio, modelo_aluno, historico_chat):
    """
        Orquestra todo o sistema de tutoria
    """
    if not modelo_dominio or not modelo_aluno:
        return None
    
    # Selecionar próximo tópico
    topico_atual = etapa_1_selecao_proximo_topico(modelo_aluno, modelo_dominio)
    
    if not topico_atual:
        return {
            "status": "concluido",
            "mensagem": "Parabéns! Você completou todos os tópicos! 🎓"
        }
    
    topico_info = modelo_dominio.get(topico_atual, {})
    
    return {
        "status": "ativo",
        "topico_atual": topico_atual,
        "exercicio": topico_info.get("exercicio", ""),
        "dificuldade": topico_info.get("dificuldade", "intermediario"),
        "progresso": modelo_aluno.get("progresso_total", 0)
    }
