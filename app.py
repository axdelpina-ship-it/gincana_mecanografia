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
    
    # Normalizar el texto (importante para la precisión)
    original_limpio = re.sub(r'\s+', ' ', texto_original.strip())
    escrito_limpio = re.sub(r'\s+', ' ', texto_escrito.strip())
    
    caracteres_correctos = 0
    caracteres_totales = len(escrito_limpio)
    
    # Comparar carácter a carácter hasta la longitud del texto escrito
    for i in range(min(len(original_limpio), caracteres_totales)):
        if original_limpio[i] == escrito_limpio[i]:
            caracteres_correctos += 1
            
    errores_caracter = caracteres_totales - caracteres_correctos
    
    if len(original_limpio) > 0:
        # Precisión basada en la comparación con el texto original
        precision_porcentaje = (caracteres_correctos / len(original_limpio)) * 100
        precision_porcentaje = max(0, min(100, precision_porcentaje))
    else:
        precision_porcentaje = 0

    # Cálculo de WPM: (Caracteres Netos / 5) / Tiempo en Minutos
    caracteres_netos = caracteres_correctos - errores_caracter
    palabras_netas = max(0, caracteres_netos / 5) 
    
    wpm = (palabras_netas / (tiempo_transcurrido_seg / 60))
    wpm = max(0, wpm)

    return wpm, precision_porcentaje, errores_caracter

# --- MÓDULOS DE NAVEGACIÓN ---

def show_typing_game():
    """Módulo principal: La interfaz de la Gincana de Mecanografía."""
    st.header("⌨️ Gincana de Mecanografía")
    st.markdown("---")

    # Input de ID de Agente
    agente_id = st.text_input("Ingresa tu ID de Agente:", key="agente_id_input")

    # 1. Área de Presentación del Texto
    st.subheader("Texto a teclear")
    st.info(TEXTO_DE_PRUEBA)

    # 2. Lógica del Juego
    if not st.session_state.started:
        # Botón de inicio
        if st.button(f"🚀 Iniciar Gincana ({DURACION_SEGUNDOS // 60} Minuto)", disabled=not agente_id):
            if agente_id:
                st.session_state.started = True
                st.session_state.start_time = time.time()
                st.session_state.finished = False
                st.rerun()

    elif st.session_state.started and not st.session_state.finished:
        # --- Interfaz de la Prueba en Curso ---
        
        st.subheader(f"¡Teclea ahora, {agente_id}!")
        
        # Campo de texto para la entrada del agente
        texto_escrito = st.text_area("Comienza a escribir aquí...", height=200, key="typing_area")

        # Temporizador
        tiempo_transcurrido = time.time() - st.session_state.start_time
        tiempo_restante = DURACION_SEGUNDOS - tiempo_transcurrido
        
        if tiempo_restante > 0:
            st.warning(f"⏳ Tiempo restante: **{int(tiempo_restante)}** segundos.")
        else:
            # Fin automático del tiempo
            tiempo_final = DURACION_SEGUNDOS
            st.session_state.finished = True
            st.session_state.end_time = st.session_state.start_time + DURACION_SEGUNDOS
            st.info("¡Tiempo Agotado! Calculando resultados...")
            
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
            # PENDIENTE: Llamada a la función de guardado en Google Sheets
            st.rerun()

        # Botón de finalización anticipada
        if st.button("🛑 Finalizar Prueba (Anticipada)"):
            tiempo_final = time.time() - st.session_state.start_time
            if tiempo_final == 0: tiempo_final = 1 # Evitar división por cero
                 
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
            # PENDIENTE: Llamada a la función de guardado en Google Sheets
            st.rerun()

    # 3. Área de Resultados (Finalizado)
    if st.session_state.finished and st.session_state.results:
        st.success(f"🎉 ¡Prueba Completada, {st.session_state.results['ID Agente']}!")
        
        col1, col2, col3 = st.columns(3)
        
        col1.metric("Velocidad (WPM)", f"{st.session_state.results['WPM']:.2f}")
        col2.metric("Precisión", f"{st.session_state.results['Precisión (%)']:.2f}%")
        col3.metric("Errores", f"{st.session_state.results['Errores']}")

        st.markdown("---")
        st.info("✅ Resultados listos para ser enviados a Google Sheets.")
        
        # Botón para nueva prueba
        if st.button("🔁 Iniciar Nueva Prueba"):
            st.session_state.started = False
            st.session_state.finished = False
            st.session_state.results = None
            # No limpiamos el ID del agente para que no tenga que escribirlo de nuevo
            st.rerun()

def show_typing_ranking():
    """Módulo: Ranking de la Prueba de Velocidad."""
    st.header("🏆 Ranking de Velocidad (WPM)")
    st.markdown("---")
    st.warning("⚠️ **Pendiente:** Conexión a Google Sheets para mostrar datos.")
    
    # Aquí irá el código que lee la Hoja 'Ranking Consolidado' y muestra el TOP 3

def show_fcr_ranking():
    """Módulo: Ranking Semanal de FCR."""
    st.header("📈 Ranking FCR Semanal")
    st.markdown("---")
    st.warning("⚠️ **Pendiente:** Conexión a Google Sheets para mostrar datos.")
    
    # Aquí irá el código que lee los datos de FCR y muestra el ranking semanal
    
# --- FUNCIÓN PRINCIPAL DE LA APP ---

st.set_page_config(page_title="Gincana Contact Center", layout="wide")
st.title("🎯 Plataforma de Productividad del Contact Center")

# Inicialización de estado global (asegura que las variables existan)
if 'started' not in st.session_state: st.session_state.started = False
if 'finished' not in st.session_state: st.session_state.finished = False
if 'results' not in st.session_state: st.session_state.results = None

# --- BARRA DE NAVEGACIÓN LATERAL ---

st.sidebar.title("Menú de Módulos")
st.sidebar.markdown("---")

# Opciones con íconos
menu_options = {
    "⌨️ Gincana (Juego)": show_typing_game,
    "🏆 Ranking de Velocidad": show_typing_ranking,
    "📈 Ranking FCR Semanal": show_fcr_ranking,
}

# Selector de opciones
selection = st.sidebar.radio("Selecciona una sección:", list(menu_options.keys()))

# Ejecutar la función seleccionada
if selection in menu_options:
    menu_options[selection]()
