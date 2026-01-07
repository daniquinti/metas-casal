import sqlite3
import streamlit as st
from datetime import date
import pandas as pd
import altair as alt

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



st.set_page_config(page_title="Rotina do Casal", layout="centered")
st.title("Checklist Diário 💙")

# -----------------------
# Pessoas
# -----------------------
pessoa = st.selectbox(
    "Quem está usando?",
    ["Daniela", "Henrique"]
)

# -----------------------
# Data
# -----------------------
data_selecionada = st.date_input(
    "Data",
    value=date.today()
)

# -----------------------
# Hábitos fixos
# -----------------------
habitos = {
    "Daniela": [
        "Exercício",
        "Beber 3,5L de água",
        "Estudar",
        "Ler",
        "Menos de 1,5h no celular"
    ],
    "Henrique": [
        "Exercício",
        "Ler",
        "Água com limão",
        "Dormir antes da 00:00"
    ]
}

st.subheader(f"Hábitos de {pessoa}")

# -----------------------
# Arquivo de dados
# -----------------------


df = pd.read_sql("SELECT * FROM registros", conn)


# -----------------------
# Filtrar dados do dia
# -----------------------
df_dia = df[
    (df["pessoa"] == pessoa) &
    (df["data"] == str(data_selecionada))
]

# -----------------------
# Checklist (com carga)
# -----------------------
checklist = {}

for habito in habitos[pessoa]:
    valor_salvo = df_dia[df_dia["habito"] == habito]["feito"]

    marcado = bool(valor_salvo.iloc[0]) if not valor_salvo.empty else False

    checklist[habito] = st.checkbox(habito, value=marcado)

if "atualizar" not in st.session_state:
    st.session_state.atualizar = False

if st.button("🔄 Atualizar gráfico (sem salvar)"):
    st.session_state.atualizar = True



# -----------------------
# Indicador: % do dia
# -----------------------
total_habitos = len(checklist)
habitos_feitos = sum(checklist.values())

if total_habitos > 0:
    percentual = (habitos_feitos / total_habitos) * 100
else:
    percentual = 0

st.metric(
    label="📊 % de hábitos concluídos no dia",
    value=f"{percentual:.0f}%"
)

import altair as alt

# -----------------------
# Histórico diário (colunas por semana)
# -----------------------
st.subheader("📊 Hábitos concluídos por dia (semana)")

if st.session_state.atualizar:
    # Usa os dados da TELA para o dia atual
    df_temp = df.copy()

    # Remove registros desse dia/pessoa
    df_temp = df_temp[
        ~(
            (df_temp["pessoa"] == pessoa) &
            (df_temp["data"] == str(data_selecionada))
        )
    ]

    # Adiciona dados da tela
    novos = []
    for habito, feito in checklist.items():
        novos.append({
            "data": str(data_selecionada),
            "pessoa": pessoa,
            "habito": habito,
            "feito": 1 if feito else 0
        })

    df_temp = pd.concat([df_temp, pd.DataFrame(novos)], ignore_index=True)

    df_hist = df_temp[df_temp["pessoa"] == pessoa]

else:
    # Usa somente dados salvos
    df_hist = df[df["pessoa"] == pessoa]



if not df_hist.empty:
    df_hist["data"] = pd.to_datetime(df_hist["data"])

    # % por dia
    diario = (
        df_hist
        .groupby("data")
        .agg(
            total_habitos=("habito", "count"),
            feitos=("feito", "sum")
        )
        .reset_index()
    )

    diario["percentual"] = (
        diario["feitos"] / diario["total_habitos"] * 100
    )

    # Ano e semana ISO
    diario["ano"] = diario["data"].dt.isocalendar().year
    diario["semana"] = diario["data"].dt.isocalendar().week

    diario["ano_semana"] = (
        diario["ano"].astype(str)
        + "-S"
        + diario["semana"].astype(str).str.zfill(2)
    )

    # Selector de semana
    semanas = sorted(diario["ano_semana"].unique())
    semana_sel = st.selectbox(
        "Selecione a semana",
        semanas,
        index=len(semanas) - 1
    )

    diario_semana = diario[diario["ano_semana"] == semana_sel]

    # Ordem correta dos dias
    ordem_dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    mapa_dias = {
        0: "Seg", 1: "Ter", 2: "Qua",
        3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"
    }

    diario_semana["dia"] = diario_semana["data"].dt.weekday.map(mapa_dias)

    base_semana = pd.DataFrame({"dia": ordem_dias})

    grafico = base_semana.merge(
        diario_semana[["dia", "percentual"]],
        on="dia",
        how="left"
    ).fillna(0)

    # Gráfico de barras
    META_SEMANAL = 70

    barras = alt.Chart(grafico).mark_bar().encode(
        x=alt.X("dia:N", sort=ordem_dias, title="Dia da semana"),
        y=alt.Y(
            "percentual:Q",
            scale=alt.Scale(domain=[0, 100]),
            title="% de hábitos concluídos"
        ),
        color=alt.condition(
            alt.datum.percentual >= META_SEMANAL,
            alt.value("#2ecc71"),  # verde
            alt.value("#e74c3c")   # vermelho
        )
    )


    # Rótulos (somente > 0)
    textos = alt.Chart(grafico).mark_text(
        dy=-10,
        fontSize=12
    ).encode(
        x=alt.X("dia:N", sort=ordem_dias),
        y="percentual:Q",
        text=alt.condition(
            "datum.percentual > 0",
            alt.Text("percentual:Q", format=".0f"),
            alt.value("")
        )
    )

    st.altair_chart(barras + textos, use_container_width=True)

