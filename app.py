import streamlit as st
import pandas as pd
from datetime import datetime
import time
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN Y CONEXIÓN A GOOGLE SHEETS ---

# Decorador para cachear la conexión y no reconectar en cada interacción
@st.cache_resource
def get_gsheet_client():
    """Conecta con Google Sheets usando los secretos de Streamlit."""
    try:
        # st.secrets.gcp_service_account lee la sección [gcp_service_account] como una tabla/diccionario
        creds_info = st.secrets.gcp_service_account 
        
        # Convertimos la tabla TOML a un diccionario estándar para el cliente gspread
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dict(creds_info), 
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        #st.success("✅ Conexión a Google Sheets exitosa.")
        return client
    except Exception as e:
        #st.error(f"❌ ERROR de Conexión a Google Sheets. Revisa tus Secrets y el código: {e}")
        return None

# Inicializa el cliente (Solo se llama una vez al inicio)
gsheet_client = get_gsheet_client()

@st.cache_data(ttl=3600) # Cacha la configuración por 1 hora
def get_config_data(client, sheet_id):
    """Lee el texto y la duración de la hoja 'Configuracion'."""
    if not client:
        return "Error: Cliente de Sheets no disponible.", 60

    try:
        sheet = client.open_by_key(sheet_id) 
        config_ws = sheet.worksheet("Configuracion")
        
        # Asumiendo que el texto de prueba está en la celda A2 y la duración (en segundos) en B2
        texto = config_ws.acell('A2').value
        duracion_seg = int(config_ws.acell('B2').value)
        
        return texto, duracion_seg
        
    except Exception as e:
        # El error de cuota (429) a menudo aparece aquí.
        return f"Error al leer la configuración de Google Sheets: {e}", 60 

# Lectura global de la configuración (Solo se ejecuta una vez por sesión o al expirar la caché)
TEXTO_DE_PRUEBA, DURACION_SEGUNDOS = get_config_data(gsheet_client, st.secrets["gsheet_id"])

# --- Funciones de Cálculo de WPM y Precisión ---

def calcular_wpm_y_precision(texto_original, texto_escrito, tiempo_transcurrido_seg):
    """Calcula WPM y la precisión de la prueba."""
    original_limpio = re.sub(r'\s+', ' ', texto_original.strip())
    escrito_limpio = re.sub(r'\s+', ' ', texto_escrito.strip())
    
    caracteres_correctos = 0
    caracteres_totales = len(escrito_limpio)
    
    for i in range(min(len(original_limpio), caracteres_totales)):
        if original_limpio[i] == escrito_limpio[i]:
            caracteres_correctos += 1
            
    errores_caracter = caracteres_totales - caracteres_correctos
    
    if len(original_limpio) > 0:
        precision_porcentaje = (caracteres_correctos / len(original_limpio)) * 100
        precision_porcentaje = max(0, min(100, precision_porcentaje))
    else:
        precision_porcentaje = 0

    caracteres_netos = caracteres_correctos - errores_caracter
    palabras_netas = max(0, caracteres_netos / 5) 
    
    wpm = (palabras_netas / (tiempo_transcurrido_seg / 60))
    wpm = max(0, wpm)

    return wpm, precision_porcentaje, errores_caracter

# --- Función de Escritura de Resultados ---

def save_typing_results(results_dict):
    """Guarda los resultados de la prueba en la hoja 'Resultados Brutos' (Solo se llama una vez)."""
    client = get_gsheet_client()
    if not client: 
        st.error("No se pudo guardar: Cliente de Sheets no disponible.")
        return

    try:
        sheet = client.open_by_key(st.secrets["gsheet_id"])
        results_ws = sheet.worksheet("Resultados Brutos") 
        
        # El orden de las columnas debe coincidir con los encabezados de tu hoja
        row_data = [
            results_dict['Fecha/Hora'],
            results_dict['ID Agente'],
            results_dict['WPM'],
            results_dict['Precisión (%)'],
            results_dict['Errores'],
            results_dict['Duracion (s)'],
            results_dict['Texto Escrito']
        ]
        
        results_ws.append_row(row_data)
        st.success("✅ ¡Tu resultado se ha guardado automáticamente en Google Sheets!")
        
    except Exception as e:
        st.error(f"❌ ¡ERROR al guardar los resultados! Revisa la hoja 'Resultados Brutos': {e}")


