import streamlit as st
import pandas as pd
from datetime import time, timedelta

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

CALL_START_HOUR = 9
CALL_END_HOUR = 18


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


def next_open_day(dt):
    dt = dt + timedelta(days=1)
    while dt.weekday() == 6:  # domingo
        dt = dt + timedelta(days=1)
    return dt


def normalize_to_callcenter_open(dt, start_hour=9, end_hour=18):
    if pd.isna(dt):
        return pd.NaT

    start_t = time(start_hour, 0)
    end_t = time(end_hour, 0)

    # Domingo -> lunes 09:00
    if dt.weekday() == 6:
        return (dt + timedelta(days=1)).replace(
            hour=start_hour, minute=0, second=0, microsecond=0
        )

    current_t = dt.time()

    # Antes de apertura
    if current_t < start_t:
        return dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)

    # Dentro de horario
    if start_t <= current_t <= end_t:
        return dt

    # Después de cierre
    return next_open_day(dt).replace(
        hour=start_hour, minute=0, second=0, microsecond=0
    )


def add_hours_and_normalize(dt, hours_to_add, start_hour=9, end_hour=18):
    target = dt + timedelta(hours=hours_to_add)
    return normalize_to_callcenter_open(target, start_hour=start_hour, end_hour=end_hour)


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
        "lead_created_at": group["lead_created_at"].iloc[0],
        "normalized_created_at": group["normalized_created_at"].iloc[0],
        "was_normalized": bool(group["was_normalized"].iloc[0]),
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
    for activity in activities:
        if idx >= len(expected):
            break
        if activity == expected[idx]:
            result[keys[idx]] = True
            idx += 1

    result["full_flow_ok"] = all(result[k] for k in keys)

    if result["full_flow_ok"]:
        result["fail_step"] = "Cumple todo"
    else:
        for k, label in zip(
            keys,
            [
                "Sin llamada 1",
                "Sin WhatsApp 1",
                "Sin llamada 2",
                "Sin llamada 3",
                "Sin WhatsApp 2",
                "Sin llamada 4",
                "Sin WhatsApp 3",
            ],
        ):
            if not result[k]:
                result["fail_step"] = label
                break

    return result


def evaluate_lead_with_time(group):
    group = group.sort_values("activity_completed_at").copy()

    created_at = group["normalized_created_at"].iloc[0]

    result = {
        "lead_id": group["lead_id"].iloc[0],
        "agent": group["agent"].iloc[0],
        "lead_created_at": group["lead_created_at"].iloc[0],
        "normalized_created_at": created_at,
        "was_normalized": bool(group["was_normalized"].iloc[0]),
        "call_1_ok": False,
        "whatsapp_1_ok": False,
        "call_2_ok": False,
        "call_3_ok": False,
        "whatsapp_2_ok": False,
        "call_4_ok": False,
        "whatsapp_3_ok": False,
        "full_flow_ok": False,
        "fail_step": "",
        "call_1_at": pd.NaT,
        "whatsapp_1_at": pd.NaT,
        "call_2_at": pd.NaT,
        "call_3_at": pd.NaT,
        "whatsapp_2_at": pd.NaT,
        "call_4_at": pd.NaT,
        "whatsapp_3_at": pd.NaT,
        "target_call_2_at": pd.NaT,
        "target_call_3_at": pd.NaT,
        "target_call_4_at": pd.NaT,
    }

    # 1) Llamada 1: primera llamada tras creación normalizada
    call_1 = get_next(group, created_at, "call")
    if call_1 is None:
        result["fail_step"] = "Sin llamada 1"
        return result

    result["call_1_at"] = call_1["activity_completed_at"]
    result["call_1_ok"] = True

    # 2) WhatsApp 1: siguiente whatsapp después de llamada 1
    w1 = get_next(group, call_1["activity_completed_at"], "whatsapp")
    if w1 is None:
        result["fail_step"] = "Sin WhatsApp 1"
        return result

    result["whatsapp_1_at"] = w1["activity_completed_at"]
    result["whatsapp_1_ok"] = True

    # 3) Llamada 2: después de 90 min o más
    target_call_2 = call_1["activity_completed_at"] + timedelta(minutes=90)
    result["target_call_2_at"] = target_call_2

    c2 = get_next(group, target_call_2, "call")
    if c2 is None:
        result["fail_step"] = "Sin llamada 2"
        return result

    result["call_2_at"] = c2["activity_completed_at"]
    result["call_2_ok"] = True

    # 4) Llamada 3: 12 horas después, normalizado a horario call center
    target_call_3 = add_hours_and_normalize(
        c2["activity_completed_at"],
        12,
        start_hour=CALL_START_HOUR,
        end_hour=CALL_END_HOUR,
    )
    result["target_call_3_at"] = target_call_3

    c3 = get_next(group, target_call_3, "call")
    if c3 is None:
        result["fail_step"] = "Sin llamada 3"
        return result

    result["call_3_at"] = c3["activity_completed_at"]
    result["call_3_ok"] = True

    # 5) WhatsApp 2: siguiente whatsapp tras llamada 3
    w2 = get_next(group, c3["activity_completed_at"], "whatsapp")
    if w2 is None:
        result["fail_step"] = "Sin WhatsApp 2"
        return result

    result["whatsapp_2_at"] = w2["activity_completed_at"]
    result["whatsapp_2_ok"] = True

    # 6) Llamada 4: 36 horas después, normalizado a horario call center
    target_call_4 = add_hours_and_normalize(
        w2["activity_completed_at"],
        36,
        start_hour=CALL_START_HOUR,
        end_hour=CALL_END_HOUR,
    )
    result["target_call_4_at"] = target_call_4

    c4 = get_next(group, target_call_4, "call")
    if c4 is None:
        result["fail_step"] = "Sin llamada 4"
        return result

    result["call_4_at"] = c4["activity_completed_at"]
    result["call_4_ok"] = True

    # 7) WhatsApp 3: siguiente whatsapp tras llamada 4
    w3 = get_next(group, c4["activity_completed_at"], "whatsapp")
    if w3 is None:
        result["fail_step"] = "Sin WhatsApp 3"
        return result

    result["whatsapp_3_at"] = w3["activity_completed_at"]
    result["whatsapp_3_ok"] = True

    result["full_flow_ok"] = True
    result["fail_step"] = "Cumple todo"
    return result


