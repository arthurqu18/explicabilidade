import json
import os
import pandas as pd
import streamlit as st
import math

# Configuração da página para modo largo (ideal para comparar A e B lado a lado)
st.set_page_config(
    page_title="Avaliação Clínica de Explicações (XAI)", layout="wide"
)

# Arquivos de dados e resultados, relativos ao diretório deste app
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "respostas", "casos_respostas.json")
RESULTS_FILE = os.path.join(APP_DIR, "avaliacoes_medicas.csv")

TOTAL_POPULACAO = 193  # N total de casos no dataset de discordância
EPSILON_MOE = 0.05  # Limiar da Margem de Erro (epsilon) desejado
MIN_SAMPLES = 30  # Mínimo de amostras para o Teorema do Limite Central
Z_CRITICAL = 1.96  # Valor z para 95% de confiança (alpha = 0.05)


# Carrega os casos salvos em JSON
@st.cache_data
def carregar_casos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


casos = carregar_casos()

# Inicializa o estado da sessão
if "current_index" not in st.session_state:
    st.session_state.current_index = 0

# --- BARRA LATERAL (IDENTIFICAÇÃO DO ESPECIALISTA) ---
st.sidebar.title("👨‍⚕️ Identificação")
medico_id = st.sidebar.text_input(
    "Nome ou ID/CRM do Especialista:",
    value="",
    placeholder="Ex: Ana / CRM-12345",
)

if not medico_id.strip():
    st.warning(
        "⚠️ Por favor, insira seu nome ou ID na barra lateral esquerda para começar a avaliação."
    )
    st.stop()

if not casos:
    st.error(f"Arquivo '{DATA_FILE}' não encontrado ou vazio.")
    st.stop()

total_casos_disponiveis = len(casos)
idx = st.session_state.current_index
caso_atual = casos[idx]


# --- FUNÇÃO ESTATÍSTICA (MERLO ET AL., 2025) ---
def calcular_estatisticas_moe(medico_id_str):
    """Calcula o MAE, Variância e MoE com Fator de Correção de População Finita (FPC)"""
    if not os.path.exists(RESULTS_FILE):
        return None

    df = pd.read_csv(RESULTS_FILE)
    df_medico = df[df["especialista_id"].astype(str) == str(medico_id_str)]

    n = len(df_medico)
    if n < MIN_SAMPLES:
        return {"n": n, "pronto": False}

    # Erros absolutos em relação à nota ideal (3)
    erros_A = 3 - df_medico["nota_A"]
    erros_B = 3 - df_medico["nota_B"]

    mae_A = erros_A.mean()
    mae_B = erros_B.mean()

    var_A = erros_A.var(ddof=1) if n > 1 else 0
    var_B = erros_B.var(ddof=1) if n > 1 else 0

    # Fator de Correção de População Finita (FPC)
    fpc = math.sqrt((TOTAL_POPULACAO - n) / (TOTAL_POPULACAO - 1))

    # Margem de erro (MoE) para cada grupo
    moe_A = Z_CRITICAL * (math.sqrt(var_A / n)) * fpc
    moe_B = Z_CRITICAL * (math.sqrt(var_B / n)) * fpc

    # O critério de parada é satisfeito se ambos os grupos atingirem MoE <= EPSILON
    atingiu_criterio = (moe_A <= EPSILON_MOE) and (moe_B <= EPSILON_MOE)

    return {
        "n": n,
        "mae_A": mae_A,
        "moe_A": moe_A,
        "mae_B": mae_B,
        "moe_B": moe_B,
        "pronto": atingiu_criterio,
    }


# --- PAINEL ESTATÍSTICO NA SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Status Estatístico (Confidence-based)")
stats = calcular_estatisticas_moe(medico_id.strip())

