
import streamlit as st
import random
import time
from datetime import datetime

st.set_page_config(page_title="Gincana de Mecanografía", layout="centered")
st.title("🏎️ Gincana de Mecanografía")

# -----------------------
# Configuración inicial
# -----------------------
if 'history' not in st.session_state:
    st.session_state['history'] = []

if 'start_time' not in st.session_state:
    st.session_state['start_time'] = None

# Usuario
user_name = st.text_input("Ingresa tu nombre o alias:")

# Lista de frases
phrases = [
    "hola mundo",
    "python es divertido",
    "streamlit facilita apps web",
    "escribe rápido y preciso",
    "gincana de mecanografía",
    "mejorando la velocidad de escritura",
    "practica diaria trae resultados",
    "cada letra cuenta para la precisión"
]

# -----------------------
# Selección de frase
# -----------------------
if 'target_phrase' not in st.session_state:
    st.session_state['target_phrase'] = random.choice(phrases)

st.subheader("Frase a escribir:")
st.code(st.session_state['target_phrase'])

# Entrada del usuario
user_input = st.text_input("Tu escritura:")

# -----------------------
# Botones de control
# -----------------------
col1, col2 = st.columns(2)

with col1:
    if st.button("Comenzar"):
        st.session_state['start_time'] = time.time()
        st.success("¡Tiempo iniciado! Escribe la frase y presiona 'Finalizar'")

with col2:
    if st.button("Finalizar"):
        if st.session_state['start_time'] is None:
            st.warning("Primero presiona 'Comenzar'")
        elif user_name.strip() == "":
            st.warning("Por favor ingresa tu nombre o alias")
        else:
            # Calcular tiempo
            end_time = time.time()
            elapsed_time = end_time - st.session_state['start_time']

            # Calcular palabras por minuto
            word_count = len(user_input.split())
            wpm = (word_count / elapsed_time) * 60 if elapsed_time > 0 else 0

            # Calcular precisión
            correct_chars = sum(1 for i, c in enumerate(user_input) 
                                if i < len(st.session_state['target_phrase']) and c == st.session_state['target_phrase'][i])
            accuracy = (correct_chars / len(st.session_state['target_phrase'])) * 100

            # Guardar resultado en historial
            result = {
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Usuario": user_name,
                "Palabras por minuto": round(wpm,2),
                "Precisión (%)": round(accuracy,2),
                "Tiempo (s)": round(elapsed_time,2)
            }
            st.session_state['history'].append(result)

            # Mostrar resultados
            st.subheader("Resultados de esta ronda:")
            st.write(result)

            # Preparar siguiente frase
            st.session_state['target_phrase'] = random.choice(phrases)
            st.session_state['start_time'] = None
            st.experimental_rerun()

# -----------------------
# Historial de la sesión
# -----------------------
if st.session_state['history']:
    st.subheader("📊 Historial de intentos")
    st.table(st.session_state['history'])
