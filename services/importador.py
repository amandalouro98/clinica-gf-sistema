from utils.db import SessionLocal
from models.client import Client
from services.google_sheets import carregar_dados
import pandas as pd


def normalizar_texto(valor):
    if pd.isna(valor):
        return None
    valor = str(valor).strip()
    return valor if valor else None


def normalizar_cpf(valor):
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    texto = "".join(ch for ch in texto if ch.isdigit())
    return texto if texto else None


def normalizar_bool(valor):
    if pd.isna(valor):
        return False
    texto = str(valor).strip().lower()
    positivos = {"sim", "yes", "true", "1", "x", "ok", "positivo"}
    return texto in positivos or "sim" in texto


def normalizar_float(valor):
    if pd.isna(valor) or valor == "":
        return None
    texto = str(valor).strip().replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def normalizar_data(valor):
    if pd.isna(valor) or valor == "":
        return None
    try:
        data = pd.to_datetime(valor, dayfirst=True, errors="coerce")
        if pd.isna(data):
            return None
        return data.date()
    except Exception:
        return None


def juntar_campos(texto_atual, rotulo, valor):
    valor = normalizar_texto(valor)
    if not valor:
        return texto_atual
    linha = f"{rotulo}: {valor}"
    if texto_atual:
        return texto_atual + "\n" + linha
    return linha


