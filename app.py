import streamlit as st
import pandas as pd

st.set_page_config(page_title="Flujo de Leads Perdidos", layout="wide")

CALL_TYPES = {
    "Lead pendiente de llamar",
    "Llamada informativa",
    "Llamada de seguimiento",
    "Llamada comprometida",
}

WHATSAPP_TYPES = {
    "Whatsapp chat",
}


def classify_activity(value):
    if pd.isna(value):
        return "other"
    value = str(value).strip()
    if value in CALL_TYPES:
        return "call"
    if value in WHATSAPP_TYPES:
        return "whatsapp"
    return "other"


def minutes_between(a, b):
    return (b - a).total_seconds() / 60.0


def hours_between(a, b):
    return (b - a).total_seconds() / 3600.0


def pct(s):
    if len(s) == 0:
        return 0.0
    return round(s.mean() * 100, 1)


def get_next(df, start_time, activity_group):
    x = df[
        (df["activity_group"] == activity_group)
        & (df["activity_completed_at"] >= start_time)
    ].sort_values("activity_completed_at")
    if x.empty:
        return None
    return x.iloc[0]


def evaluate_lead_sequence_only(group):
    group = group.sort_values("activity_completed_at").copy()

    result = {
        "lead_id": group["lead_id"].iloc[0],
        "agent": group["agent"].iloc[0],
        "call_1_ok": False,
        "whatsapp_1_ok": False,
        "call_2_ok": False,
        "call_3_ok": False,
        "whatsapp_2_ok": False,
        "call_4_ok": False,
        "whatsapp_3_ok": False,
        "full_flow_ok": False,
        "fail_step": "",
    }

    activities = group["activity_group"].tolist()
    expected = ["call", "whatsapp", "call", "call", "whatsapp", "call", "whatsapp"]
    keys = [
        "call_1_ok",
        "whatsapp_1_ok",
        "call_2_ok",
        "call_3_ok",
        "whatsapp_2_ok",
        "call_4_ok",
        "whatsapp_3_ok",
    ]

    idx = 0
    for a in activities:
        if idx >= len(expected):
            break
        if a == expected[idx]:
            result[keys[idx]] = True
            idx += 1

    result["full_flow_ok"] = all(result[k] for k in keys)

    if result["full_flow_ok"]:
        result["fail_step"] = "Cumple todo"
    else:
        for k, label in zip(keys, [
            "Sin llamada 1",
            "Sin WhatsApp 1",
            "Sin llamada 2",
            "Sin llamada 3",
            "Sin WhatsApp 2",
            "Sin llamada 4",
            "Sin WhatsApp 3",
        ]):
            if not result[k]:
                result["fail_step"] = label
                break

    return result


def in_window(value, target, tolerance):
    return (target - tolerance) <= value <= (target + tolerance)


