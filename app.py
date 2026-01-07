import sqlite3
import streamlit as st
from datetime import datetime
import pandas as pd
import altair as alt
import pytz

# =========================================================
# BANCO DE DADOS
# =========================================================
def get_connection():
    return sqlite3.connect("dados.db", check_same_thread=False)

conn = get_connection()
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS registros (
    data TEXT,
    pessoa TEXT,
    habito TEXT,
    feito INTEGER
)
""")
conn.commit()

# =========================================================
# CONFIGURAÇÃO
# =========================================================
st.set_page_config(page_title="Rotina dos Belezinhas", layout="centered")
st.title("Checklist Diário 💙")

# =========================================================
# PESSOA E DATA (FUSO BR + ESTADO CONTROLADO)
# =========================================================
pessoa = st.selectbox("Quem está usando?", ["Daniela", "Henrique"])

fuso_brasil = pytz.timezone("America/Sao_Paulo")
hoje_br = datetime.now(fuso_brasil).date()

# Inicializa data controlada
if "data_atual" not in st.session_state:
    st.session_state.data_atual = hoje_br

# Input controlado
st.date_input(
    "Data",
    value=st.session_state.data_atual,
    key="input_data",
    on_change=lambda: setattr(
        st.session_state,
        "data_atual",
        st.session_state.input_data
    )
)

data_selecionada = st.session_state.data_atual



# =========================================================
# HÁBITOS
# =========================================================
habitos = {
    "Daniela": [
        "Exercício",
        "Beber 3,5L de água",
        "Estudar",
        "Ler",
        "Menos de 1,5h no celular",
        "Sem doce",
        "Hobbie"
    ],
    "Henrique": [
        "Exercício",
        "Ler",
        "Água com limão",
        "Dormir antes da 00:00",
        "Creatina",
        "Vitaminas",
        "Frutas",
        "Tomar sol"
    ]
}

st.subheader(f"Hábitos de {pessoa}")

# =========================================================
# CARREGAR DADOS
# =========================================================
df = pd.read_sql("SELECT * FROM registros", conn)

# =========================================================
# CHECKLIST DO DIA
# =========================================================
df_dia = df[
    (df["pessoa"] == pessoa) &
    (df["data"] == str(data_selecionada))
]

checklist = {}
for habito in habitos[pessoa]:
    valor = df_dia[df_dia["habito"] == habito]["feito"]
    marcado = bool(valor.iloc[0]) if not valor.empty else False
    checklist[habito] = st.checkbox(
    habito,
    value=marcado,
    key=f"{pessoa}_{data_selecionada}_{habito}"
)


# =========================================================
# % DO DIA
# =========================================================
percentual_dia = (sum(checklist.values()) / len(checklist)) * 100
st.metric("📊 % de hábitos concluídos no dia", f"{percentual_dia:.0f}%")

# =========================================================
# CONTROLE DE ATUALIZAÇÃO
# =========================================================
if "atualizar" not in st.session_state:
    st.session_state.atualizar = False

if st.button("🔄 Atualizar gráfico (sem salvar)"):
    st.session_state.atualizar = True

# =========================================================
# SALVAR
# =========================================================
if st.button("💾 Salvar dia"):
    cursor.execute("""
    DELETE FROM registros
    WHERE pessoa = ? AND data = ?
    """, (pessoa, str(data_selecionada)))

    for habito, feito in checklist.items():
        cursor.execute("""
        INSERT INTO registros (data, pessoa, habito, feito)
        VALUES (?, ?, ?, ?)
        """, (str(data_selecionada), pessoa, habito, int(feito)))

    conn.commit()
    st.success("Dia salvo com sucesso! ✅")

# =========================================================
# HISTÓRICO BASE (SALVO OU SIMULADO)
# =========================================================
if df.empty:
    st.info("Ainda não há dados suficientes para gerar gráficos.")
    st.stop()

if st.session_state.atualizar:
    df_hist = df.copy()
    df_hist = df_hist[
        ~(
            (df_hist["pessoa"] == pessoa) &
            (df_hist["data"] == str(data_selecionada))
        )
    ]

    simulados = []
    for habito, feito in checklist.items():
        simulados.append({
            "data": str(data_selecionada),
            "pessoa": pessoa,
            "habito": habito,
            "feito": int(feito)
        })

    df_hist = pd.concat([df_hist, pd.DataFrame(simulados)])
else:
    df_hist = df.copy()

df_hist["data"] = pd.to_datetime(df_hist["data"])

# =========================================================
# AGREGAÇÃO DIÁRIA
# =========================================================
diario = (
    df_hist
    .groupby(["pessoa", "data"])
    .agg(total=("habito", "count"), feitos=("feito", "sum"))
    .reset_index()
)

diario["percentual"] = diario["feitos"] / diario["total"] * 100

# Semana ISO
diario["ano"] = diario["data"].dt.isocalendar().year
diario["semana"] = diario["data"].dt.isocalendar().week
diario["ano_semana"] = (
    diario["ano"].astype(str) + "-S" +
    diario["semana"].astype(str).str.zfill(2)
)

semanas = sorted(diario["ano_semana"].unique())
semana_sel = st.selectbox("Selecione a semana", semanas)

diario_semana = diario[diario["ano_semana"] == semana_sel]

# =========================================================
# ORDEM DOS DIAS
# =========================================================
mapa_dias = {
    0: "Seg", 1: "Ter", 2: "Qua",
    3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"
}
ordem_dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

diario_semana["dia"] = diario_semana["data"].dt.weekday.map(mapa_dias)

# =========================================================
# 📊 GRÁFICO INDIVIDUAL
# =========================================================
st.divider()
st.subheader("📊 Hábitos concluídos por dia (semana)")

base = pd.DataFrame({"dia": ordem_dias})

grafico_ind = base.merge(
    diario_semana[diario_semana["pessoa"] == pessoa][["dia", "percentual"]],
    on="dia",
    how="left"
).fillna(0)

META = 70

barras = alt.Chart(grafico_ind).mark_bar().encode(
    x=alt.X("dia:N", sort=ordem_dias),
    y=alt.Y("percentual:Q", scale=alt.Scale(domain=[0, 100])),
    color=alt.condition(
        alt.datum.percentual >= META,
        alt.value("#2ecc71"),
        alt.value("#e74c3c")
    )
)

textos = alt.Chart(grafico_ind).mark_text(dy=-10).encode(
    x=alt.X("dia:N", sort=ordem_dias),
    y="percentual:Q",
    text=alt.condition(
        "datum.percentual > 0",
        alt.Text("percentual:Q", format=".0f"),
        alt.value("")
    )
)

st.altair_chart(barras + textos, use_container_width=True)

media_semana = grafico_ind["percentual"].mean()

if media_semana >= META:
    st.success(f"🎯 Meta semanal batida! ({media_semana:.0f}%)")
else:
    st.error(f"⚠️ Meta semanal não atingida ({media_semana:.0f}%)")

# =========================================================
# 🟣 COMPARAÇÃO DANIELA X HENRIQUE
# =========================================================
st.divider()
st.subheader("🟣 Comparação semanal – Daniela x Henrique")

base_comp = pd.DataFrame({"dia": ordem_dias})
pessoas = pd.DataFrame({"pessoa": ["Daniela", "Henrique"]})
base_comp["key"] = 1
pessoas["key"] = 1

base_comp = base_comp.merge(pessoas, on="key").drop("key", axis=1)

grafico_comp = base_comp.merge(
    diario_semana[["dia", "pessoa", "percentual"]],
    on=["dia", "pessoa"],
    how="left"
).fillna(0)

barras_comp = alt.Chart(grafico_comp).mark_bar().encode(
    x=alt.X("dia:N", sort=ordem_dias),
    xOffset="pessoa:N",
    y=alt.Y("percentual:Q", scale=alt.Scale(domain=[0, 100])),
    color=alt.Color(
        "pessoa:N",
        scale=alt.Scale(
            domain=["Daniela", "Henrique"],
            range=["#e84393", "#0984e3"]
        ),
        legend=None
    )
)

st.altair_chart(barras_comp, use_container_width=True)

# =========================================================
# 🔥 STREAK
# =========================================================
st.divider()
st.subheader("🔥 Streak de dias bons (≥ 70%)")

def calcular_streak(df_pessoa):
    streak = 0
    for p in df_pessoa.sort_values("data")["percentual"]:
        streak = streak + 1 if p >= META else 0
    return streak

streak_dani = calcular_streak(diario[diario["pessoa"] == "Daniela"])
streak_henri = calcular_streak(diario[diario["pessoa"] == "Henrique"])

c1, c2 = st.columns(2)
with c1:
    st.metric("💗 Daniela", f"{streak_dani} dias")
with c2:
    st.metric("💙 Henrique", f"{streak_henri} dias")
