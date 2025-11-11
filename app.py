import streamlit as st
import pandas as pd
from datetime import datetime
import time
import re
import gspread
from google.oauth2 import service_account 

# --- CONFIGURACIÓN ESTÁTICA (Para evitar cuota de Google Sheets) ---

DURACION_SEGUNDOS = 60 # Tiempo fijo para la prueba de tecleo
TEXTO_PRUEBA_GINCANA = (
    "La atención al cliente en un Contact Center requiere precisión y velocidad. "
    "La métrica clave es el FCR, First Contact Resolution, que mide la capacidad "
    "de resolver el problema del cliente en la primera interacción. Un alto FCR "
    "está directamente relacionado con la satisfacción del cliente (CSAT) y la "
    "eficiencia operativa. El manejo adecuado de la información y la capacidad "
    "de teclear con fluidez son habilidades fundamentales para el éxito."
)

PREGUNTAS_COMPRENSION = [
    {
        "pregunta": "¿Cuál es la métrica clave mencionada en el texto?",
        "opciones": ["A. CSAT", "B. FCR", "C. WPM"],
        "respuesta_correcta": "B. FCR"
    },
    {
        "pregunta": "¿Con qué está directamente relacionado un alto FCR?",
        "opciones": ["A. Ahorro de tiempo", "B. Satisfacción del Cliente (CSAT)", "C. Cantidad de llamadas"],
        "respuesta_correcta": "B. Satisfacción del Cliente (CSAT)"
    },
    {
        "pregunta": "¿Qué habilidades se mencionan como fundamentales?",
        "opciones": ["A. Hablar inglés", "B. Vender productos", "C. Manejo de información y fluidez al teclear"],
        "respuesta_correcta": "C. Manejo de información y fluidez al teclear"
    }
]

# --- CSS PERSONALIZADO (CLEAN & PROFESIONAL) ---
st.markdown("""
<style>
    /* 1. FUENTE GLOBAL */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Roboto', sans-serif;
    }

    /* 2. ESTILO GLASSMORPHISM (Barra Lateral) */
    [data-testid="stSidebar"] {
        background: rgba(14, 17, 23, 0.8);
        box-shadow: 0 0 15px rgba(0, 191, 255, 0.1);
        backdrop-filter: blur(3px);
        -webkit-backdrop-filter: blur(3px);
        border-right: 1px solid rgba(0, 191, 255, 0.2);
    }

    /* 3. ESTILO PARA LAS TARJETAS METRIC (st.metric) */
    [data-testid="stMetric"] {
        background-color: #1E222A;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #00BFFF; 
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: 0 4px 15px rgba(0, 191, 255, 0.3);
        transform: translateY(-2px);
    }

    [data-testid="stMetricLabel"] {
        font-weight: 500;
        color: #B0B7C0; 
        font-size: 0.9em;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.8em;
        color: #FFFFFF; 
        font-weight: 700;
    }
    
    /* 4. TÍTULOS Y CABECERAS */
    .st-emotion-cache-10trblm { 
        border-bottom: 2px solid #00BFFF;
        padding-bottom: 5px;
        margin-bottom: 10px;
        color: #FFFFFF !important; 
    }
</style>
""", unsafe_allow_html=True)


# --- CONEXIÓN A GOOGLE SHEETS (Solo para GUARDAR RESULTADOS) ---

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
    except Exception:
        return None

gsheet_client = get_gsheet_client()

# --- Funciones de Cálculo y Guardado ---

