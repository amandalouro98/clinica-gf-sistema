import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

SHEET_URL = "https://docs.google.com/spreadsheets/d/1ltWjDSt5UOqbotlfe2BYAZ5aZWnP2ueFsys-CBK71BI"
CREDENTIALS_FILE = "clinica-gf-06e7d742ecca.json"


def carregar_dados() -> pd.DataFrame:
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).sheet1
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        erro_msg = str(e)
        if "invalid_grant" in erro_msg or "Invalid JWT" in erro_msg:
            raise Exception(
                "Credencial do Google expirada ou inválida. "
                "É necessário gerar uma nova chave no Google Cloud Console "
                "(IAM > Service Accounts > Criar nova chave JSON) e substituir "
                f"o arquivo '{CREDENTIALS_FILE}' no servidor. Erro: {erro_msg}"
            )
        raise
