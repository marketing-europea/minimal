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


def pct(series):
    if len(series) == 0:
        return 0.0
    return round(series.mean() * 100, 1)


def minutes_between(a, b):
    return (b - a).total_seconds() / 60.0


def hours_between(a, b):
    return (b - a).total_seconds() / 3600.0


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

    if dt.weekday() == 6:  # domingo
        return (dt + timedelta(days=1)).replace(
            hour=start_hour, minute=0, second=0, microsecond=0
        )

    current_t = dt.time()

    if current_t < start_t:
        return dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)

    if start_t <= current_t <= end_t:
        return dt

    return next_open_day(dt).replace(
        hour=start_hour, minute=0, second=0, microsecond=0
    )


def extract_lead_milestones(group: pd.DataFrame) -> dict:
    group = group.sort_values("activity_completed_at").copy()

    result = {
        "lead_id": group["lead_id"].iloc[0],
        "agent": group["agent"].iloc[0],
        "lead_created_at": group["lead_created_at"].iloc[0],
        "normalized_created_at": group["normalized_created_at"].iloc[0],
        "was_normalized": bool(group["was_normalized"].iloc[0]),

        "call_1_at": pd.NaT,
        "wpp_1_at": pd.NaT,
        "call_2_at": pd.NaT,
        "call_3_at": pd.NaT,
        "wpp_2_at": pd.NaT,
        "call_4_at": pd.NaT,
        "wpp_3_at": pd.NaT,

        "has_call_1": False,
        "has_wpp_1": False,
        "has_call_2": False,
        "has_call_3": False,
        "has_wpp_2": False,
        "has_call_4": False,
        "has_wpp_3": False,

        "call_1_delay_min": None,
        "wpp_1_delay_min": None,
        "call_2_delay_h": None,
        "call_3_delay_h": None,
        "wpp_2_delay_min": None,
        "call_4_delay_h": None,
        "wpp_3_delay_min": None,
    }

    calls = group[group["activity_group"] == "call"].sort_values("activity_completed_at")
    wpps = group[group["activity_group"] == "whatsapp"].sort_values("activity_completed_at")

    # Llamada 1: primera llamada desde creación normalizada
    call_1 = calls[calls["activity_completed_at"] >= result["normalized_created_at"]]
    if not call_1.empty:
        result["call_1_at"] = call_1.iloc[0]["activity_completed_at"]
        result["has_call_1"] = True
        result["call_1_delay_min"] = round(
            minutes_between(result["normalized_created_at"], result["call_1_at"]), 2
        )

    # WhatsApp 1: primer WhatsApp después de llamada 1
    if result["has_call_1"]:
        wpp_1 = wpps[wpps["activity_completed_at"] > result["call_1_at"]]
        if not wpp_1.empty:
            result["wpp_1_at"] = wpp_1.iloc[0]["activity_completed_at"]
            result["has_wpp_1"] = True
            result["wpp_1_delay_min"] = round(
                minutes_between(result["call_1_at"], result["wpp_1_at"]), 2
            )

    # Llamada 2: siguiente llamada después de llamada 1
    if result["has_call_1"]:
        call_2 = calls[calls["activity_completed_at"] > result["call_1_at"]]
        if not call_2.empty:
            result["call_2_at"] = call_2.iloc[0]["activity_completed_at"]
            result["has_call_2"] = True

            base_time = result["wpp_1_at"] if result["has_wpp_1"] else result["call_1_at"]
            result["call_2_delay_h"] = round(
                hours_between(base_time, result["call_2_at"]), 2
            )

    # Llamada 3: siguiente llamada después de llamada 2
    if result["has_call_2"]:
        call_3 = calls[calls["activity_completed_at"] > result["call_2_at"]]
        if not call_3.empty:
            result["call_3_at"] = call_3.iloc[0]["activity_completed_at"]
            result["has_call_3"] = True
            result["call_3_delay_h"] = round(
                hours_between(result["call_2_at"], result["call_3_at"]), 2
            )

    # WhatsApp 2: siguiente whatsapp después de llamada 3
    if result["has_call_3"]:
        wpp_2 = wpps[wpps["activity_completed_at"] > result["call_3_at"]]
        if not wpp_2.empty:
            result["wpp_2_at"] = wpp_2.iloc[0]["activity_completed_at"]
            result["has_wpp_2"] = True
            result["wpp_2_delay_min"] = round(
                minutes_between(result["call_3_at"], result["wpp_2_at"]), 2
            )

    # Llamada 4: siguiente llamada después de llamada 3
    if result["has_call_3"]:
        call_4 = calls[calls["activity_completed_at"] > result["call_3_at"]]
        if not call_4.empty:
            result["call_4_at"] = call_4.iloc[0]["activity_completed_at"]
            result["has_call_4"] = True

            base_time = result["wpp_2_at"] if result["has_wpp_2"] else result["call_3_at"]
            result["call_4_delay_h"] = round(
                hours_between(base_time, result["call_4_at"]), 2
            )

    # WhatsApp 3: siguiente whatsapp después de llamada 4
    if result["has_call_4"]:
        wpp_3 = wpps[wpps["activity_completed_at"] > result["call_4_at"]]
        if not wpp_3.empty:
            result["wpp_3_at"] = wpp_3.iloc[0]["activity_completed_at"]
            result["has_wpp_3"] = True
            result["wpp_3_delay_min"] = round(
                minutes_between(result["call_4_at"], result["wpp_3_at"]), 2
            )

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

    df = df.sort_values(["lead_id", "activity_completed_at"]).reset_index(drop=True)
    return df