def calcular_metrics(texto_original, texto_escrito, tiempo_tecleo_seg, tiempo_lectura_seg):
    """Calcula WPM, precisión, RPM y errores."""
    
    original_limpio = re.sub(r'\s+', ' ', texto_original.strip())
    escrito_limpio = re.sub(r'\s+', ' ', texto_escrito.strip())
    
    total_palabras_original = len(original_limpio.split())
    
    caracteres_correctos = 0
    caracteres_escritos = len(escrito_limpio)
    
    for i in range(min(len(original_limpio), caracteres_escritos)):
        if original_limpio[i] == escrito_limpio[i]:
            caracteres_correctos += 1
            
    errores_caracter = max(0, caracteres_escritos - caracteres_correctos) 
    
    # WPM (Neto, Caracteres correctos / 5)
    palabras_netas_tecleo = max(0, (caracteres_correctos - errores_caracter) / 5)
    wpm = (palabras_netas_tecleo / (tiempo_tecleo_seg / 60))
    wpm = max(0, round(wpm, 2))

    # Precisión
    if len(original_limpio) > 0:
        precision_porcentaje = (caracteres_correctos / len(original_limpio)) * 100
        precision_porcentaje = max(0, min(100, precision_porcentaje))
    else:
        precision_porcentaje = 0
        
    # RPM (Lectura por Minuto)
    if tiempo_lectura_seg > 0:
        rpm = (total_palabras_original / (tiempo_lectura_seg / 60))
        rpm = round(rpm, 2)
    else:
        rpm = 0

    return wpm, round(precision_porcentaje, 2), errores_caracter, rpm

def save_typing_results(results_dict):
    """Guarda los resultados de la prueba en la hoja 'Resultados Brutos'."""
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
            results_dict['Duracion Tecleo (s)'],
            results_dict['Duracion Lectura (s)'],
            results_dict['RPM'],
            results_dict['Respuestas Correctas'], # Aquí se guarda la métrica de Comprensión
            results_dict['Texto Escrito']
        ]
        
        results_ws.append_row(row_data)
        st.session_state.guardado_exitoso = True
        
    except Exception as e:
        st.error(f"❌ ¡ERROR al guardar los resultados! Revisa que la hoja de cálculo exista, la clave 'gsheet_id' y que las 10 cabeceras sean correctas: {e}")
        st.session_state.guardado_exitoso = False

def reiniciar_test():
    """Resetea todas las variables de estado para un nuevo test."""
    st.session_state.agente_id = ""
    st.session_state.current_phase = "ID_INPUT"
    st.session_state.start_time = None
    st.session_state.reading_time = 0
    st.session_state.typing_time = 0
    st.session_state.finished = False
    st.session_state.saving = False
    st.session_state.texto_escrito = ""
    st.session_state.guardado_exitoso = False
    st.session_state.comprehension_answers = [None] * len(PREGUNTAS_COMPRENSION)
    st.session_state.results = None


# --- MÓDULOS DE NAVEGACIÓN ---