# --- MÓDULOS DE NAVEGACIÓN ---

def show_typing_game():
    """Módulo principal: La interfaz de la Gincana de Mecanografía."""
    st.header("⌨️ Gincana de Mecanografía")
    st.markdown("---")

    # Muestra el error de configuración si existe
    if TEXTO_DE_PRUEBA.startswith("Error"):
        st.error(TEXTO_DE_PRUEBA)
        st.warning("No se puede iniciar la prueba sin el texto de configuración.")
        return

    # Input de ID de Agente
    agente_id = st.text_input("Ingresa tu ID de Agente:", key="agente_id_input")

    # 1. Área de Presentación del Texto
    st.subheader("Texto a teclear")
    st.info(TEXTO_DE_PRUEBA)

    # 2. Lógica del Juego
    if not st.session_state.started:
        if st.button(f"🚀 Iniciar Gincana ({DURACION_SEGUNDOS} Segundos)", disabled=not agente_id):
            if agente_id:
                st.session_state.started = True
                st.session_state.start_time = time.time()
                st.session_state.finished = False
                st.session_state.texto_escrito = "" # Inicializar texto escrito
                st.rerun()

    elif st.session_state.started and not st.session_state.finished:
        st.subheader(f"¡Teclea ahora, {agente_id}!")
        
        # Usamos session_state para mantener el texto escrito
        texto_escrito = st.text_area("Comienza a escribir aquí...", 
                                     height=200, 
                                     key="typing_area", 
                                     value=st.session_state.texto_escrito)
        
        # Sincronizamos el session_state para que persista el texto
        st.session_state.texto_escrito = texto_escrito 

        tiempo_transcurrido = time.time() - st.session_state.start_time
        tiempo_restante = DURACION_SEGUNDOS - tiempo_transcurrido
        
        # Placeholder para el contador de tiempo
        timer_placeholder = st.empty()
        
        if tiempo_restante > 0:
            timer_placeholder.warning(f"⏳ Tiempo restante: **{int(tiempo_restante)}** segundos.")
            
            # --- Ajuste Anti-Cuota (429) ---
            # Esperamos 1 segundo antes de forzar el rerun para actualizar el timer.
            # Esto reduce las llamadas a la API 10 veces, evitando el error de cuota.
            if int(tiempo_restante) > 0:
                time.sleep(1)
                st.rerun()    
            # -------------------------------

        else:
            # Lógica de finalización por tiempo agotado
            tiempo_final = DURACION_SEGUNDOS
            st.session_state.finished = True
            timer_placeholder.info("¡Tiempo Agotado! Calculando resultados...")
            
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
                'Texto Escrito': texto_escrito 
            }
            save_typing_results(st.session_state.results) # GUARDA SÓLO UNA VEZ
            st.rerun()

        if st.button("🛑 Finalizar Prueba (Anticipada)"):
            tiempo_final = time.time() - st.session_state.start_time
            if tiempo_final == 0: tiempo_final = 1
                 
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
            save_typing_results(st.session_state.results) # GUARDA SÓLO UNA VEZ
            st.rerun()

    # 3. Área de Resultados (Finalizado)
    if st.session_state.finished and st.session_state.results:
        st.success(f"🎉 ¡Prueba Completada, {st.session_state.results['ID Agente']}!")
        
        col1, col2, col3 = st.columns(3)
        
        col1.metric("Velocidad (WPM)", f"{st.session_state.results['WPM']:.2f}")
        col2.metric("Precisión", f"{st.session_state.results['Precisión (%)']:.2f}%")
        col3.metric("Errores", f"{st.session_state.results['Errores']}")

        if st.button("🔁 Iniciar Nueva Prueba"):
            st.session_state.started = False
            st.session_state.finished = False
            st.session_state.results = None
            st.session_state.texto_escrito = ""
            st.rerun()

