import streamlit as st
import pandas as pd

st.title("📞 Lead Flow - Versión simple")

uploaded_file = st.file_uploader("Sube tu Excel", type=["xlsx"])

if uploaded_file is None:
    st.stop()

df = pd.read_excel(uploaded_file)

# Renombrar columnas clave
df = df.rename(columns={
    "Negocio - ID": "lead_id",
    "Actividad - Hora en que se marcó como completada": "fecha",
    "Negocio - Propietario": "agent",
    "Actividad - Tipo": "tipo"
})

df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

# Clasificación simple
def clasificar(tipo):
    if tipo == "Whatsapp chat":
        return "whatsapp"
    else:
        return "call"

df["tipo_simple"] = df["tipo"].apply(clasificar)

df = df.sort_values(["lead_id", "fecha"])

# 🔥 FUNNEL SIMPLE
def evaluar_lead(group):
    tipos = group["tipo_simple"].tolist()

    result = {
        "call_1": False,
        "wpp_1": False,
        "call_2": False,
        "call_3": False,
        "wpp_2": False,
        "call_4": False,
        "wpp_3": False,
    }

    flow = ["call", "whatsapp", "call", "call", "whatsapp", "call", "whatsapp"]

    i = 0
    for t in tipos:
        if i >= len(flow):
            break
        if t == flow[i]:
            key = list(result.keys())[i]
            result[key] = True
            i += 1

    result["lost_correctly"] = all(result.values())

    return result

# Agrupar por lead
rows = []
for lead_id, group in df.groupby("lead_id"):
    r = evaluar_lead(group)
    r["lead_id"] = lead_id
    r["agent"] = group["agent"].iloc[0]
    rows.append(r)

funnel_df = pd.DataFrame(rows)

# Resumen por agente
resumen = funnel_df.groupby("agent").mean() * 100

# UI
agente = st.selectbox("Selecciona agente", resumen.index)

st.subheader(f"Resultados - {agente}")

data = resumen.loc[agente].to_frame(name="Porcentaje")
data.index.name = "Paso"

st.dataframe(data)

st.subheader("Leads procesados")
st.write(len(funnel_df))

st.subheader("Leads correctos")
st.write(int(funnel_df["lost_correctly"].sum()))