@st.cache_data
def load_data(uploaded_file):
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
        raise ValueError("Faltan columnas: " + ", ".join(missing))

    df = raw.rename(
        columns={
            "Negocio - ID": "lead_id",
            "Negocio - Negocio creado el": "lead_created_at",
            "Actividad - Hora en que se marcó como completada": "activity_completed_at",
            "Negocio - Propietario": "agent",
            "Actividad - Tipo": "activity_type",
        }
    ).copy()

    df["lead_id"] = df["lead_id"].astype(str).str.strip()
    df["agent"] = df["agent"].astype(str).str.strip()
    df["lead_created_at"] = pd.to_datetime(df["lead_created_at"], errors="coerce")
    df["activity_completed_at"] = pd.to_datetime(df["activity_completed_at"], errors="coerce")
    df["activity_group"] = df["activity_type"].apply(classify_activity)

    df = df.dropna(subset=["lead_id", "lead_created_at", "activity_completed_at", "agent"])
    df = df[df["activity_group"].isin(["call", "whatsapp"])].copy()

    df["normalized_created_at"] = df["lead_created_at"].apply(
        lambda x: normalize_to_callcenter_open(
            x,
            start_hour=CALL_START_HOUR,
            end_hour=CALL_END_HOUR,
        )
    )
    df["was_normalized"] = df["normalized_created_at"] != df["lead_created_at"]

    df = df.sort_values(["lead_id", "activity_completed_at"])
    return df


@st.cache_data
def build_results(df, mode):
    rows = []
    for _, group in df.groupby("lead_id", sort=False):
        if mode == "Solo secuencia":
            rows.append(evaluate_lead_sequence_only(group))
        else:
            rows.append(evaluate_lead_with_time(group))
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

uploaded_file = st.file_uploader("Sube el Excel de actividades", type=["xlsx"])

if not uploaded_file:
    st.info("Sube el Excel para analizar los leads.")
    st.stop()

try:
    df = load_data(uploaded_file)
except Exception as exc:
    st.error(str(exc))
    st.stop()

results = build_results(df, mode)

agents = sorted(results["agent"].dropna().unique().tolist())
selected_agent = st.selectbox("Selecciona agente", ["Todos"] + agents)

view = results if selected_agent == "Todos" else results[results["agent"] == selected_agent].copy()

if view.empty:
    st.warning("No hay leads para el filtro seleccionado.")
    st.stop()

normalized_pct = round(view["was_normalized"].mean() * 100, 1) if len(view) else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Leads analizados", len(view))
c2.metric("Cumplen flujo completo", f"{pct(view['full_flow_ok']):.1f}%")
c3.metric("Leads normalizados", f"{normalized_pct:.1f}%")
c4.metric("Modo", mode)

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
    card("Llamada 1", f"{metrics['Llamada 1']:.1f}%", "tras creación")
with r1[1]:
    card("Llamada 2", f"{metrics['Llamada 2']:.1f}%", "después de 90 min")
with r1[2]:
    card("Llamada 3", f"{metrics['Llamada 3']:.1f}%", "después de 12 h")
with r1[3]:
    card("Llamada 4", f"{metrics['Llamada 4']:.1f}%", "después de 1,5 días")

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
        leads_normalizados=("was_normalized", lambda s: round(s.mean() * 100, 1)),
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

st.subheader("Detalle de leads")
detail_cols = [
    "lead_id",
    "agent",
    "lead_created_at",
    "normalized_created_at",
    "was_normalized",
    "call_1_ok",
    "whatsapp_1_ok",
    "call_2_ok",
    "call_3_ok",
    "whatsapp_2_ok",
    "call_4_ok",
    "whatsapp_3_ok",
    "full_flow_ok",
    "fail_step",
    "call_1_at",
    "whatsapp_1_at",
    "call_2_at",
    "target_call_2_at",
    "call_3_at",
    "target_call_3_at",
    "whatsapp_2_at",
    "call_4_at",
    "target_call_4_at",
    "whatsapp_3_at",
]
existing_cols = [c for c in detail_cols if c in view.columns]
st.dataframe(view[existing_cols], use_container_width=True, hide_index=True)