def show_typing_ranking():
    """Módulo: Ranking de la Prueba de Velocidad."""
    st.header("🏆 Ranking de Velocidad (WPM)")
    st.markdown("---")
    
    client = get_gsheet_client()
    if not client:
        st.error("No se pudo conectar a Google Sheets para el ranking.")
        return

    try:
        # Lee la hoja de resultados brutos
        sheet = client.open_by_key(st.secrets["gsheet_id"]) 
        results_ws = sheet.worksheet("Resultados Brutos")
        
        # Obtiene todos los registros
        data = results_ws.get_all_records()
        df = pd.DataFrame(data)

        if df.empty:
            st.info("Aún no hay resultados de la gincana para mostrar.")
            return

        # Lógica para encontrar el mejor WPM por agente
        df['WPM'] = pd.to_numeric(df['WPM'], errors='coerce')
        
        # Agrupar y encontrar la fila con el WPM máximo para cada agente
        idx = df.groupby(['ID Agente'])['WPM'].transform(max) == df['WPM']
        ranking_consolidado = df[idx].sort_values(by='WPM', ascending=False)
        
        st.subheader("Mejores Resultados Históricos")
        st.dataframe(ranking_consolidado[['ID Agente', 'WPM', 'Precisión (%)', 'Fecha/Hora']], hide_index=True)

        st.markdown("---")
        st.subheader("TOP 3")
        
        # Formateo visual del TOP 3
        top3 = ranking_consolidado.head(3).reset_index(drop=True)
        if not top3.empty:
            st.metric("🥇 Primer Lugar", f"{top3.loc[0, 'ID Agente']} con {top3.loc[0, 'WPM']} WPM")
        if len(top3) > 1:
            st.metric("🥈 Segundo Lugar", f"{top3.loc[1, 'ID Agente']} con {top3.loc[1, 'WPM']} WPM")
        if len(top3) > 2:
            st.metric("🥉 Tercer Lugar", f"{top3.loc[2, 'ID Agente']} con {top3.loc[2, 'WPM']} WPM")

    except Exception as e:
        st.error(f"❌ Error al generar el ranking: {e}. ¿Están las columnas correctas?")


def show_fcr_ranking():
    """Módulo: Ranking Semanal de FCR."""
    st.header("📈 Ranking FCR Semanal")
    st.markdown("---")
    st.warning("⚠️ **Pendiente de Datos:** Este ranking necesita que conectes una pestaña o fuente con datos semanales de FCR.")
    
# --- FUNCIÓN PRINCIPAL DE LA APP ---

st.set_page_config(page_title="Gincana Contact Center", layout="wide")
st.title("🎯 Plataforma de Productividad del Contact Center")

# Muestra la confirmación de conexión si el cliente existe
if gsheet_client:
    st.success("✅ Conexión a Google Sheets exitosa.")
else:
    st.error("❌ Fallo en la conexión a Google Sheets. Revisa los Secrets.")

# Inicialización de estado global
if 'started' not in st.session_state: st.session_state.started = False
if 'finished' not in st.session_state: st.session_state.finished = False
if 'results' not in st.session_state: st.session_state.results = None
if 'texto_escrito' not in st.session_state: st.session_state.texto_escrito = ""

# --- BARRA DE NAVEGACIÓN LATERAL ---

st.sidebar.title("Menú de Módulos")
st.sidebar.markdown("---")

menu_options = {
    "⌨️ Gincana (Juego)": show_typing_game,
    "🏆 Ranking de Velocidad": show_typing_ranking,
    "📈 Ranking FCR Semanal": show_fcr_ranking,
}

selection = st.sidebar.radio("Selecciona una sección:", list(menu_options.keys()))

if selection in menu_options:
    menu_options[selection]()
