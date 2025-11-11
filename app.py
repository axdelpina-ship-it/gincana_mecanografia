import streamlit as st
import pandas as pd
from datetime import datetime
import time
import re
import gspread
from google.oauth2 import service_account 

# --- CSS PERSONALIZADO para Glassmorphism y Estilo General ---
st.markdown("""
<style>
    /* 1. ESTILO GLASSMORPHISM para la BARRA LATERAL (Menú de Módulos) */
    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(5px);
        -webkit-backdrop-filter: blur(5px);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    /* 2. ESTILO para las tarjetas Metric (Mejora de st.metric) */
    [data-testid="stMetric"] {
        background-color: #0E1117; /* Fondo oscuro Streamlit */
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #00BFFF; /* Color Azul/Cyan llamativo */
        box-shadow: 2px 2px 8px rgba(0, 0, 0, 0.5);
    }

    [data-testid="stMetricLabel"] {
        font-weight: bold;
        color: #B0B7C0; /* Color de label estándar */
    }

    [data-testid="stMetricValue"] {
        font-size: 1.5em;
        color: #FFFFFF; /* Valor en blanco */
    }

    /* 3. Estilo para el área de selección en la barra lateral (radio) */
    .stRadio > label {
        color: #E0E0E0;
    }
    .stRadio [role="radiogroup"] > label:hover {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 5px;
    }
    
</style>
""", unsafe_allow_html=True)


# --- CONFIGURACIÓN Y CONEXIÓN A GOOGLE SHEETS (Mantenido) ---

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

# Función con argumento dummy (_) para evitar el UnhashableParamError
def get_config_data(client, sheet_id, _):
    """Lee el texto y la duración de la hoja 'Configuracion'."""
    if not client:
        return "Error: Cliente de Sheets no disponible.", 60

    try:
        sheet = client.open_by_key(sheet_id) 
        config_ws = sheet.worksheet("Configuracion")
        
        texto = config_ws.acell('A2').value
        duracion_val = config_ws.acell('B2').value
        duracion_seg = int(duracion_val) if duracion_val and str(duracion_val).isdigit() else 60
        
        return texto, duracion_seg
        
    except Exception as e:
        if "gsheet_id" not in st.secrets:
            return f"Error: st.secrets no tiene la clave 'gsheet_id'. Revisa tus Secrets.", 60
        # Maneja el error específico de hoja no encontrada o celda no numérica
        return f"Error al leer la configuración de Google Sheets: {e}", 60 

try:
    TEXTO_DE_PRUEBA, DURACION_SEGUNDOS = get_config_data(gsheet_client, st.secrets["gsheet_id"], gsheet_client)
except KeyError:
    TEXTO_DE_PRUEBA, DURACION_SEGUNDOS = "Error: Falta la clave 'gsheet_id' en Streamlit Secrets.", 60

# --- Funciones de Cálculo y Guardado (Mantenidas) ---

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


# --- MÓDULOS DE NAVEGACIÓN (Mantenidos) ---

def show_typing_game():
    """Módulo principal: La interfaz de la Gincana de Mecanografía."""
    st.header("⌨️ Gincana de Mecanografía 🛠️")
    st.markdown("---")

    if TEXTO_DE_PRUEBA.startswith("Error"):
        st.error(TEXTO_DE_PRUEBA)
        st.warning("No se puede iniciar la prueba. Revisa la conexión y configuración de Google Sheets.")
        return

    agente_id = st.text_input("Ingresa tu ID de Agente:", key="agente_id_input", disabled=st.session_state.started)

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
                
                # 🎉 EFECTO VISUAL: Nieve al iniciar
                st.snow()
                
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
        
        # 🎉 EFECTO VISUAL: Globos al terminar
        st.balloons()
        
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

        # 1. Limpieza y preparación de datos
        # Asumimos que la columna '% +' (H) es la clave
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
        
        max_percentage = df['% +'].max()
        if max_percentage == 0:
            max_percentage = 1 # Evitar división por cero

        # Usamos st.dataframe con column_config para renderizar la barra de progreso
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
        st.warning(f"Por favor, asegúrate de crear la pestaña y nombrarla exactamente: '{worksheet_name}'.")
    except Exception as e:
        st.error(f"❌ Error al generar el Ranking FCR. ¿Están las columnas correctas?: {e}")