if stats and stats["n"] >= MIN_SAMPLES:
    st.sidebar.metric(
        "Amostras Avaliadas", f"{stats['n']} / {TOTAL_POPULACAO}"
    )
    st.sidebar.write(
        f"**Grupo A (MAE):** {stats['mae_A']:.3f} (±{stats['moe_A']:.3f})"
    )
    st.sidebar.write(
        f"**Grupo B (MAE):** {stats['mae_B']:.3f} (±{stats['moe_B']:.3f})"
    )

    if stats["pronto"]:
        st.sidebar.success(f"🎯 Margem de erro <= {EPSILON_MOE} atingida!")
    else:
        st.sidebar.info(f"⏳ Buscando MoE <= {EPSILON_MOE}...")
else:
    qtd_n = stats["n"] if stats else 0
    st.sidebar.info(
        f"Avaliando amostra inicial: {qtd_n}/{MIN_SAMPLES} casos mínimos para ativar cálculo de MoE."
    )


# --- CABEÇALHO E PROGRESSO ---
st.title("🩺 Avaliação de Narrativas Clínicas (IA)")
st.progress((idx + 1) / total_casos_disponiveis)
st.caption(
    f"Avaliador: **{medico_id}** | Caso {idx + 1} de {total_casos_disponiveis} | ID do Paciente: {caso_atual['caso_id']}"
)

# Alerta caso o critério de confiança estatística já tenha sido atingido
if stats and stats["pronto"]:
    st.success(
        f"🎉 **Parabéns!** A amostra atual ({stats['n']} casos) já atingiu o nível de confiança estatística desejado (MoE ≤ {EPSILON_MOE}). Você pode continuar avaliando ou encerrar por aqui!"
    )

st.markdown("---")

# --- GUIA DE PONTUAÇÃO ---
with st.expander("📌 Critérios de Pontuação (0 a 3)"):
    st.markdown("""
    * **0 (Incoerente):** A narrativa alucina, erra dados do SHAP/SHAP-IQ ou apoia-se em premissas clinicamente absurdas.[cite: 2]
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
        key=f"nota_a_{idx}_{medico_id}",
        horizontal=True,
    )

with col_b:
    st.subheader("Conjunto B (SHAP + Predição)")
    st.success(caso_atual["narrativa_B"])
    nota_b = st.radio(
        "Nota para o Conjunto B:",
        options=[0, 1, 2, 3],
        key=f"nota_b_{idx}_{medico_id}",
        horizontal=True,
    )

st.markdown("---")


# --- SALVAMENTO E NAVEGAÇÃO ---
def salvar_e_avancar():
    novo_resultado = {
        "especialista_id": medico_id.strip(),
        "caso_id": caso_atual["caso_id"],
        "nota_A": st.session_state[f"nota_a_{idx}_{medico_id}"],
        "nota_B": st.session_state[f"nota_b_{idx}_{medico_id}"],
    }

    df_novo = pd.DataFrame([novo_resultado])

    if os.path.exists(RESULTS_FILE):
        df_existente = pd.read_csv(RESULTS_FILE)

        mascara_mesmo_registro = (
            (
                df_existente["especialista_id"].astype(str)
                == str(medico_id.strip())
            )
            & (df_existente["caso_id"] == caso_atual["caso_id"])
        )
        df_existente = df_existente[~mascara_mesmo_registro]
        df_final = pd.concat([df_existente, df_novo], ignore_index=True)
    else:
        df_final = df_novo

    df_final.to_csv(RESULTS_FILE, index=False)

    if st.session_state.current_index < total_casos_disponiveis - 1:
        st.session_state.current_index += 1


col_voltar, col_espaco, col_avancar = st.columns([1, 4, 1])

with col_voltar:
    if st.button("⬅️ Anterior") and st.session_state.current_index > 0:
        st.session_state.current_index -= 1
        st.rerun()

with col_avancar:
    if st.session_state.current_index < total_casos_disponiveis - 1:
        st.button("Próximo ➡️", on_click=salvar_e_avancar)
    else:
        if st.button("💾 Finalizar Avaliação"):
            salvar_e_avancar()
            st.balloons()
            st.success(
                f"Avaliação do especialista '{medico_id}' concluída!."
            )