def evaluate_lead_with_time(group, immediate_max_min, tol_90_min, tol_half_day_h, tol_day_half_h):
    group = group.sort_values("activity_completed_at").copy()

    lead_id = group["lead_id"].iloc[0]
    agent = group["agent"].iloc[0]
    created_at = group["lead_created_at"].iloc[0]

    result = {
        "lead_id": lead_id,
        "agent": agent,
        "call_1_ok": False,
        "whatsapp_1_ok": False,
        "call_2_ok": False,
        "call_3_ok": False,
        "whatsapp_2_ok": False,
        "call_4_ok": False,
        "whatsapp_3_ok": False,
        "full_flow_ok": False,
        "fail_step": "",
    }

    call_1 = get_next(group, created_at, "call")
    if call_1 is None:
        result["fail_step"] = "Sin llamada 1"
        return result
    if minutes_between(created_at, call_1["activity_completed_at"]) > 5:
        result["fail_step"] = "Llamada 1 fuera de 5 min"
        return result
    result["call_1_ok"] = True

    w1 = get_next(group, call_1["activity_completed_at"], "whatsapp")
    if w1 is None:
        result["fail_step"] = "Sin WhatsApp 1"
        return result
    if not (0 <= minutes_between(call_1["activity_completed_at"], w1["activity_completed_at"]) <= immediate_max_min):
        result["fail_step"] = "WhatsApp 1 no inmediato"
        return result
    result["whatsapp_1_ok"] = True

    c2 = get_next(group, w1["activity_completed_at"], "call")
    if c2 is None:
        result["fail_step"] = "Sin llamada 2"
        return result
    if not in_window(minutes_between(w1["activity_completed_at"], c2["activity_completed_at"]), 90, tol_90_min):
        result["fail_step"] = "Llamada 2 fuera de ventana"
        return result
    result["call_2_ok"] = True

    c3 = get_next(group, c2["activity_completed_at"], "call")
    if c3 is None:
        result["fail_step"] = "Sin llamada 3"
        return result
    if not in_window(hours_between(c2["activity_completed_at"], c3["activity_completed_at"]), 12, tol_half_day_h):
        result["fail_step"] = "Llamada 3 fuera de ventana"
        return result
    result["call_3_ok"] = True

    w2 = get_next(group, c3["activity_completed_at"], "whatsapp")
    if w2 is None:
        result["fail_step"] = "Sin WhatsApp 2"
        return result
    if not (0 <= minutes_between(c3["activity_completed_at"], w2["activity_completed_at"]) <= immediate_max_min):
        result["fail_step"] = "WhatsApp 2 no inmediato"
        return result
    result["whatsapp_2_ok"] = True

    c4 = get_next(group, w2["activity_completed_at"], "call")
    if c4 is None:
        result["fail_step"] = "Sin llamada 4"
        return result
    if not in_window(hours_between(w2["activity_completed_at"], c4["activity_completed_at"]), 36, tol_day_half_h):
        result["fail_step"] = "Llamada 4 fuera de ventana"
        return result
    result["call_4_ok"] = True

    w3 = get_next(group, c4["activity_completed_at"], "whatsapp")
    if w3 is None:
        result["fail_step"] = "Sin WhatsApp 3"
        return result
    if not (0 <= minutes_between(c4["activity_completed_at"], w3["activity_completed_at"]) <= immediate_max_min):
        result["fail_step"] = "WhatsApp 3 no inmediato"
        return result
    result["whatsapp_3_ok"] = True

    result["full_flow_ok"] = True
    result["fail_step"] = "Cumple todo"
    return result


def build_results(df, mode, immediate_max_min, tol_90_min, tol_half_day_h, tol_day_half_h):
    rows = []
    for _, group in df.groupby("lead_id", sort=False):
        if mode == "Solo secuencia":
            rows.append(evaluate_lead_sequence_only(group))
        else:
            rows.append(
                evaluate_lead_with_time(
                    group,
                    immediate_max_min,
                    tol_90_min,
                    tol_half_day_h,
                    tol_day_half_h,
                )
            )
    return pd.DataFrame(rows)


