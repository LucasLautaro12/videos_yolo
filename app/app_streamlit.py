import streamlit as st
from pathlib import Path
from app.config import UPLOAD_DIR, PROCESSED_DIR, YOLO_CLASSES, PAGE_TITLE, LOGO_PATH, ALLOWED_VIDEO_TYPES
from app.processing.processing import ejecutar_procesamiento
from app.utils.utils import asegurar_video_web, obtener_duracion_formato

# ==============================================================================
# COMPONENTES DE LA INTERFAZ DE USUARIO (Funciones de Streamlit)
# ==============================================================================

def aplicar_estilos_css():
    """Aplica todo el CSS custom para dar estilo a la aplicación."""
    st.markdown("""
        <style>
            .block-container { padding-top: 2rem; }
            .stApp { background-color: #00050a; color: #E0E0E0; }
            .logo-container { display: flex; justify-content: center; margin-bottom: 1.5rem; }
            header[data-testid="stHeader"] { background-color: #1c262e; }
            header[data-testid="stHeader"] button { color: #E0E0E0; }
            h1 a, h2 a, h3 a { display: none !important; }
            .stMarkdown label, .stSelectbox label, .stMultiSelect label { color: #FFFFFF !important; font-weight: 600; }

            /* File Uploader */
            .stFileUploader {
                border: 2px dashed #444444; background-color: #1E1E1E;
                border-radius: 12px; padding: 25px; text-align: center;
                transition: border-color 0.3s ease;
            }
            .stFileUploader:hover { border-color: #00BFFF; }
            .stFileUploader label { color: #3c5263; font-size: 1.5rem; }
            .stFileUploader button {
                background-color: #333333; color: #FFFFFF;
                border-radius: 8px; border: 1px solid #555555; font-weight: 600;
            }
            .stFileUploader button:hover { background-color: #444444; border-color: #00BFFF; }

            /* Multiselect */
            div[data-baseweb="select"] > div { border: none !important; border-radius: 10px !important; }
            div[data-baseweb="select"] span {
                background-color: white !important;
                color: black !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 4px 8px !important;
                margin: 2px !important;
                font-size: 14px !important;
                line-height: 18px !important;
                max-width: 120px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: normal !important;
                word-break: break-word !important;
                max-width: 200px;
            }

            /* Nombre del archivo en el uploader */
            .stFileUploaderFileName, 
            .stFileUploader .st-emotion-cache, 
            .st-emotion-cache-1rpn56r {
                color: white !important;   /* o #E0E0E0 para gris claro */
            }


            /* Botones Principales (Procesar / Descargar) */
            div.stButton > button:first-child, .stDownloadButton button {
                background-color: #F5F5F5; color: black; border-radius: 10px;
                padding: 0.8rem 2rem; border: 1px solid #424242; width: 100%;
                max-width: 400px; font-weight: 600; height: 3rem;
                transition: all 0.2s ease-in-out;
            }
            div.stButton > button:first-child:hover, .stDownloadButton button:hover {
                background-color: #E0E0E0; border-color: #FFFFFF; color: black;
            }
        </style>
    """, unsafe_allow_html=True)

def mostrar_header():
    """Muestra el encabezado de la aplicación con el logo y los títulos."""
    with st.container():
        st.markdown('<div class="logo-container">', unsafe_allow_html=True)
        if LOGO_PATH.exists():
            col1, col2, col3 = st.columns([1.5,2,1.5])
            with col2:
                st.image(str(LOGO_PATH), width=350)
        else:
            st.error(f"No se encontró el logo '{LOGO_PATH.name}'. Verifique que esté en la carpeta correcta.")
            st.markdown("<h1 style='text-align: center;'>Ministerio Público de la Acusación</h1>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<h3 style='text-align: center; margin-top: 0; margin-bottom: 20px; font-size:24px;'> Procesamiento Inteligente de Videos 🎥</h3>", unsafe_allow_html=True)

def manejar_subida_video():
    """Gestiona el componente de subida de archivos y el guardado del video."""
    video_file = st.file_uploader(
        "Arrastrá o subí un video",
        type=ALLOWED_VIDEO_TYPES,
        label_visibility="collapsed"
    )
    if video_file:
        save_path = UPLOAD_DIR / video_file.name
        with open(save_path, "wb") as f:
            f.write(video_file.getbuffer())
        st.session_state['video_cargado'] = save_path
        st.success("✅ Video cargado correctamente")
        st.video(str(save_path))

def mostrar_resultados(ruta_video_procesado: Path):
    """Muestra el video procesado y el botón de descarga."""
    st.success("✅ Procesamiento completado.")
    st.video(str(ruta_video_procesado))

    with open(ruta_video_procesado, "rb") as f:
        st.download_button(
            label="⬇️ Descargar el video",
            data=f,
            file_name=ruta_video_procesado.name,
            mime="video/mp4"
        )

# ==============================================================================
# FLUJO PRINCIPAL DE LA APLICACIÓN
# ==============================================================================

def main():
    """Función principal que ejecuta la aplicación de Streamlit."""
    st.set_page_config(page_title=PAGE_TITLE, layout="centered")
    aplicar_estilos_css()
    mostrar_header()

    # --- Selección de objetos YOLO ---
    opciones = st.multiselect(
        "Selecciona qué objetos detectar:*",
        ["todos"] + YOLO_CLASSES,
        default=[],
        placeholder="Elegí una o varias opciones"
    )

    # --- Sección de Carga de Video ---
    manejar_subida_video()

    # --- Sección de Procesamiento (solo si hay un video cargado) ---
    if 'video_cargado' in st.session_state:
        video_original_path = st.session_state.video_cargado

        if st.button("Procesar el video"):
            if not opciones:
                st.error("⚠️ Debes seleccionar al menos un objeto a detectar para continuar.")
            else:
                st.session_state['video_procesado'] = None
                with st.spinner("Procesando video... Esto puede tardar unos minutos."):
                    try:
                        _, duracion_min = obtener_duracion_formato(str(video_original_path))
                        output_path = PROCESSED_DIR / f"procesado_{video_original_path.name}"

                        if "todos" in opciones:
                            target_classes = None  # None = todas las clases
                        else:
                            from app.config import YOLO_MAP
                            target_classes = [YOLO_MAP[x] for x in opciones]

                        final_path_str, _ = ejecutar_procesamiento(
                            str(video_original_path),
                            str(output_path),
                            duracion_min=duracion_min,
                            target_classes=target_classes,
                            forzar_todas=False
                        )

                        final_path = Path(final_path_str)
                        final_web_path = asegurar_video_web(final_path)

                        if final_web_path:
                            # 🧹 borrar el original para que no quede duplicado
                            if final_path.exists():
                                final_path.unlink()
                            st.session_state['video_procesado'] = final_web_path

                    except Exception as e:
                        st.error(f"❌ Error al procesar: {e}")

    # --- Sección de Resultados (solo si un video fue procesado exitosamente) ---
    if 'video_procesado' in st.session_state and st.session_state.video_procesado:
        mostrar_resultados(st.session_state.video_procesado)


if __name__ == "__main__":
    main()