def show_typing_game():
    """Módulo principal: La interfaz de la Gincana de Mecanografía en 4 fases."""
    st.header("⌨️ Gincana de Mecanografía y Comprensión 🛠️")
    st.markdown("---")
    
    # ----------------------------------------
    # FASE 1: INGRESO DE ID
    # ----------------------------------------
    if st.session_state.current_phase == "ID_INPUT":
        st.session_state.agente_id = st.text_input("Ingresa tu ID de Agente:", key="agente_id_input")
        if st.button("▶️ Iniciar Lectura"):
            if st.session_state.agente_id:
                st.session_state.current_phase = "READING"
                st.session_state.start_time = time.time() 
                st.rerun()

    # ----------------------------------------
    # FASE 2: LECTURA DEL TEXTO
    # ----------------------------------------
    elif st.session_state.current_phase == "READING":
        st.subheader("📚 Paso 1: Lee el siguiente texto con atención")
        st.info(TEXTO_PRUEBA_GINCANA)
        st.warning("El tiempo de lectura está corriendo. Cuando termines de leer, haz clic en Continuar.")

        tiempo_transcurrido = time.time() - st.session_state.start_time
        st.caption(f"Tiempo de lectura transcurrido: **{int(tiempo_transcurrido)}** segundos.")

        if st.button("Continúar a la Prueba de Tecleo ➡️"):
            st.session_state.reading_time = tiempo_transcurrido
            st.session_state.current_phase = "TYPING"
            st.session_state.start_time = time.time() 
            st.snow()
            st.rerun()

    # ----------------------------------------
    # FASE 3: TECLEO (JUEGO)
    # ----------------------------------------
    elif st.session_state.current_phase == "TYPING":
        
        tiempo_transcurrido = time.time() - st.session_state.start_time
        tiempo_restante = DURACION_SEGUNDOS - tiempo_transcurrido
        
        st.subheader(f"📝 Paso 2: ¡Teclea ahora, {st.session_state.agente_id}!")
        timer_placeholder = st.empty()
        timer_placeholder.warning(f"⏳ Tiempo restante: **{int(tiempo_restante)}** segundos.")
        
        st.info(TEXTO_PRUEBA_GINCANA)

        texto_escrito = st.text_area("Comienza a escribir aquí...", 
                                     height=200, 
                                     key="typing_area", 
                                     value=st.session_state.texto_escrito,
                                     disabled=tiempo_restante <= 0)
        
        st.session_state.texto_escrito = texto_escrito 

        if tiempo_restante > 0:
            time.sleep(1)
            st.rerun()

        else:
            st.session_state.typing_time = DURACION_SEGUNDOS
            st.session_state.current_phase = "COMPREHENSION"
            timer_placeholder.info("¡Tiempo Agotado! Presiona Continuar.")
            st.rerun()

        if st.button("🛑 Finalizar Tecleo (Anticipado)"):
            st.session_state.typing_time = time.time() - st.session_state.start_time
            st.session_state.current_phase = "COMPREHENSION"
            st.rerun()

    # ----------------------------------------
    # FASE 4: COMPRENSIÓN
    # ----------------------------------------
    elif st.session_state.current_phase == "COMPREHENSION":
        st.subheader("🧠 Paso 3: Preguntas de Comprensión")
        st.info("Responde las siguientes preguntas basadas *únicamente* en el texto que leíste al inicio.")

        if 'comprehension_answers' not in st.session_state:
            st.session_state.comprehension_answers = [None] * len(PREGUNTAS_COMPRENSION)

        # Muestra las preguntas
        for i, item in enumerate(PREGUNTAS_COMPRENSION):
            selected_answer = st.radio(
                f"**Pregunta {i+1}:** {item['pregunta']}",
                item['opciones'],
                key=f"q_{i}"
            )
            st.session_state.comprehension_answers[i] = selected_answer

        if st.button("Finalizar Test y Ver Resultados ➡️"):
            st.session_state.current_phase = "RESULTS"
            st.balloons()
            st.rerun()

    # ----------------------------------------
    # FASE 5: RESULTADOS Y GUARDADO
    # ----------------------------------------
    elif st.session_state.current_phase == "RESULTS":
        
        # --- CÁLCULOS FINALES ---
        wpm, precision, errores, rpm = calcular_metrics(
            TEXTO_PRUEBA_GINCANA, 
            st.session_state.texto_escrito, 
            st.session_state.typing_time,
            st.session_state.reading_time
        )
        
        respuestas_correctas = 0
        for i, item in enumerate(PREGUNTAS_COMPRENSION):
            if st.session_state.comprehension_answers[i] == item["respuesta_correcta"]:
                respuestas_correctas += 1

        st.session_state.results = {
            'ID Agente': st.session_state.agente_id,
            'Fecha/Hora': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'WPM': wpm,
            'Precisión (%)': precision,
            'Errores': errores,
            'Duracion Tecleo (s)': round(st.session_state.typing_time, 2),
            'Duracion Lectura (s)': round(st.session_state.reading_time, 2),
            'RPM': rpm,
            'Respuestas Correctas': respuestas_correctas,
            'Texto Escrito': st.session_state.texto_escrito
        }
        
        st.subheader("📊 Tus Resultados Finales")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Velocidad (WPM)", f"{st.session_state.results['WPM']:.2f}")
        col2.metric("Lectura (RPM)", f"{st.session_state.results['RPM']:.2f}")
        col3.metric("Precisión", f"{st.session_state.results['Precisión (%)']:.2f}%")
        col4.metric("Comprensión", f"{st.session_state.results['Respuestas Correctas']}/{len(PREGUNTAS_COMPRENSION)}")
        
        st.markdown("---")
        
        st.info("⚠️ Las métricas de 'borrado' no están disponibles en Streamlit nativo. Se utiliza WPM Neto y Errores de Carácter.")

        if not st.session_state.saving:
            if st.button("💾 Guardar Resultados en Google Sheets"):
                st.session_state.saving = True
                save_typing_results(st.session_state.results)
                st.rerun()

        if st.session_state.guardado_exitoso:
            st.success("✅ ¡Tu resultado se ha guardado exitosamente!")
        elif st.session_state.saving and not st.session_state.guardado_exitoso:
            st.error("❌ Hubo un error al guardar. Revisa el error anterior.")

        if st.button("🔁 Iniciar Nueva Prueba"):
            reiniciar_test()
            st.rerun()