def card(title, value, subtitle=""):
    st.markdown(
        f"""
        <div style="
            border:1px solid #bbb;
            border-radius:10px;
            padding:14px 10px;
            text-align:center;
            background:#f7f7f7;
            color:#111;
            min-height:110px;
        ">
            <div style="font-size:14px; font-weight:700;">{title}</div>
            <div style="font-size:28px; font-weight:800; margin-top:8px;">{value}</div>
            <div style="font-size:12px; color:#555; margin-top:4px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.title("📞 Flujo de tratamiento de leads perdidos")

with st.sidebar:
    st.header("Configuración")
    mode = st.radio("Modo de validación", ["Solo secuencia", "Secuencia + tiempos"])
    immediate_max_min = st.number_input("WhatsApp inmediato (máx. min)", 0, 60, 10, 1)
    tol_90_min = st.number_input("Tolerancia llamada 2 (min)", 0, 180, 30, 5)
    tol_half_day_h = st.number_input("Tolerancia llamada 3 (horas)", 0, 24, 4, 1)
    tol_day_half_h = st.number_input("Tolerancia llamada 4 (horas)", 0, 48, 8, 1)

uploaded_file = st.file_uploader("Sube el Excel de actividades", type=["xlsx"])

if not uploaded_file:
    st.stop()

raw = pd.read_excel(uploaded_file)

required_cols = [
    "Negocio - ID",
    "Negocio - Negocio creado el",
    "Actividad - Hora en que se marcó como completada",
    "Negocio - Propietario",
    "Actividad - Tipo",
]

missing = [c for c in required_cols if c not in raw.columns]
if missing:
    st.error("Faltan columnas: " + ", ".join(missing))
    st.stop()

df = raw.rename(columns={
    "Negocio - ID": "lead_id",
    "Negocio - Negocio creado el": "lead_created_at",
    "Actividad - Hora en que se marcó como completada": "activity_completed_at",
    "Negocio - Propietario": "agent",
    "Actividad - Tipo": "activity_type",
}).copy()

df["lead_id"] = df["lead_id"].astype(str).str.strip()
df["agent"] = df["agent"].astype(str).str.strip()
df["lead_created_at"] = pd.to_datetime(df["lead_created_at"], errors="coerce")
df["activity_completed_at"] = pd.to_datetime(df["activity_completed_at"], errors="coerce")
df["activity_group"] = df["activity_type"].apply(classify_activity)

df = df.dropna(subset=["lead_id", "lead_created_at", "activity_completed_at", "agent"])
df = df[df["activity_group"].isin(["call", "whatsapp"])].copy()
df = df.sort_values(["lead_id", "activity_completed_at"])

results = build_results(df, mode, immediate_max_min, tol_90_min, tol_half_day_h, tol_day_half_h)

agents = sorted(results["agent"].dropna().unique().tolist())
selected_agent = st.selectbox("Selecciona agente", ["Todos"] + agents)

view = results if selected_agent == "Todos" else results[results["agent"] == selected_agent].copy()

c1, c2, c3 = st.columns(3)
c1.metric("Leads analizados", len(view))
c2.metric("Cumplen flujo completo", f"{pct(view['full_flow_ok']):.1f}%")
c3.metric("Modo", mode)

metrics = {
    "Llamada 1": pct(view["call_1_ok"]),
    "WhatsApp 1": pct(view["whatsapp_1_ok"]),
    "Llamada 2": pct(view["call_2_ok"]),
    "Llamada 3": pct(view["call_3_ok"]),
    "WhatsApp 2": pct(view["whatsapp_2_ok"]),
    "Llamada 4": pct(view["call_4_ok"]),
    "WhatsApp 3": pct(view["whatsapp_3_ok"]),
    "Flujo completo": pct(view["full_flow_ok"]),
}

st.subheader("Flujo esperado")

r1 = st.columns([1, 1, 1, 1])
with r1[0]:
    card("Llamada 1", f"{metrics['Llamada 1']:.1f}%", "desde creación")
with r1[1]:
    card("Llamada 2", f"{metrics['Llamada 2']:.1f}%", "tras WhatsApp 1")
with r1[2]:
    card("Llamada 3", f"{metrics['Llamada 3']:.1f}%", "tras llamada 2")
with r1[3]:
    card("Llamada 4", f"{metrics['Llamada 4']:.1f}%", "tras WhatsApp 2")

r2 = st.columns([1, 1, 1, 1])
with r2[0]:
    card("WhatsApp 1", f"{metrics['WhatsApp 1']:.1f}%", "tras llamada 1")
with r2[1]:
    st.write("")
with r2[2]:
    card("WhatsApp 2", f"{metrics['WhatsApp 2']:.1f}%", "tras llamada 3")
with r2[3]:
    card("WhatsApp 3", f"{metrics['WhatsApp 3']:.1f}%", "tras llamada 4")

st.markdown("### Resultado final")
card("Cumple flujo completo", f"{metrics['Flujo completo']:.1f}%", "lead perdido correctamente")

st.subheader("Resumen por agente")
summary = (
    results.groupby("agent")
    .agg(
        leads=("lead_id", "nunique"),
        llamada_1=("call_1_ok", lambda s: round(s.mean() * 100, 1)),
        whatsapp_1=("whatsapp_1_ok", lambda s: round(s.mean() * 100, 1)),
        llamada_2=("call_2_ok", lambda s: round(s.mean() * 100, 1)),
        llamada_3=("call_3_ok", lambda s: round(s.mean() * 100, 1)),
        whatsapp_2=("whatsapp_2_ok", lambda s: round(s.mean() * 100, 1)),
        llamada_4=("call_4_ok", lambda s: round(s.mean() * 100, 1)),
        whatsapp_3=("whatsapp_3_ok", lambda s: round(s.mean() * 100, 1)),
        flujo_completo=("full_flow_ok", lambda s: round(s.mean() * 100, 1)),
    )
    .reset_index()
    .sort_values("flujo_completo", ascending=False)
)
st.dataframe(summary, use_container_width=True, hide_index=True)

st.subheader("Motivo de fallo")
fails = (
    view.groupby("fail_step")
    .size()
    .reset_index(name="num_leads")
    .sort_values("num_leads", ascending=False)
)
st.dataframe(fails, use_container_width=True, hide_index=True)
