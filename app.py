import sqlite3
import streamlit as st
from datetime import date, datetime
import pandas as pd
import altair as alt
import pytz

# -----------------------
# Banco de dados
# -----------------------
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

# -----------------------
# Configuração da página
# -----------------------
st.set_page_config(page_title="Rotina do Casal", layout="centered")
st.title("Checklist Diário 💙")

# -----------------------
# Pessoa e data
# -----------------------
pessoa = st.selectbox("Quem está usando?", ["Daniela", "Henrique"])
fuso_brasil = pytz.timezone("America/Sao_Paulo")
hoje_br = datetime.now(fuso_brasil).date()
data_selecionada = st.date_input(
    "Data",
    value=hoje_br
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
# Carregar dados
# -----------------------
df = pd.read_sql("SELECT * FROM registros", conn)

# -----------------------
# Checklist do dia
# -----------------------
df_dia = df[
    (df["pessoa"] == pessoa) &
    (df["data"] == str(data_selecionada))
]

checklist = {}
for habito in habitos[pessoa]:
    valor = df_dia[df_dia["habito"] == habito]["feito"]
    marcado = bool(valor.iloc[0]) if not valor.empty else False
    checklist[habito] = st.checkbox(habito, value=marcado)

# -----------------------
# % do dia
# -----------------------
percentual_dia = (sum(checklist.values()) / len(checklist)) * 100
st.metric("📊 % de hábitos concluídos no dia", f"{percentual_dia:.0f}%")

# -----------------------
# Botão salvar
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
        """, (str(data_selecionada), pessoa, habito, int(feito)))

    conn.commit()
    st.success("Dia salvo com sucesso! ✅")

# -----------------------
# HISTÓRICO / GRÁFICOS
# -----------------------
st.divider()
st.subheader("📊 Hábitos concluídos por dia (semana)")

if df.empty:
    st.info("Ainda não há dados suficientes para gerar gráficos.")
    st.stop()

# Base diária
df["data"] = pd.to_datetime(df["data"])

diario = (
    df.groupby(["pessoa", "data"])
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

diario = diario[diario["ano_semana"] == semana_sel]

# Dia da semana
mapa_dias = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}
ordem_dias = list(mapa_dias.values())

diario["dia"] = diario["data"].dt.weekday.map(mapa_dias)

base = pd.DataFrame({"dia": ordem_dias})
grafico = base.merge(
    diario[diario["pessoa"] == pessoa][["dia", "percentual"]],
    on="dia",
    how="left"
).fillna(0)

# Gráfico
META = 70

barras = alt.Chart(grafico).mark_bar().encode(
    x=alt.X("dia:N", sort=ordem_dias),
    y=alt.Y("percentual:Q", scale=alt.Scale(domain=[0, 100])),
    color=alt.condition(
        alt.datum.percentual >= META,
        alt.value("#2ecc71"),
        alt.value("#e74c3c")
    )
)

textos = alt.Chart(grafico).mark_text(dy=-10).encode(
    x="dia:N",
    y="percentual:Q",
    text=alt.condition(
        "datum.percentual > 0",
        alt.Text("percentual:Q", format=".0f"),
        alt.value("")
    )
)

st.altair_chart(barras + textos, use_container_width=True)

# -----------------------
# Meta semanal
# -----------------------
media_semana = grafico["percentual"].mean()

if media_semana >= META:
    st.success(f"🎯 Meta semanal batida! ({media_semana:.0f}%)")
else:
    st.error(f"⚠️ Meta semanal não atingida ({media_semana:.0f}%)")