else:
    st.info("Ainda não há dados suficientes para gerar o gráfico.")

# -----------------------
# Meta semanal
# -----------------------
META_SEMANAL = 70  # % desejada

media_semana = grafico["percentual"].mean()

if media_semana >= META_SEMANAL:
    st.success(f"🎯 Meta semanal batida! ({media_semana:.0f}%)")
else:
    st.error(f"⚠️ Meta semanal não atingida ({media_semana:.0f}%)")

# Dani x Henrique
# --------------------------

st.subheader("🟣 Comparação semanal – Daniela x Henrique")

# Base completa
df_comp = df.copy()
df_comp["data"] = pd.to_datetime(df_comp["data"])

# % por dia e pessoa
diario_comp = (
    df_comp
    .groupby(["pessoa", "data"])
    .agg(
        total_habitos=("habito", "count"),
        feitos=("feito", "sum")
    )
    .reset_index()
)

diario_comp["percentual"] = (
    diario_comp["feitos"] / diario_comp["total_habitos"] * 100
)

# Semana ISO
diario_comp["ano"] = diario_comp["data"].dt.isocalendar().year
diario_comp["semana"] = diario_comp["data"].dt.isocalendar().week

diario_comp["ano_semana"] = (
    diario_comp["ano"].astype(str)
    + "-S"
    + diario_comp["semana"].astype(str).str.zfill(2)
)

# Filtrar semana selecionada
diario_comp = diario_comp[diario_comp["ano_semana"] == semana_sel]

# Mapear dia da semana
mapa_dias = {
    0: "Seg", 1: "Ter", 2: "Qua",
    3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"
}
ordem_dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

diario_comp["dia"] = diario_comp["data"].dt.weekday.map(mapa_dias)

# Base fixa para garantir todos os dias
base = pd.DataFrame({
    "dia": ordem_dias,
    "key": 1
})

pessoas = pd.DataFrame({
    "pessoa": ["Daniela", "Henrique"],
    "key": 1
})

base_completa = base.merge(pessoas, on="key").drop("key", axis=1)

grafico_comp = base_completa.merge(
    diario_comp[["dia", "pessoa", "percentual"]],
    on=["dia", "pessoa"],
    how="left"
).fillna(0)

# Gráfico de colunas agrupadas
barras_comp = alt.Chart(grafico_comp).mark_bar().encode(
    x=alt.X("dia:N", sort=ordem_dias, title="Dia da semana"),
    xOffset="pessoa:N",
    y=alt.Y(
        "percentual:Q",
        scale=alt.Scale(domain=[0, 100]),
        title="% de hábitos concluídos"
    ),
    color=alt.Color(
        "pessoa:N",
        scale=alt.Scale(
            domain=["Daniela", "Henrique"],
            range=["#e84393", "#0984e3"]  # rosa / azul
        ),
        legend=alt.Legend(title="")
    )
)

st.altair_chart(barras_comp, use_container_width=True)

# Streak de dias bons
# ------------------------
st.subheader("🔥 Streak de dias bons (≥ 70%)")

LIMIAR_STREAK = 70

def calcular_streak(df_diario):
    df_diario = df_diario.sort_values("data")

    streak = 0
    for perc in df_diario["percentual"]:
        if perc >= LIMIAR_STREAK:
            streak += 1
        else:
            streak = 0
    return streak


# Base diária para TODOS
df_streak = df.copy()
df_streak["data"] = pd.to_datetime(df_streak["data"])

diario_streak = (
    df_streak
    .groupby(["pessoa", "data"])
    .agg(
        total_habitos=("habito", "count"),
        feitos=("feito", "sum")
    )
    .reset_index()
)

diario_streak["percentual"] = (
    diario_streak["feitos"] / diario_streak["total_habitos"] * 100
)

# Calcular streak por pessoa
streak_daniela = calcular_streak(
    diario_streak[diario_streak["pessoa"] == "Daniela"]
)

streak_henrique = calcular_streak(
    diario_streak[diario_streak["pessoa"] == "Henrique"]
)

# Exibir
col1, col2 = st.columns(2)

with col1:
    st.metric(
        label="💗 Daniela",
        value=f"{streak_daniela} dias"
    )

with col2:
    st.metric(
        label="💙 Henrique",
        value=f"{streak_henrique} dias"
    )





# -----------------------
# Salvar
# -----------------------
if st.button("💾 Salvar dia"):
    cursor.execute("""
    DELETE FROM registros
    WHERE pessoa = ? AND data = ?
    """, (pessoa, str(data_selecionada)))

    for habito, feito in checklist.items():
        cursor.execute("""
        INSERT INTO registros (data, pessoa, habito, feito)
        VALUES (?, ?, ?, ?)
        """, (str(data_selecionada), pessoa, habito, 1 if feito else 0))

    conn.commit()

    st.success("Dia salvo com sucesso! ✅")

