import json
import os
import pandas as pd
import streamlit as st

# Configuração da página para modo largo (ideal para comparar A e B lado a lado)
st.set_page_config(
    page_title="Avaliação Clínica de Explicações (XAI)", layout="wide"
)

# Arquivos de dados e resultados, relativos ao diretório deste app
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "respostas", "casos_respostas.json")
RESULTS_FILE = os.path.join(APP_DIR, "avaliacoes_medicas.csv")


# Carrega os casos salvos
@st.cache_data
def carregar_casos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


casos = carregar_casos()

# Inicializa o estado da sessão (navegação)
if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if not casos:
    st.error(f"Arquivo '{DATA_FILE}' não encontrado ou vazio.")
    st.stop()

total_casos = len(casos)
idx = st.session_state.current_index
caso_atual = casos[idx]

# --- CABEÇALHO E PROGRESSO ---
st.title("🩺 Avaliação de Narrativas Clínicas (IA)")
st.progress((idx + 1) / total_casos)
st.caption(
    f"Caso {idx + 1} de {total_casos} | ID do Paciente: {caso_atual['caso_id']}"
)

st.markdown("---")

# --- GUIA DE PONTUAÇÃO (EXPANSÍVEL) ---
with st.expander("📌 Critérios de Pontuação (0 a 3)"):
    st.markdown("""
    * **0 (Incoerente):** A narrativa alucina, erra dados do SHAP ou apoia-se em premissas clinicamente absurdas.
    * **1 (Fraca):** Traduz o SHAP, mas falha em conectar os achados com a gravidade do paciente.[cite: 2]
    * **2 (Boa):** Explica corretamente as atribuições de risco do SHAP e mantém coerência fisiológica.[cite: 2]
    * **3 (Excelente):** Identifica perfeitamente a dinâmica clínica (ex: detecta outliers ou integra múltiplos marcadores).[cite: 2]
    """)

# --- COMPARAÇÃO LADO A LADO ---
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Conjunto A (Apenas SHAP)")
    st.info(caso_atual["narrativa_A"])
    nota_a = st.radio(
        "Nota para o Conjunto A:",
        options=[0, 1, 2, 3],
        key=f"nota_a_{idx}",
        horizontal=True,
    )

with col_b:
    st.subheader("Conjunto B (SHAP + Predição)")
    st.success(caso_atual["narrativa_B"])
    nota_b = st.radio(
        "Nota para o Conjunto B:",
        options=[0, 1, 2, 3],
        key=f"nota_b_{idx}",
        horizontal=True,
    )

st.markdown("---")


# --- SALVAMENTO E NAVEGAÇÃO ---
def salvar_e_avancar():
    # Estrutura do resultado
    novo_resultado = {
        "caso_id": caso_atual["caso_id"],
        "nota_A": st.session_state[f"nota_a_{idx}"],
        "nota_B": st.session_state[f"nota_b_{idx}"],
    }

    # Salva em CSV
    df_novo = pd.DataFrame([novo_resultado])
    if os.path.exists(RESULTS_FILE):
        df_existente = pd.read_csv(RESULTS_FILE)
        # Remove se já existia avaliação para o mesmo caso_id (sobrescreve)
        df_existente = df_existente[
            df_existente["caso_id"] != caso_atual["caso_id"]
        ]
        df_final = pd.concat([df_existente, df_novo], ignore_index=True)
    else:
        df_final = df_novo

    df_final.to_csv(RESULTS_FILE, index=False)

    # Avança para o próximo caso
    if st.session_state.current_index < total_casos - 1:
        st.session_state.current_index += 1


col_voltar, col_espaco, col_avancar = st.columns([1, 4, 1])

with col_voltar:
    if st.button("⬅️ Anterior") and st.session_state.current_index > 0:
        st.session_state.current_index -= 1
        st.rerun()

with col_avancar:
    if st.session_state.current_index < total_casos - 1:
        st.button("Próximo ➡️", on_click=salvar_e_avancar)
    else:
        if st.button("💾 Finalizar Avaliação"):
            salvar_e_avancar()
            st.balloons()
            st.success(
                f"Avaliação concluída! Resultados salvos em `{RESULTS_FILE}`."
            )