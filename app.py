import streamlit as st
import pandas as pd
from datetime import datetime
import time
import re
import gspread
from google.oauth2 import service_account 

# --- CONFIGURACIÓN Y CONEXIÓN A GOOGLE SHEETS ---

@st.cache_resource
def get_gsheet_client():
    """Conecta con Google Sheets usando los secretos de Streamlit."""
    try:
        creds_info = st.secrets.gcp_service_account 
        
        creds = service_account.Credentials.from_service_account_info(
            dict(creds_info), 
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

gsheet_client = get_gsheet_client()

def get_config_data(client, sheet_id, _):
    """Lee el texto y la duración de la hoja 'Configuracion'."""
    if not client:
        return "Error: Cliente de Sheets no disponible.", 60

    try:
        sheet = client.open_by_key(sheet_id) 
        config_ws = sheet.worksheet("Configuracion")
        
        texto = config_ws.acell('A2').value
        duracion_val = config_ws.acell('B2').value
        # Aseguramos que la duración sea un entero válido
        duracion_seg = int(duracion_val) if duracion_val and str(duracion_val).isdigit() else 60
        
        return texto, duracion_seg
        
    except Exception as e:
        # Se verifica si el error es por falta de 'gsheet_id'
        if "gsheet_id" not in st.secrets:
            return f"Error: st.secrets no tiene la clave 'gsheet_id'. Revisa tus Secrets.", 60
        return f"Error al leer la configuración de Google Sheets: {e}", 60 

# Lectura global de la configuración (la clave 'gsheet_id' DEBE existir en secrets.toml)
try:
    TEXTO_DE_PRUEBA, DURACION_SEGUNDOS = get_config_data(gsheet_client, st.secrets["gsheet_id"], gsheet_client)
except KeyError:
    TEXTO_DE_PRUEBA, DURACION_SEGUNDOS = "Error: Falta la clave 'gsheet_id' en Streamlit Secrets.", 60

# --- Funciones de Cálculo y Guardado (sin cambios) ---

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

def save_typing_results(results_dict):
    """Guarda los resultados de la prueba en la hoja 'Resultados Brutos' (Solo se llama una vez)."""
    client = get_gsheet_client()
    if not client: 
        st.error("No se pudo guardar: Cliente de Sheets no disponible.")
        return

    try:
        sheet = client.open_by_key(st.secrets["gsheet_id"])
        results_ws = sheet.worksheet("Resultados Brutos") 
        
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
        st.session_state.guardado_exitoso = True
        
    except Exception as e:
        st.error(f"❌ ¡ERROR al guardar los resultados! Revisa la hoja 'Resultados Brutos': {e}")
        st.session_state.guardado_exitoso = False

# --- MÓDULOS DE NAVEGACIÓN ---

def show_typing_game():
    """Módulo principal: La interfaz de la Gincana de Mecanografía."""
    st.header("⌨️ Gincana de Mecanografía 🛠️")
    st.markdown("---")

    if TEXTO_DE_PRUEBA.startswith("Error"):
        st.error(TEXTO_DE_PRUEBA)
        st.warning("No se puede iniciar la prueba. Revisa la conexión y configuración de Google Sheets.")
        return

    agente_id = st.text_input("Ingresa tu ID de Agente:", key="agente_id_input", disabled=st.session_state.started)

    # ... (Resto de la lógica de show_typing_game se mantiene igual)
    st.subheader("Texto a teclear")
    st.info(TEXTO_DE_PRUEBA)

    if not st.session_state.started:
        if st.button(f"🚀 Iniciar Gincana ({DURACION_SEGUNDOS} Segundos)", disabled=not agente_id):
            if agente_id:
                st.session_state.started = True
                st.session_state.start_time = time.time()
                st.session_state.finished = False
                st.session_state.saving = False
                st.session_state.texto_escrito = "" 
                st.session_state.guardado_exitoso = False
                st.rerun()

    elif st.session_state.started and not st.session_state.finished:
        st.subheader(f"¡Teclea ahora, {agente_id}!")
        
        texto_escrito = st.text_area("Comienza a escribir aquí...", 
                                     height=200, 
                                     key="typing_area", 
                                     value=st.session_state.texto_escrito)
        
        st.session_state.texto_escrito = texto_escrito 

        tiempo_transcurrido = time.time() - st.session_state.start_time
        tiempo_restante = DURACION_SEGUNDOS - tiempo_transcurrido
        
        timer_placeholder = st.empty()
        
        if tiempo_restante > 0:
            timer_placeholder.warning(f"⏳ Tiempo restante: **{int(tiempo_restante)}** segundos.")
            
            if int(tiempo_restante) > 0:
                time.sleep(1)
                st.rerun()    

        else:
            st.session_state.finished = True
            timer_placeholder.info("¡Tiempo Agotado! Presiona GUARDAR RESULTADOS.")
            st.rerun()

        if st.button("🛑 Finalizar Prueba (Anticipada)"):
            st.session_state.finished = True
            st.rerun()

    if st.session_state.finished:
        
        tiempo_final = min(DURACION_SEGUNDOS, time.time() - st.session_state.start_time)
        tiempo_final = max(1, tiempo_final) 

        wpm, precision, errores = calcular_wpm_y_precision(
            TEXTO_DE_PRUEBA, 
            st.session_state.texto_escrito, 
            tiempo_final
        )

        st.session_state.results = {
            'ID Agente': agente_id,
            'Fecha/Hora': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'WPM': round(wpm, 2),
            'Precisión (%)': round(precision, 2),
            'Errores': errores,
            'Duracion (s)': round(tiempo_final, 2),
            'Texto Escrito': st.session_state.texto_escrito
        }
        
        st.subheader("📊 Tus Resultados")
        col1, col2, col3 = st.columns(3)
        col1.metric("Velocidad (WPM)", f"{st.session_state.results['WPM']:.2f}")
        col2.metric("Precisión", f"{st.session_state.results['Precisión (%)']:.2f}%")
        col3.metric("Errores", f"{st.session_state.results['Errores']}")

        if not st.session_state.saving:
            if st.button("💾 Finalizar Prueba y Guardar Resultados", help="Esto guardará tu registro en Google Sheets"):
                st.session_state.saving = True
                save_typing_results(st.session_state.results)
                st.rerun()

        if st.session_state.guardado_exitoso:
            st.success("✅ ¡Tu resultado se ha guardado exitosamente!")
        elif st.session_state.saving and not st.session_state.guardado_exitoso:
            st.error("❌ Hubo un error al guardar los resultados. Revisa los mensajes de arriba.")

        if st.button("🔁 Iniciar Nueva Prueba"):
            st.session_state.started = False
            st.session_state.finished = False
            st.session_state.saving = False
            st.session_state.results = None
            st.session_state.texto_escrito = ""
            st.session_state.guardado_exitoso = False
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
        sheet = client.open_by_key(st.secrets["gsheet_id"]) 
        results_ws = sheet.worksheet("Resultados Brutos")
        
        data = results_ws.get_all_records()
        df = pd.DataFrame(data)

        if df.empty:
            st.info("Aún no hay resultados de la gincana para mostrar.")
            return

        df['WPM'] = pd.to_numeric(df['WPM'], errors='coerce')
        idx = df.groupby(['ID Agente'])['WPM'].transform(max) == df['WPM']
        ranking_consolidado = df[idx].sort_values(by='WPM', ascending=False)
        
        st.subheader("Mejores Resultados Históricos")
        st.dataframe(ranking_consolidado[['ID Agente', 'WPM', 'Precisión (%)', 'Fecha/Hora']], hide_index=True)

        st.markdown("---")
        st.subheader("TOP 3")
        
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
    """Módulo: Ranking Semanal de FCR, dinámico con medallas y barra de progreso."""
    st.header("📈 Ranking FCR Semanal: Eficiencia y Calidad")
    st.markdown("---")
    
    client = get_gsheet_client()
    if not client:
        st.error("❌ No se pudo conectar a Google Sheets. Revisa tu configuración de Secrets.")
        return

    try:
        sheet = client.open_by_key(st.secrets["gsheet_id"]) 
        # ASUMIMOS que la pestaña se llama 'Ranking FCR Semanal'
        results_ws = sheet.worksheet("Ranking FCR Semanal")
        
        # Obtenemos los datos (columnas A a I)
        data = results_ws.get_all_records()
        df = pd.DataFrame(data)

        if df.empty:
            st.info("📊 Aún no hay datos en la pestaña 'Ranking FCR Semanal'.")
            return

        # 1. Limpieza y preparación de datos
        # Asumimos que la Columna 'Ranking' y la Columna '% +' (H) son críticas
        # Se limpia la columna de porcentaje, eliminando el '%' y convirtiendo a float
        df['% +'] = df['% +'].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
        
        # Ordenar por el Ranking (Columna A) o por el porcentaje (mayor es mejor)
        df = df.sort_values(by='Ranking', ascending=True).reset_index(drop=True)

        # 2. Mostrar TOP 3 con Medallas
        st.subheader("🏆 TOP 3 Semanal")
        top3 = df.head(3)
        col1, col2, col3 = st.columns(3)
        
        if not top3.empty:
            col1.metric("🥇 1er Lugar", f"{top3.loc[0, 'Empleado']}", f"{top3.loc[0, '% +']:.2f}%")
        if len(top3) > 1:
            col2.metric("🥈 2do Lugar", f"{top3.loc[1, 'Empleado']}", f"{top3.loc[1, '% +']:.2f}%")
        if len(top3) > 2:
            col3.metric("🥉 3er Lugar", f"{top3.loc[2, 'Empleado']}", f"{top3.loc[2, '% +']:.2f}%")

        st.markdown("---")
        st.subheader("Tabla de Posiciones y Progreso")

        # 3. Mostrar la tabla completa con barra de progreso
        
        # Obtenemos el valor máximo (para normalizar la barra de progreso)
        max_percentage = df['% +'].max()
        if max_percentage == 0:
            max_percentage = 1 # Evitar división por cero

        # Crear una columna visual para el progreso
        df['Progreso'] = df['% +'].apply(lambda x: f"|{'█' * int(x/max_percentage * 20)}{'░' * int(20 - x/max_percentage * 20)}| {x:.2f}%")
        
        # Mostrar las columnas más importantes (A, B, H, Progreso)
        st.dataframe(
            df[['Ranking', 'Empleado', 'Chats', 'Cantidad +', '% +', 'Progreso']],
            column_config={
                "Progreso": st.column_config.ProgressColumn(
                    "Progreso FCR",
                    help="Proximidad al mejor porcentaje de FCR/CSAT Positivo",
                    format="%.2f%%",
                    min_value=0,
                    max_value=max_percentage,
                ),
                "% +": st.column_config.NumberColumn(
                    "Porcentaje Positivo",
                    format="%.2f%%",
                )
            },
            hide_index=True
        )

    except gspread.WorksheetNotFound:
        st.error(f"❌ La hoja de cálculo NO tiene una pestaña llamada 'Ranking FCR Semanal'.")
        st.warning("Por favor, crea la pestaña con este nombre y asegúrate de que tenga las columnas A-I con datos.")
    except Exception as e:
        st.error(f"❌ Error al generar el Ranking FCR. ¿Están las columnas y el formato de datos correctos?: {e}")


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
if 'saving' not in st.session_state: st.session_state.saving = False 
if 'guardado_exitoso' not in st.session_state: st.session_state.guardado_exitoso = False


# --- BARRA DE NAVEGACIÓN LATERAL ---

st.sidebar.title("Menú de Módulos")
st.sidebar.markdown("---")

menu_options = {
    "⌨️ Gincana (Juego) 🛠️": show_typing_game,
    "🏆 Ranking de Velocidad": show_typing_ranking,
    "📈 Ranking FCR Semanal": show_fcr_ranking,
}

selection = st.sidebar.radio("Selecciona una sección:", list(menu_options.keys()))

if selection in menu_options:
    menu_options[selection]()