def show_fcr_global_ranking():
    """Consolida datos de todos los turnos, calcula el TOP 10 global y muestra las métricas."""
    
    # Revertido a un Título Estándar
    st.header("👑 TOP 10 Global FCR/CSAT") 
    
    st.markdown("---")
    
    client = get_gsheet_client()
    if not client:
        st.error("❌ No se pudo conectar a Google Sheets para el ranking global.")
        return

    # 1. Definir Hojas a Consolidar
    fcr_sheets = {
        "PM": "Ranking FCR Semanal - PM",
        "AM": "Ranking FCR Semanal - AM",
        "NT1": "Ranking FCR Semanal - NT1",
        "NT2": "Ranking FCR Semanal - NT2",
    }
    
    all_data = []
    
    # 2. Consolidar Datos de Todos los Turnos
    for turno_key, sheet_name in fcr_sheets.items():
        try:
            sheet = client.open_by_key(st.secrets["gsheet_id"])
            results_ws = sheet.worksheet(sheet_name)
            
            df_turno = pd.DataFrame(results_ws.get_all_records())
            
            # Limpiar y convertir columnas clave
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

    # Consolidar todos los DataFrames
    df_consolidado = pd.concat(all_data, ignore_index=True)
    
    # ✅ CORRECCIÓN DEL KEYERROR: Reiniciar el índice
    df_consolidado = df_consolidado.reset_index(drop=True) 
    
    # Asegurar que solo tenemos una entrada por empleado (el mejor resultado)
    df_consolidado = df_consolidado.dropna(subset=['Empleado', 'Total P+N', '% +'])
    
    # Selecciona la fila con el 'Total P+N' máximo para cada 'Empleado'
    df_consolidado = df_consolidado.loc[df_consolidado.groupby('Empleado')['Total P+N'].idxmax()]
    
    # 3. Ordenar el Ranking Global
    # Criterio principal: 'Total P+N' descendente. Criterio secundario (desempate): '% +' descendente
    df_consolidado = df_consolidado.sort_values(
        by=['Total P+N', '% +'], 
        ascending=[False, False]
    ).reset_index(drop=True)

    df_top10 = df_consolidado.head(10).copy()
    
    if df_top10.empty:
        st.info("No hay suficientes datos para generar el TOP 10.")
        return

    # 4. Mostrar el Scoreboard y Mensajes Destacados
    
    st.subheader("🥇 Los Héroes de la Semana")
    
    global_leader = df_top10.iloc[0]
    high_pct_leader = df_top10.loc[df_top10['% +'].idxmax()]
    
    col_trophy, col_msg = st.columns([1, 4])
    
    with col_trophy:
        st.markdown(f"## 🏆")
        st.markdown(f"## 👑")
    
    with col_msg:
        # Mensajes de felicitación
        st.info(
            f"**¡Felicidades, {global_leader['Empleado']}!** se corona como el operador global con el **mayor volumen de satisfacción** ({global_leader['Total P+N']:.0f} Total P+N)."
        )
        st.success(
            f"**{high_pct_leader['Empleado']}** destaca con el **porcentaje positivo más alto** del top ({high_pct_leader['% +']:.2f}%)."
        )
        
        # Lógica para Nota de Desempate (simple)
        desempate_count = df_consolidado['Total P+N'].duplicated(keep='first').sum()
        if desempate_count > 0:
            st.warning(
                f"**Nota Importante:** Los desempates en 'Total P+N' fueron resueltos utilizando el criterio secundario del porcentaje positivo (**% +**)."
            )

    st.markdown("---")
    
    # 6. Visualizar el TOP 10 en tabla
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


# --- FUNCIÓN PRINCIPAL DE LA APP (Mantenida) ---

# Configuración de página con layout extendido
st.set_page_config(page_title="Gincana Contact Center", layout="wide")
st.title("🎯 Plataforma de Productividad del Contact Center")

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


# --- BARRA DE NAVEGACIÓN LATERAL (Mantenida) ---

st.sidebar.title("Menú de Módulos")
st.sidebar.markdown("---")

menu_options = {
    "⌨️ Gincana (Juego) 🛠️": "game",
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

# --- Lógica del Menú Desplegable para FCR Semanal por Turno ---
elif current_module == "fcr_ranking":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Seleccionar Turno FCR")
    
    fcr_sheets = {
        "Turno PM": "Ranking FCR Semanal - PM",
        "Turno AM": "Ranking FCR Semanal - AM",
        "Turno Noche (NT1)": "Ranking FCR Semanal - NT1",
        "Turno Noche (NT2)": "Ranking FCR Semanal - NT2",
    }
    
    turno_selection = st.sidebar.radio(
        "Ver Ranking del Turno:", 
        list(fcr_sheets.keys()),
        index=0
    )
    
    worksheet_name = fcr_sheets[turno_selection]
    show_fcr_ranking(worksheet_name)
    
# --- Lógica para el Ranking Global ---
elif current_module == "fcr_global_ranking":
    show_fcr_global_ranking()
