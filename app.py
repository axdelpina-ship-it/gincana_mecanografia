import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import re

# --- CONFIGURACIÓN DE LA PRUEBA (Estos datos vendrán de Google Sheets al final) ---
TEXTO_DE_PRUEBA = "Reducir el porcentaje de No-FCR atribuible al Ejecutivo de 8,32% a 7% mediante la aplicación de Gincana de mecanografía y un ranking visible que incentiva la resolución de calidad con CSAT positivo."
DURACION_SEGUNDOS = 60 # Ejemplo: 60 segundos (1 minuto)

# --- Funciones de Cálculo ---

def calcular_wpm_y_precision(texto_original, texto_escrito, tiempo_transcurrido_seg):
    """Calcula WPM y la precisión de la prueba."""
    
    # Normalizar (opcional: quitar dobles espacios, mayúsculas/minúsculas)
    original_limpio = re.sub(r'\s+', ' ', texto_original.strip())
    escrito_limpio = re.sub(r'\s+', ' ', texto_escrito.strip())
    
    # Contar palabras originales para la métrica
    palabras_originales = original_limpio.split()
    
    # 1. Conteo de Errores (simple por carácter hasta el punto de parada)
    caracteres_correctos = 0
    caracteres_totales = len(escrito_limpio)
    
    # Comparar carácter a carácter hasta la longitud del texto escrito
    for i in range(min(len(original_limpio), caracteres_totales)):
        if original_limpio[i] == escrito_limpio[i]:
            caracteres_correctos += 1
            
    errores_caracter = caracteres_totales - caracteres_correctos
    
    if caracteres_totales > 0:
        precision_porcentaje = (caracteres_correctos / len(original_limpio)) * 100
        # Limitamos la precisión a 100% y aseguramos que no sea negativa
        precision_porcentaje = max(0, min(100, precision_porcentaje))
    else:
        precision_porcentaje = 0

    # 2. Cálculo de WPM (Palabras por minuto - métrica común)
    # Se basa en 5 caracteres por palabra (incluyendo espacios)
    caracteres_netos = caracteres_correctos - errores_caracter
    palabras_netas = max(0, caracteres_netos / 5) 
    
    # WPM es Palabras Netas / Tiempo en Minutos
    wpm = (palabras_netas / (tiempo_transcurrido_seg / 60))
    wpm = max(0, wpm) # Asegurar que no sea negativo

    return wpm, precision_porcentaje, errores_caracter

# --- Interfaz de Streamlit ---

st.set_page_config(page_title="Gincana de Mecanografía Beta", layout="centered")
st.title("⌨️ Gincana de Mecanografía - Beta")

# Inicialización de estado para controlar el juego
if 'started' not in st.session_state:
    st.session_state.started = False
if 'finished' not in st.session_state:
    st.session_state.finished = False
if 'results' not in st.session_state:
    st.session_state.results = None

# Input de ID de Agente
agente_id = st.text_input("Ingresa tu ID de Agente:", key="agente_id_input")

st.markdown("---")

# 1. Área de Presentación del Texto
st.subheader("Texto a teclear (Duración: 60 segundos)")
st.info(TEXTO_DE_PRUEBA) # Aquí se muestra el texto que debe teclear

# 2. Lógica del Juego
if not st.session_state.started:
    # Botón de inicio
    if st.button("🚀 Iniciar Gincana (1 Minuto)", disabled=not agente_id):
        if agente_id:
            st.session_state.started = True
            st.session_state.start_time = time.time()
            st.session_state.finished = False
            st.rerun() # Reiniciar para mostrar la interfaz de tecleo

elif st.session_state.started and not st.session_state.finished:
    # --- Interfaz de la Prueba ---
    
    st.subheader(f"¡Teclea ahora, {agente_id}!")
    
    # Campo de texto para la entrada del agente
    texto_escrito = st.text_area("Comienza a escribir aquí...", height=200, key="typing_area")

    # Muestra un temporizador simple (actualizado en cada interacción)
    tiempo_transcurrido = time.time() - st.session_state.start_time
    tiempo_restante = DURACION_SEGUNDOS - tiempo_transcurrido
    
    if tiempo_restante > 0:
        st.warning(f"⏳ Tiempo restante: **{int(tiempo_restante)}** segundos.")
    else:
        # Fin automático del tiempo
        texto_escrito = st.session_state.typing_area # Asegurar que se tome el último valor
        tiempo_final = DURACION_SEGUNDOS # El tiempo máximo
        st.session_state.finished = True
        st.session_state.end_time = st.session_state.start_time + DURACION_SEGUNDOS # Fija el tiempo de fin
        st.info("¡Tiempo Agotado! Calculando resultados...")
        
        # Simular el cálculo final
        wpm, precision, errores = calcular_wpm_y_precision(
            TEXTO_DE_PRUEBA, 
            texto_escrito, 
            tiempo_final
        )
        
        st.session_state.results = {
            'ID Agente': agente_id,
            'Fecha/Hora': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'WPM': round(wpm, 2),
            'Precisión (%)': round(precision, 2),
            'Errores': errores,
            'Duracion (s)': tiempo_final,
            'Texto Escrito': texto_escrito # Para auditoría
        }
        st.rerun() # Recalcula la interfaz para mostrar los resultados

    # Botón de finalización anticipada (opcional)
    if st.button("🛑 Finalizar Prueba (Antes de tiempo)"):
        tiempo_final = time.time() - st.session_state.start_time
        texto_escrito = st.session_state.typing_area

        if tiempo_final == 0:
             tiempo_final = 1 # Evitar división por cero
             
        st.session_state.finished = True
        
        wpm, precision, errores = calcular_wpm_y_precision(
            TEXTO_DE_PRUEBA, 
            texto_escrito, 
            tiempo_final
        )

        st.session_state.results = {
            'ID Agente': agente_id,
            'Fecha/Hora': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'WPM': round(wpm, 2),
            'Precisión (%)': round(precision, 2),
            'Errores': errores,
            'Duracion (s)': round(tiempo_final, 2),
            'Texto Escrito': texto_escrito
        }
        st.rerun() # Recalcula la interfaz

# 3. Área de Resultados (Finalizado)
if st.session_state.finished and st.session_state.results:
    st.success(f"🎉 ¡Prueba Completada, {st.session_state.results['ID Agente']}!")
    
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Velocidad (WPM)", f"{st.session_state.results['WPM']:.2f}")
    col2.metric("Precisión", f"{st.session_state.results['Precisión (%)']:.2f}%")
    col3.metric("Errores", f"{st.session_state.results['Errores']}")

    st.markdown("---")
    
    # PENDIENTE: Aquí iría la llamada a la función para GUARDAR en Google Sheets (Paso 3)
    # Por ahora, simulamos la escritura:
    st.info("✅ Resultados listos para ser enviados a Google Sheets. (Función pendiente de conexión).")
    
    # Botón para nueva prueba
    if st.button("🔁 Iniciar Nueva Prueba"):
        st.session_state.started = False
        st.session_state.finished = False
        st.session_state.results = None
        st.rerun()
