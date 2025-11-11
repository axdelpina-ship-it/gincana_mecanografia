import streamlit as st
from sheets_service import conectar_sheets

st.title("🔗 Prueba de conexión con Google Sheets")

try:
    sheet = conectar_sheets("Gincana_Mecanografia")
    st.success("✅ Conexión exitosa con la hoja de cálculo.")
    st.write("Primera fila de la hoja:", sheet.row_values(1))
except Exception as e:
    st.error("❌ Error al conectar:")
    st.exception(e)
