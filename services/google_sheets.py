import os
import time
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_URL = "https://docs.google.com/spreadsheets/d/1ltWjDSt5UOqbotlfe2BYAZ5aZWnP2ueFsys-CBK71BI"

# Procura a credencial em vários caminhos.
# Prioridade: variável de ambiente > /opt/clinica-gf/secrets > raiz do projeto
_CAMINHOS_CREDENCIAL = [
    os.getenv("GOOGLE_CREDENTIALS_PATH", ""),
    "/opt/clinica-gf/secrets/google-credentials.json",
    "/app/secrets/google-credentials.json",
    "secrets/google-credentials.json",
    "/app/clinica-gf-06e7d742ecca.json",
    "clinica-gf-06e7d742ecca.json",
]


def _resolver_credencial() -> str:
    for caminho in _CAMINHOS_CREDENCIAL:
        if caminho and os.path.exists(caminho):
            return caminho
    return ""


def carregar_dados() -> pd.DataFrame:
    caminho_cred = _resolver_credencial()
    if not caminho_cred:
        raise Exception(
            "Credencial do Google não encontrada. "
            "Coloque o arquivo JSON em /opt/clinica-gf/secrets/google-credentials.json "
            "ou defina a variável de ambiente GOOGLE_CREDENTIALS_PATH."
        )

    ultimo_erro = None
    for tentativa in range(3):
        try:
            creds = Credentials.from_service_account_file(caminho_cred, scopes=SCOPES)
            client = gspread.authorize(creds)
            sheet = client.open_by_url(SHEET_URL).sheet1
            dados = sheet.get_all_records()
            return pd.DataFrame(dados)
        except Exception as e:
            ultimo_erro = e
            erro_msg = str(e)
            if "invalid_grant" in erro_msg or "Invalid JWT" in erro_msg:
                raise Exception(
                    "Credencial do Google expirada ou inválida. "
                    "Gere uma nova chave no Google Cloud Console "
                    "(IAM > Service Accounts > Criar nova chave JSON) e salve em "
                    f"'{caminho_cred}'. Erro: {erro_msg}"
                )
            # Retry com espera crescente (1s, 3s, 5s)
            if tentativa < 2:
                time.sleep(1 + tentativa * 2)

    raise Exception(
        f"Não foi possível conectar ao Google Sheets após 3 tentativas. "
        f"Erro: {ultimo_erro}"
    )