def sincronizar_clientes():
    """
    Sincroniza clientes do Google Forms/Sheets.
    Retorna dict com contadores: importados, atualizados, pulados (sem nome).
    Clientes sem CPF são importados usando e-mail ou telefone como chave.
    """
    db = SessionLocal()
    resultado = {"importados": 0, "atualizados": 0, "pulados": 0, "pulados_nomes": []}
    try:
        df = carregar_dados()
        chaves_processadas = set()   # dedup dentro da planilha
        db_ids_atualizados = set()   # evita atualizar o mesmo registro duas vezes

        for _, row in df.iterrows():
            nome = normalizar_texto(row.get("Nome Completo"))
            cpf = normalizar_cpf(row.get("CPF"))
            telefone = normalizar_texto(row.get("Telefone (DDD)\n"))
            email = normalizar_texto(row.get("E-mail"))

            # Sem nome é impossível identificar — pula
            if not nome:
                resultado["pulados"] += 1
                continue

            # Chave de deduplicação DENTRO da planilha:
            # CPF > email > telefone > nome (evita a mesma pessoa 2x no forms)
            chave_dedup = cpf or email or telefone or nome

            if chave_dedup in chaves_processadas:
                continue
            chaves_processadas.add(chave_dedup)

            profissao = normalizar_texto(row.get("Profissão"))
            data_nascimento = normalizar_data(row.get("Data de Nascimento"))
            queixa_principal = normalizar_texto(row.get("Queixa principal"))
            endereco = normalizar_texto(row.get("Endereço (Rua, Complemento)"))
            bairro = normalizar_texto(row.get("Bairro"))
            cidade = normalizar_texto(row.get("Cidade"))
            peso = normalizar_float(row.get("PESO"))
            altura = normalizar_float(row.get("ALTURA"))
            exames_recentes = normalizar_texto(row.get("Realizou exames recentemente? se sim, quais?"))
            funcionamento_intestinal = normalizar_texto(row.get("FUNCIONAEMENTO INTESTINO (QUANTIDADE)"))
            uso_vitaminas = normalizar_texto(row.get('USO DE VITAMINAS (se sim, descrever em "outra")'))
            neoplasia = normalizar_bool(row.get("NEOPLASIA (câncer)"))
            epilepsia = normalizar_bool(row.get("EPILEPSIA"))

            outras_condicoes = None
            outras_condicoes = juntar_campos(outras_condicoes, "RADIO/QUÍMIO", row.get("RADIO/QUÍMIO"))
            outras_condicoes = juntar_campos(outras_condicoes, 'ALERGIAS', row.get('ALERGIAS (Se sim, descreva em "outra")'))
            outras_condicoes = juntar_campos(outras_condicoes, 'TRATAMENTOS', row.get('TRATAMENTOS (Se sim, descreva em "outra")'))
            outras_condicoes = juntar_campos(outras_condicoes, 'CIRURGIAS', row.get('CIRURGIAS (Se sim, descreva em "outra")'))
            outras_condicoes = juntar_campos(outras_condicoes, 'PROBLEMAS CARDÍACOS', row.get('PROBLEMAS CARDÍACOS'))
            outras_condicoes = juntar_campos(outras_condicoes, 'MARCA PASSO', row.get('MARCA PASSO'))
            outras_condicoes = juntar_campos(outras_condicoes, 'DIABETES', row.get('DIABETES'))
            outras_condicoes = juntar_campos(outras_condicoes, 'HISTÓRICO FAMÍLIAR', row.get('HISTÓRICO FAMÍLIAR (Algum histórico relevante de doença)'))
            outras_condicoes = juntar_campos(outras_condicoes, 'GRAVIDEZ', row.get('GRAVIDEZ'))
            outras_condicoes = juntar_campos(outras_condicoes, 'MENOPAUSA', row.get('MENOPAUSA'))
            outras_condicoes = juntar_campos(outras_condicoes, 'MEDICAMENTOS EM USO', row.get('MEDICAMENTOS EM USO (Se sim, descreva em "outra")'))
            outras_condicoes = juntar_campos(outras_condicoes, 'POSSUI PLACA OU PINO (FACE)', row.get('POSSUI PLACA OU PINO (FACE)'))
            outras_condicoes = juntar_campos(outras_condicoes, 'POSSUI PREENCHIMENTO', row.get('POSSUI PREENCHIMENTO'))
            outras_condicoes = juntar_campos(outras_condicoes, 'FUMA', row.get('FUMA (SE SIM, DESCREVER A FREQUENCIA EM "OUTRA")'))
            outras_condicoes = juntar_campos(outras_condicoes, 'CONSUMO DE ÁLCOOL', row.get('CONSUMO DE ÁLCOOL (SE SIM, DESCREVER A FREQUENCIA EM "OUTRA")'))
            outras_condicoes = juntar_campos(outras_condicoes, 'ATITIVDADE FÍSICA', row.get('ATITIVDADE FÍSICA'))
            outras_condicoes = juntar_campos(outras_condicoes, 'TEMPO DE SONO', row.get('TEMPO DE SONO'))
            outras_condicoes = juntar_campos(outras_condicoes, 'ALIMENTAÇÃO', row.get('ALIMENTAÇÃO'))
            outras_condicoes = juntar_campos(outras_condicoes, 'ÁGUA', row.get('ÁGUA'))

            marcacao_corporal = normalizar_texto(row.get('ASSINALE DE ACORDO COM A IMAGEM'))

            # Busca no banco APENAS por CPF, email ou telefone
            # (nunca por nome — evita confundir pessoas diferentes com o mesmo nome)
            cliente = None
            if cpf:
                cliente = db.query(Client).filter(Client.cpf == cpf).first()
            if not cliente and email:
                cliente = db.query(Client).filter(Client.email == email).first()
            if not cliente and telefone:
                cliente = db.query(Client).filter(Client.telefone == telefone).first()

            # Se o registro do banco já foi atualizado nesta sessão, cria novo
            if cliente and cliente.id in db_ids_atualizados:
                cliente = None

            dados = dict(
                nome=nome,
                cpf=cpf,
                data_nascimento=data_nascimento,
                telefone=telefone,
                email=email,
                profissao=profissao,
                endereco=endereco,
                bairro=bairro,
                cidade=cidade,
                peso=peso,
                altura=altura,
                exames_recentes=exames_recentes,
                funcionamento_intestinal=funcionamento_intestinal,
                uso_vitaminas=uso_vitaminas,
                marcacao_corporal=marcacao_corporal,
                neoplasia=neoplasia,
                epilepsia=epilepsia,
                outras_condicoes=outras_condicoes,
                queixa_principal=queixa_principal,
            )

            if cliente:
                for k, v in dados.items():
                    setattr(cliente, k, v)
                db_ids_atualizados.add(cliente.id)
                resultado["atualizados"] += 1
            else:
                cliente = Client(**dados, termo_aceite=True)
                db.add(cliente)
                db.flush()
                db_ids_atualizados.add(cliente.id)
                resultado["importados"] += 1

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return resultado