def show_typing_ranking():
    # El código de los Rankings debe ir aquí y usar la conexión a Google Sheets.
    # Se omite para no repetir el código extenso, pero DEBES INCLUIRLO.
    st.header("🏆 Ranking de Velocidad (WPM)")
    st.warning("El código para cargar el ranking de Google Sheets debe ser pegado aquí.")
    pass 
    
def show_fcr_ranking(worksheet_name):
    st.header(f"📈 Ranking FCR Semanal: {worksheet_name.replace('Ranking FCR Semanal - ', '')}")
    st.warning("El código para cargar el ranking de FCR semanal debe ser pegado aquí.")
    pass

def show_fcr_global_ranking():
    st.header("👑 TOP 10 Global FCR/CSAT") 
    st.warning("El código para cargar el ranking de FCR global debe ser pegado aquí.")
    pass

# --- FUNCIÓN PRINCIPAL DE LA APP ---

st.set_page_config(page_title="Plataforma de Productividad", layout="wide")
st.title("🎯 Plataforma de Productividad del Contact Center")

# Chequeo de conexión (solo informativo)
if gsheet_client:
    st.success("✅ Conexión a Google Sheets exitosa (Solo para guardar resultados).")
else:
    st.error("❌ Fallo en la conexión a Google Sheets. Los resultados no se podrán guardar. Revisa tus Secrets.")

# Inicialización de estado global (Máquina de estados)
if 'current_phase' not in st.session_state: reiniciar_test()


# --- BARRA DE NAVEGACIÓN LATERAL ---

st.sidebar.title("Menú de Módulos")
st.sidebar.markdown("---")

menu_options = {
    "⌨️ Gincana (Test) 🛠️": "game",
    "🏆 Ranking de Velocidad": "typing_ranking",
    "📈 Ranking FCR Semanal": "fcr_ranking",
    "👑 TOP 10 FCR Global": "fcr_global_ranking",
}

selection = st.sidebar.radio("Selecciona una sección:", list(menu_options.keys()))
current_module = menu_options[selection]

if current_module == "game":
    show_typing_game()
    
elif current_module == "typing_ranking":
    show_typing_ranking()

elif current_module == "fcr_ranking":
    # Lógica de selección de turno (requiere el código de show_fcr_ranking)
    st.sidebar.markdown("---")
    st.sidebar.subheader("Seleccionar Turno FCR")
    fcr_sheets = {
        "Turno PM": "Ranking FCR Semanal - PM",
        "Turno AM": "Ranking FCR Semanal - AM",
        "Turno Noche (NT1)": "Ranking FCR Semanal - NT1",
        "Turno Noche (NT2)": "Ranking FCR Semanal - NT2",
    }
    turno_selection = st.sidebar.radio("Ver Ranking del Turno:", list(fcr_sheets.keys()), index=0)
    worksheet_name = fcr_sheets[turno_selection]
    show_fcr_ranking(worksheet_name)
    
elif current_module == "fcr_global_ranking":
    show_fcr_global_ranking()
