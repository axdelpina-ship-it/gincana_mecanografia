# Entrada del usuario con key para poder resetear
user_input = st.text_input("Tu escritura:", key="user_input")

# Botón Finalizar
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

            # Calcular WPM
            word_count = len(user_input.split())
            wpm = (word_count / elapsed_time) * 60 if elapsed_time > 0 else 0

            # Calcular precisión
            correct_chars = sum(1 for i, c in enumerate(user_input) 
                                if i < len(st.session_state['target_phrase']) and c == st.session_state['target_phrase'][i])
            accuracy = (correct_chars / len(st.session_state['target_phrase'])) * 100

            # Guardar resultado
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

            # Preparar siguiente frase y resetear input
            st.session_state['target_phrase'] = random.choice(phrases)
            st.session_state['start_time'] = None
            st.session_state['user_input'] = ""  # resetea input sin rerun
