import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

def _load_creds_dict_from_secrets():
    creds_secret = st.secrets.get("credentials")
    if creds_secret is None:
        raise RuntimeError("No se encontró 'credentials' en st.secrets. Revisa los Secrets.")

    if isinstance(creds_secret, dict):
        return creds_secret
    if isinstance(creds_secret, str):
        return json.loads(creds_secret)

    raise RuntimeError("El formato de st.secrets['credentials'] no es válido.")

def conectar_sheets(sheet_name):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = _load_creds_dict_from_secrets()
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1
    return sheet

def guardar_resultado(usuario, palabras_min, precision, tiempo):
    sheet = conectar_sheets("Gincana_Mecanografia")
    sheet.append_row([
        pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        usuario,
        palabras_min,
        precision,
        tiempo
    ])

