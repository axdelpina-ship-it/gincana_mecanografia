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

# --- CSS PERSONALIZADO (CLEAN & PROFESIONAL con BARRA LATERAL CLARA) ---
st.markdown("""
<style>
    /* 1. FUENTE GLOBAL */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Roboto', sans-serif;
    }

    /* 2. ESTILO BARRA LATERAL (FORZADO a color claro para visibilidad) */
    [data-testid="stSidebar"] {
        background-color: #F0F2F6; 
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.5); 
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
    /* Estilo del texto de la gincana para que se vea bien en el contenedor */
    .typing-text {
        font-size: 1.1em;
        line-height: 1.6;
        padding: 15px;
        border: 1px solid #444;
        border-radius: 5px;
        background-color: #1E222A; /* Fondo oscuro similar a metric */
        color: #FFFFFF;
        white-space: pre-wrap; /* Asegura saltos de línea y buen formato */
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
    
    # WPM (Neto: (Caracteres correctos - errores) / 5)
    if tiempo_tecleo_seg > 0:
        palabras_netas_tecleo = max(0, (caracteres_correctos - errores_caracter) / 5)
        wpm = (palabras_netas_tecleo / (tiempo_tecleo_seg / 60))
        wpm = max(0, round(wpm, 2))
    else:
        wpm = 0.00

    # Precisión
    if len(original_limpio) > 0 and caracteres_escritos > 0:
        precision_porcentaje = (caracteres_correctos / len(original_limpio)) * 100
        precision_porcentaje = max(0, min(100, precision_porcentaje))
    else:
        precision_porcentaje = 0.00
        
    # RPM (Lectura por Minuto)
    if tiempo_lectura_seg > 0:
        rpm = (total_palabras_original / (tiempo_lectura_seg / 60))
        rpm = round(rpm, 2)
    else:
        rpm = 0.00

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
            results_dict['Respuestas Correctas'], 
            results_dict['Texto Escrito']
        ]
        
        results_ws.append_row(row_data)
        st.session_state.guardado_exitoso = True
        
    except Exception as e:
        st.error(f"❌ ¡ERROR al guardar los resultados! Revisa que la hoja de cálculo exista y el formato de las cabeceras (10 columnas): {e}")
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
    if 'progress_value' in st.session_state: del st.session_state['progress_value'] # Limpia la distracción
    st.rerun() # Fuerza el reinicio de la aplicación


# --- MÓDULOS DE NAVEGACIÓN (FLUJO PRINCIPAL) ---

def show_typing_game():
    """Módulo principal: La interfaz de la Gincana de Mecanografía en 4 fases."""
    st.header("⌨️ Gincana de Mecanografía y Comprensión 🛠️")
    st.markdown("---")
    
    # ----------------------------------------
    # FASE 0: CUENTA REGRESIVA
    # ----------------------------------------
    if st.session_state.current_phase == "COUNTDOWN":
        placeholder = st.empty()
        
        tiempo_transcurrido = time.time() - st.session_state.countdown_start
        tiempo_restante = st.session_state.countdown_target - int(tiempo_transcurrido)
        
        if tiempo_restante > 0:
            placeholder.markdown(f"## 🛑 Prepárate para Leer... **{tiempo_restante}**", unsafe_allow_html=True)
            time.sleep(1)
            st.rerun()
        else:
            # Finaliza la cuenta, inicia el cronómetro de lectura y pasa a la fase activa
            st.session_state.current_phase = "READING_ACTIVE"
            st.session_state.start_time = time.time() # INICIO DEL CRONÓMETRO DE LECTURA
            st.session_state.update_count = 0 # Contador para el refresco del cronómetro
            st.rerun()


    # ----------------------------------------
    # FASE 1: INGRESO DE ID
    # ----------------------------------------
    if st.session_state.current_phase == "ID_INPUT":
        st.session_state.agente_id = st.text_input("Ingresa tu ID de Agente:", key="agente_id_input")
        
        st.subheader("📚 Paso 1: Información Importante")
        st.info("ℹ️ **Antes de comenzar:** Esta prueba tiene 3 partes. Primero, leerás un texto. El tiempo de lectura (**RPM**) influye en tu resultado. Luego, tendrás 60 segundos para teclear y, finalmente, responderás 3 preguntas de comprensión.")

        if st.button("▶️ Comenzar el Test (Iniciar Cuenta Regresiva)"): 
            if st.session_state.agente_id:
                st.session_state.current_phase = "READING_WARNING" # Paso intermedio para la advertencia
                st.rerun()
            else:
                st.warning("Por favor, ingresa tu ID de Agente para iniciar.")

    # ----------------------------------------
    # FASE 2A: ADVERTENCIA Y BOTÓN DE INICIO DE CUENTA
    # ----------------------------------------
    elif st.session_state.current_phase == "READING_WARNING":
        st.subheader("🛑 Listo para Iniciar la Lectura")
        st.warning("⚠️ **Advertencia:** Al presionar 'Comenzar a Contar', iniciarás una cuenta regresiva de 5 segundos. **El texto aparecerá y el tiempo de lectura comenzará inmediatamente después.**")
        
        if st.button("Comenzar a Contar (5 Segundos)"):
            st.session_state.current_phase = "COUNTDOWN"
            st.session_state.countdown_start = time.time()
            st.session_state.countdown_target = 5
            st.rerun()


    # ----------------------------------------
    # FASE 2B: LECTURA DEL TEXTO (CRONÓMETRO ACTIVO Y VOLUNTARIO)
    # ----------------------------------------
    elif st.session_state.current_phase == "READING_ACTIVE":
        st.subheader("📚 Paso 1: Lee el siguiente texto con atención")
        st.info("📢 **IMPORTANTE:** Cuando termines de leer y creas haber entendido el texto, presiona el botón para detener el cronómetro y pasar a la prueba de tecleo.")
        
        # Muestra el texto legible
        st.markdown(f'<div class="typing-text">{TEXTO_PRUEBA_GINCANA}</div>', unsafe_allow_html=True)

        tiempo_placeholder = st.empty()
        
        # CRONÓMETRO DE LECTURA DE BAJA FRECUENCIA (Para no bloquear el botón)
        tiempo_transcurrido = time.time() - st.session_state.start_time
        tiempo_placeholder.info(f"⏰ Tiempo de lectura transcurrido: **{int(tiempo_transcurrido)}** segundos.")
        
        # Pequeño bucle que solo se ejecuta unas pocas veces para dar feedback inicial sin ser intrusivo
        if st.session_state.update_count < 15: # Refresca por ~7.5 segundos (15 * 0.5s)
            st.session_state.update_count += 1
            time.sleep(0.5)
            st.rerun()


        if st.button("Terminé de leer y Continuar a la Prueba de Tecleo ➡️"):
            # Captura el tiempo final al presionar
            if st.session_state.start_time:
                st.session_state.reading_time = time.time() - st.session_state.start_time
            else:
                 st.session_state.reading_time = 0 
                 
            st.session_state.current_phase = "TYPING"
            st.session_state.start_time = time.time() # Reinicia el cronómetro para el tecleo
            st.snow()
            st.rerun()


    # ----------------------------------------
    # FASE 3: TECLEO (JUEGO CON DISTRACCIÓN)
    # ----------------------------------------
    elif st.session_state.current_phase == "TYPING":
        
        tiempo_transcurrido = time.time() - st.session_state.start_time
        tiempo_restante = DURACION_SEGUNDOS - tiempo_transcurrido
        
        st.subheader(f"📝 Paso 2: ¡Teclea ahora, {st.session_state.agente_id}!")
        timer_placeholder = st.empty()
        
        # --- DISTRACCIÓN (BARRA DE PROGRESO "GUSANITO") ---
        if 'progress_value' not in st.session_state:
            st.session_state.progress_value = 0.05
        
        # Modifica el valor en cada ciclo para que parezca que "se mueve" y nunca llega a 100% o 0%
        # Simula un proceso constante y molesto
        st.session_state.progress_value = (st.session_state.progress_value + 0.01) % 0.9 + 0.05
        st.progress(st.session_state.progress_value, text="**🚨 Atención:** Proceso interno en ejecución... ¡Concéntrate! 🚨")
        st.markdown("---")
        # ----------------------------------------------------
        
        if tiempo_restante > 0:
            timer_placeholder.warning(f"⏳ Tiempo restante: **{int(tiempo_restante)}** segundos.")
        else:
            timer_placeholder.error("🚨 ¡TIEMPO AGOTADO! Tu tecleo ha terminado. Presiona Continuar.")

        st.markdown(f'<div class="typing-text">{TEXTO_PRUEBA_GINCANA}</div>', unsafe_allow_html=True)

        texto_escrito = st.text_area("Comienza a escribir aquí...", 
                                     height=200, 
                                     key="typing_area", 
                                     value=st.session_state.texto_escrito,
                                     disabled=tiempo_restante <= 0)
        
        st.session_state.texto_escrito = texto_escrito 

        # Bucle de refresco del cronómetro de tecleo y distracción
        if tiempo_restante > 0 and tiempo_restante <= DURACION_SEGUNDOS:
            time.sleep(1)
            st.rerun() 

        if tiempo_restante <= 0 and 'typing_finished' not in st.session_state:
            st.session_state.typing_time = DURACION_SEGUNDOS 
            st.session_state.typing_finished = True
            st.rerun()
            
        if st.session_state.get('typing_finished', False) or st.button("🛑 Finalizar Tecleo (Anticipado) y Continuar"):
            if not st.session_state.get('typing_finished', False):
                st.session_state.typing_time = time.time() - st.session_state.start_time
                
            st.session_state.current_phase = "COMPREHENSION"
            if 'typing_finished' in st.session_state: del st.session_state['typing_finished'] 
            st.rerun()


    # ----------------------------------------
    # FASE 4: COMPRENSIÓN
    # ----------------------------------------
    elif st.session_state.current_phase == "COMPREHENSION":
        st.subheader("🧠 Paso 3: Preguntas de Comprensión")
        st.info("Responde las siguientes preguntas basadas *únicamente* en el texto que leíste al inicio.")

        if 'comprehension_answers' not in st.session_state:
            st.session_state.comprehension_answers = [None] * len(PREGUNTAS_COMPRENSION)

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

        # Botón de nueva prueba en la sección de resultados
        if st.button("🔁 Iniciar Nueva Prueba (desde Resultados)"):
            reiniciar_test()
            st.rerun()


# --- MÓDULOS DE RANKING ---

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
            st.metric("🥇 Primer Lugar", f"{top3.loc[0, 'ID Agente']}", f"{top3.loc[0, 'WPM']} WPM")
        if len(top3) > 1:
            st.metric("🥈 Segundo Lugar", f"{top3.loc[1, 'ID Agente']}", f"{top3.loc[1, 'WPM']} WPM")
        if len(top3) > 2:
            st.metric("🥉 Tercer Lugar", f"{top3.loc[2, 'ID Agente']}", f"{top3.loc[2, 'WPM']} WPM")

    except Exception as e:
        st.error(f"❌ Error al generar el ranking: {e}. ¿Están las columnas correctas en 'Resultados Brutos'?")


def show_fcr_ranking(worksheet_name):
    """Módulo: Ranking Semanal de FCR, dinámico con medallas y barra de progreso."""
    st.header(f"📈 Ranking FCR Semanal: {worksheet_name.replace('Ranking FCR Semanal - ', '')}")
    st.markdown("---")
    
    client = get_gsheet_client()
    if not client:
        st.error("❌ No se pudo conectar a Google Sheets. Revisa tu configuración de Secrets.")
        return

    try:
        sheet = client.open_by_key(st.secrets["gsheet_id"]) 
        results_ws = sheet.worksheet(worksheet_name)
        
        data = results_ws.get_all_records()
        df = pd.DataFrame(data)

        if df.empty:
            st.info(f"📊 Aún no hay datos en la pestaña '{worksheet_name}'.")
            return

        df['% +'] = df['% +'].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
        
        df = df.sort_values(by='Ranking', ascending=True).reset_index(drop=True)

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

        max_percentage = df['% +'].max()
        if max_percentage == 0:
            max_percentage = 1 

        st.dataframe(
            df[['Ranking', 'Empleado', 'Chats', 'Cantidad +', '% +']],
            column_config={
                "% +": st.column_config.ProgressColumn(
                    "Progreso FCR",
                    help="Proximidad al mejor porcentaje de FCR/CSAT Positivo",
                    format="%.2f%%",
                    min_value=0,
                    max_value=max_percentage,
                ),
                "Empleado": st.column_config.TextColumn("Agente"),
                "Cantidad +": st.column_config.NumberColumn("CSAT Positivo", format="%d")
            },
            hide_index=True
        )

    except gspread.WorksheetNotFound:
        st.error(f"❌ La hoja de cálculo NO tiene una pestaña llamada '{worksheet_name}'.")
    except Exception as e:
        st.error(f"❌ Error al generar el Ranking FCR. ¿Están las columnas correctas?: {e}")


def show_fcr_global_ranking():
    """Consolida datos de todos los turnos, calcula el TOP 10 global y muestra las métricas."""
    
    st.header("👑 TOP 10 Global FCR/CSAT") 
    st.markdown("---")
    
    client = get_gsheet_client()
    if not client:
        st.error("❌ No se pudo conectar a Google Sheets para el ranking global.")
        return

    fcr_sheets = {
        "PM": "Ranking FCR Semanal - PM",
        "AM": "Ranking FCR Semanal - AM",
        "NT1": "Ranking FCR Semanal - NT1",
        "NT2": "Ranking FCR Semanal - NT2",
    }
    
    all_data = []
    
    for turno_key, sheet_name in fcr_sheets.items():
        try:
            sheet = client.open_by_key(st.secrets["gsheet_id"])
            results_ws = sheet.worksheet(sheet_name)
            
            df_turno = pd.DataFrame(results_ws.get_all_records())
            
            if 'Total P+N' in df_turno.columns:
                df_turno['Total P+N'] = pd.to_numeric(df_turno['Total P+N'], errors='coerce').fillna(0)
            
            if '% +' in df_turno.columns:
                df_turno['% +'] = df_turno['% +'].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
                
            df_turno['Turno'] = turno_key
            all_data.append(df_turno)
            
        except gspread.WorksheetNotFound:
            st.warning(f"⚠️ Omisión: No se encontró la hoja '{sheet_name}'.")
        except Exception as e:
            st.error(f"❌ Error al procesar datos del turno {turno_key}: {e}")
            
    if not all_data:
        st.info("No se pudo cargar la data de ningún turno.")
        return

    df_consolidado = pd.concat(all_data, ignore_index=True)
    df_consolidado = df_consolidado.reset_index(drop=True) 
    df_consolidado = df_consolidado.dropna(subset=['Empleado', 'Total P+N', '% +'])
    
    df_consolidado = df_consolidado.loc[df_consolidado.groupby('Empleado')['Total P+N'].idxmax()]
    
    df_consolidado = df_consolidado.sort_values(
        by=['Total P+N', '% +'], 
        ascending=[False, False]
    ).reset_index(drop=True)

    df_top10 = df_consolidado.head(10).copy()
    
    if df_top10.empty:
        st.info("No hay suficientes datos para generar el TOP 10.")
        return

    st.subheader("🥇 Los Héroes de la Semana")
    
    global_leader = df_top10.iloc[0]
    high_pct_leader = df_top10.loc[df_top10['% +'].idxmax()]
    
    col_trophy, col_msg = st.columns([1, 4])
    
    with col_trophy:
        st.markdown(f"## 🏆")
        st.markdown(f"## 👑")
    
    with col_msg:
        st.info(
            f"**¡Felicidades, {global_leader['Empleado']}!** se corona como el operador global con el **mayor volumen de satisfacción** ({global_leader['Total P+N']:.0f} Total P+N)."
        )
        st.success(
            f"**{high_pct_leader['Empleado']}** destaca con el **porcentaje positivo más alto** del top ({high_pct_leader['% +']:.2f}%)."
        )
        
        desempate_count = df_consolidado['Total P+N'].duplicated(keep='first').sum()
        if desempate_count > 0:
            st.warning(
                f"**Nota Importante:** Los desempates en 'Total P+N' fueron resueltos utilizando el criterio secundario del porcentaje positivo (**% +**)."
            )

    st.markdown("---")
    
    st.subheader("Tabla Consolidada (TOP 10)")
    
    max_pn_value = df_top10['Total P+N'].max()
    if max_pn_value == 0: max_pn_value = 1

    st.dataframe(
        df_top10[[
            'Empleado', 
            'Turno', 
            'Total P+N', 
            '% +', 
            'Chats', 
            'Cantidad +'
        ]].reset_index(drop=True).assign(Rank=lambda x: x.index + 1),
        column_order=('Rank', 'Empleado', 'Turno', 'Total P+N', '% +', 'Chats', 'Cantidad +'),
        column_config={
            "Total P+N": st.column_config.ProgressColumn(
                "Total P+N (Volumen)",
                help="Volumen total de satisfacción (P+N)",
                format="%d",
                min_value=0,
                max_value=max_pn_value,
            ),
            "% +": st.column_config.NumberColumn(
                "Porcentaje Positivo",
                format="%.2f%%",
            ),
            "Turno": st.column_config.TextColumn("Turno"),
            "Rank": st.column_config.NumberColumn("Posición", format="%d")
        },
        hide_index=True
    )


# --- FUNCIÓN PRINCIPAL DE LA APP ---

st.set_page_config(page_title="Plataforma de Productividad", layout="wide")
st.title("🎯 Plataforma de Productividad del Contact Center")

# Chequeo de conexión y mensaje inicial
if gsheet_client:
    st.success("✅ Conexión a Google Sheets exitosa (Solo para guardar resultados y rankings).")
else:
    st.error("❌ Fallo en la conexión a Google Sheets. Los resultados no se podrán guardar ni los rankings se cargarán. Revisa tus Secrets (gsheet_id y credenciales).")

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

# Botón de Reinicio Global en la Barra Lateral
st.sidebar.markdown("---")
if st.sidebar.button("🚨 Reiniciar Test (En cualquier momento)"):
    reiniciar_test()


if current_module == "game":
    show_typing_game()
    
elif current_module == "typing_ranking":
    show_typing_ranking()

elif current_module == "fcr_ranking":
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
