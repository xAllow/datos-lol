import streamlit as st

# Configuración de la página (Debe ser el primer comando de Streamlit)
st.set_page_config(page_title="Panel de Vida", page_icon="📊", layout="wide")

# Importar las pestañas modulares
from steps_tab import render_steps_tab
from lol_tab import render_lol_tab
from registro_tab import render_registro_tab
from finanzas_tab import render_finanzas_tab


def main() -> None:
    st.title("📊 Mi panel de vida")
    st.markdown("Un lugar para ver pasos, LoL y más métricas personales en pestañas separadas.")

    tab_pasos, tab_lol, tab_registro, tab_finanzas = st.tabs(
        ["🚶 Pasos", "🎮 LoL", "📋 Registro", "💳 Finanzas"]
    )

    with tab_pasos:
        render_steps_tab()

    with tab_lol:
        render_lol_tab()

    with tab_registro:
        render_registro_tab()

    with tab_finanzas:
        render_finanzas_tab()



if __name__ == "__main__":
    main()