@st.cache_data
def build_milestones(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in df.groupby("lead_id", sort=False):
        rows.append(extract_lead_milestones(group))
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
    st.header("Filtros de tiempo")
    max_call_1_min = st.number_input("Límite Llamada 1 (min)", min_value=1, max_value=1440, value=5)
    max_wpp_1_min = st.number_input("Límite WhatsApp 1 (min)", min_value=1, max_value=1440, value=5)
    max_call_2_h = st.number_input("Límite Llamada 2 (h)", min_value=0.0, max_value=240.0, value=4.0, step=0.5)
    max_call_3_h = st.number_input("Límite Llamada 3 (h)", min_value=0.0, max_value=240.0, value=12.0, step=0.5)
    max_wpp_2_min = st.number_input("Límite WhatsApp 2 (min)", min_value=1, max_value=1440, value=5)
    max_call_4_h = st.number_input("Límite Llamada 4 (h)", min_value=0.0, max_value=240.0, value=36.0, step=0.5)
    max_wpp_3_min = st.number_input("Límite WhatsApp 3 (min)", min_value=1, max_value=1440, value=5)

uploaded_file = st.file_uploader("Sube el Excel de actividades", type=["xlsx"])

if not uploaded_file:
    st.info("Sube el Excel para analizar los leads.")
    st.stop()

try:
    df = load_data(uploaded_file)
except Exception as exc:
    st.error(str(exc))
    st.stop()

milestones = build_milestones(df)

agents = sorted(milestones["agent"].dropna().unique().tolist())
selected_agent = st.selectbox("Selecciona agente", ["Todos"] + agents)

view = milestones if selected_agent == "Todos" else milestones[milestones["agent"] == selected_agent].copy()

if view.empty:
    st.warning("No hay leads para el filtro seleccionado.")
    st.stop()

normalized_pct = round(view["was_normalized"].mean() * 100, 1) if len(view) else 0.0

c1, c2, c3 = st.columns(3)
c1.metric("Leads analizados", len(view))
c2.metric("Leads normalizados", f"{normalized_pct:.1f}%")
c3.metric("Agente", selected_agent)

# NIVEL 1: flujo completo
metrics = {
    "Llamada 1": pct(view["has_call_1"]),
    "WhatsApp 1": pct(view["has_wpp_1"]),
    "Llamada 2": pct(view["has_call_2"]),
    "Llamada 3": pct(view["has_call_3"]),
    "WhatsApp 2": pct(view["has_wpp_2"]),
    "Llamada 4": pct(view["has_call_4"]),
    "WhatsApp 3": pct(view["has_wpp_3"]),
}

st.subheader("Flujo completo alcanzado")

r1 = st.columns([1, 1, 1, 1])
with r1[0]:
    card("Llamada 1", f"{metrics['Llamada 1']:.1f}%", "del total de leads")
with r1[1]:
    card("Llamada 2", f"{metrics['Llamada 2']:.1f}%", "del total de leads")
with r1[2]:
    card("Llamada 3", f"{metrics['Llamada 3']:.1f}%", "del total de leads")
with r1[3]:
    card("Llamada 4", f"{metrics['Llamada 4']:.1f}%", "del total de leads")

r2 = st.columns([1, 1, 1, 1])
with r2[0]:
    card("WhatsApp 1", f"{metrics['WhatsApp 1']:.1f}%", "del total de leads")
with r2[1]:
    st.write("")
with r2[2]:
    card("WhatsApp 2", f"{metrics['WhatsApp 2']:.1f}%", "del total de leads")
with r2[3]:
    card("WhatsApp 3", f"{metrics['WhatsApp 3']:.1f}%", "del total de leads")

st.subheader("Cumplimiento de tiempo sobre los leads que sí llegaron al paso")

time_rows = []

def add_time_row(step_name, exists_col, delay_col, limit_value, unit):
    subset = view[view[exists_col] == True].copy()
    total_step = len(subset)
    if total_step == 0:
        within = 0
        pct_within = 0.0
    else:
        within = (subset[delay_col] <= limit_value).sum()
        pct_within = round(within / total_step * 100, 1)

    time_rows.append({
        "Paso": step_name,
        "Leads que llegaron al paso": total_step,
        "Leads dentro de límite": int(within),
        "% dentro de límite": pct_within,
        "Límite aplicado": f"{limit_value} {unit}",
    })

add_time_row("Llamada 1", "has_call_1", "call_1_delay_min", max_call_1_min, "min")
add_time_row("WhatsApp 1", "has_wpp_1", "wpp_1_delay_min", max_wpp_1_min, "min")
add_time_row("Llamada 2", "has_call_2", "call_2_delay_h", max_call_2_h, "h")
add_time_row("Llamada 3", "has_call_3", "call_3_delay_h", max_call_3_h, "h")
add_time_row("WhatsApp 2", "has_wpp_2", "wpp_2_delay_min", max_wpp_2_min, "min")
add_time_row("Llamada 4", "has_call_4", "call_4_delay_h", max_call_4_h, "h")
add_time_row("WhatsApp 3", "has_wpp_3", "wpp_3_delay_min", max_wpp_3_min, "min")

time_summary = pd.DataFrame(time_rows)
st.dataframe(time_summary, use_container_width=True, hide_index=True)

selected_step = st.selectbox(
    "Ver detalle de cumplimiento temporal para un paso",
    [
        "Llamada 1",
        "WhatsApp 1",
        "Llamada 2",
        "Llamada 3",
        "WhatsApp 2",
        "Llamada 4",
        "WhatsApp 3",
    ]
)

step_map = {
    "Llamada 1": ("has_call_1", "call_1_delay_min", max_call_1_min, "min"),
    "WhatsApp 1": ("has_wpp_1", "wpp_1_delay_min", max_wpp_1_min, "min"),
    "Llamada 2": ("has_call_2", "call_2_delay_h", max_call_2_h, "h"),
    "Llamada 3": ("has_call_3", "call_3_delay_h", max_call_3_h, "h"),
    "WhatsApp 2": ("has_wpp_2", "wpp_2_delay_min", max_wpp_2_min, "min"),
    "Llamada 4": ("has_call_4", "call_4_delay_h", max_call_4_h, "h"),
    "WhatsApp 3": ("has_wpp_3", "wpp_3_delay_min", max_wpp_3_min, "min"),
}

exists_col, delay_col, limit_value, unit = step_map[selected_step]
step_detail = view[view[exists_col] == True].copy()
if not step_detail.empty:
    step_detail["within_limit"] = step_detail[delay_col] <= limit_value

st.subheader(f"Detalle temporal · {selected_step}")
st.write(f"Mostrando solo leads que sí llegaron a {selected_step.lower()}.")

detail_cols = [
    "lead_id",
    "agent",
    "lead_created_at",
    "normalized_created_at",
    "was_normalized",
    "call_1_at",
    "wpp_1_at",
    "call_2_at",
    "call_3_at",
    "wpp_2_at",
    "call_4_at",
    "wpp_3_at",
    "call_1_delay_min",
    "wpp_1_delay_min",
    "call_2_delay_h",
    "call_3_delay_h",
    "wpp_2_delay_min",
    "call_4_delay_h",
    "wpp_3_delay_min",
    "within_limit",
]

available_cols = [c for c in detail_cols if c in step_detail.columns]
st.dataframe(step_detail[available_cols], use_container_width=True, hide_index=True)

st.subheader("Resumen por agente")
summary = (
    milestones.groupby("agent")
    .agg(
        leads=("lead_id", "nunique"),
        leads_normalizados=("was_normalized", lambda s: round(s.mean() * 100, 1)),
        llamada_1=("has_call_1", lambda s: round(s.mean() * 100, 1)),
        whatsapp_1=("has_wpp_1", lambda s: round(s.mean() * 100, 1)),
        llamada_2=("has_call_2", lambda s: round(s.mean() * 100, 1)),
        llamada_3=("has_call_3", lambda s: round(s.mean() * 100, 1)),
        whatsapp_2=("has_wpp_2", lambda s: round(s.mean() * 100, 1)),
        llamada_4=("has_call_4", lambda s: round(s.mean() * 100, 1)),
        whatsapp_3=("has_wpp_3", lambda s: round(s.mean() * 100, 1)),
    )
    .reset_index()
    .sort_values("leads", ascending=False)
)

st.dataframe(summary, use_container_width=True, hide_index=True)
