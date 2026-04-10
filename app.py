import re
from datetime import time, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Analisis de Leads", layout="wide")

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

MONTHS_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
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


def normalize_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def is_outbound_call_subject(subject):
    text = normalize_text(subject)
    outbound_patterns = [
        "llamada saliente",
        "llamada saliente (",
        "llamada saliente de ",
    ]
    return any(pat in text for pat in outbound_patterns)


def extract_origin_phone(subject):
    if pd.isna(subject):
        return None

    text = str(subject)
    match = re.search(r"\bde\s+(\+\d{7,20})\b", text)
    if match:
        return match.group(1)
    return None


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

    if dt.weekday() == 6:
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
        "activity_year": group["activity_year"].iloc[0],
        "activity_month": group["activity_month"].iloc[0],
        "activity_month_name": group["activity_month_name"].iloc[0],
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

    call_1 = calls[calls["activity_completed_at"] >= result["normalized_created_at"]]
    if not call_1.empty:
        result["call_1_at"] = call_1.iloc[0]["activity_completed_at"]
        result["has_call_1"] = True
        result["call_1_delay_min"] = round(
            minutes_between(result["normalized_created_at"], result["call_1_at"]), 2
        )

    if result["has_call_1"]:
        wpp_1 = wpps[wpps["activity_completed_at"] > result["call_1_at"]]
        if not wpp_1.empty:
            result["wpp_1_at"] = wpp_1.iloc[0]["activity_completed_at"]
            result["has_wpp_1"] = True
            result["wpp_1_delay_min"] = round(
                minutes_between(result["call_1_at"], result["wpp_1_at"]), 2
            )

    if result["has_call_1"]:
        call_2 = calls[calls["activity_completed_at"] > result["call_1_at"]]
        if not call_2.empty:
            result["call_2_at"] = call_2.iloc[0]["activity_completed_at"]
            result["has_call_2"] = True
            base_time = result["wpp_1_at"] if result["has_wpp_1"] else result["call_1_at"]
            result["call_2_delay_h"] = round(
                hours_between(base_time, result["call_2_at"]), 2
            )

    if result["has_call_2"]:
        call_3 = calls[calls["activity_completed_at"] > result["call_2_at"]]
        if not call_3.empty:
            result["call_3_at"] = call_3.iloc[0]["activity_completed_at"]
            result["has_call_3"] = True
            result["call_3_delay_h"] = round(
                hours_between(result["call_2_at"], result["call_3_at"]), 2
            )

    if result["has_call_3"]:
        wpp_2 = wpps[wpps["activity_completed_at"] > result["call_3_at"]]
        if not wpp_2.empty:
            result["wpp_2_at"] = wpp_2.iloc[0]["activity_completed_at"]
            result["has_wpp_2"] = True
            result["wpp_2_delay_min"] = round(
                minutes_between(result["call_3_at"], result["wpp_2_at"]), 2
            )

    if result["has_call_3"]:
        call_4 = calls[calls["activity_completed_at"] > result["call_3_at"]]
        if not call_4.empty:
            result["call_4_at"] = call_4.iloc[0]["activity_completed_at"]
            result["has_call_4"] = True
            base_time = result["wpp_2_at"] if result["has_wpp_2"] else result["call_3_at"]
            result["call_4_delay_h"] = round(
                hours_between(base_time, result["call_4_at"]), 2
            )

    if result["has_call_4"]:
        wpp_3 = wpps[wpps["activity_completed_at"] > result["call_4_at"]]
        if not wpp_3.empty:
            result["wpp_3_at"] = wpp_3.iloc[0]["activity_completed_at"]
            result["has_wpp_3"] = True
            result["wpp_3_delay_min"] = round(
                minutes_between(result["call_4_at"], result["wpp_3_at"]), 2
            )

    return result


def analyze_phone_carrousel(group: pd.DataFrame) -> dict:
    group = group.sort_values("activity_completed_at").copy()

    calls = group[
        (group["activity_group"] == "call") &
        (group["is_outbound_call"] == True)
    ].copy()

    calls = calls[calls["origin_phone"].notna()].copy()

    result = {
        "lead_id": group["lead_id"].iloc[0],
        "agent": group["agent"].iloc[0],
        "lead_created_at": group["lead_created_at"].iloc[0],
        "activity_year": group["activity_year"].iloc[0],
        "activity_month": group["activity_month"].iloc[0],
        "activity_month_name": group["activity_month_name"].iloc[0],
        "num_calls_with_phone": 0,
        "unique_origin_phones": 0,
        "expected_unique_phones": 0,
        "unique_origin_phones_first_3": 0,
        "first_3_phones_sequence": "",
        "has_outbound_call_with_phone": False,
        "carrousel_status": "Sin llamadas",
        "phones_sequence": "",
    }

    if calls.empty:
        return result

    phones = calls["origin_phone"].tolist()
    num_calls = len(phones)
    unique_phones_total = len(set(phones))

    result["num_calls_with_phone"] = num_calls
    result["unique_origin_phones"] = unique_phones_total
    result["phones_sequence"] = " | ".join(phones)
    result["has_outbound_call_with_phone"] = True

    first_three = phones[:3]
    unique_first_three = len(set(first_three))

    result["expected_unique_phones"] = min(num_calls, 3)
    result["unique_origin_phones_first_3"] = unique_first_three
    result["first_3_phones_sequence"] = " | ".join(first_three)

    if num_calls == 1:
        result["carrousel_status"] = "Incorrecto"
    elif num_calls == 2:
        if len(set(phones[:2])) == 2:
            result["carrousel_status"] = "Uso ideal"
        else:
            result["carrousel_status"] = "Incorrecto"
    else:
        if unique_first_three == 3:
            result["carrousel_status"] = "Uso ideal"
        elif unique_first_three == 2:
            result["carrousel_status"] = "Uso parcial"
        else:
            result["carrousel_status"] = "Incorrecto"

    return result


def resolve_completed_column(columns):
    if "Actividad - Hora en que se marcó como completada" in columns:
        return "Actividad - Hora en que se marcó como completada"
    if "Actividad - Hora en que se marco como completada" in columns:
        return "Actividad - Hora en que se marco como completada"
    return None


def compute_flow_usage_score(df: pd.DataFrame) -> pd.Series:
    step_cols = [
        "has_call_1",
        "has_wpp_1",
        "has_call_2",
        "has_call_3",
        "has_wpp_2",
        "has_call_4",
        "has_wpp_3",
    ]
    return df[step_cols].sum(axis=1) / len(step_cols) * 100


def apply_general_filters(df: pd.DataFrame, selected_year, selected_month, month_name_to_num):
    out = df.copy()

    if selected_year != "Todos":
        out = out[out["activity_year"] == selected_year].copy()

    if selected_month != "Todos":
        month_num = month_name_to_num[selected_month]
        out = out[out["activity_month"] == month_num].copy()

    return out


@st.cache_data
def load_data(uploaded_file):
    raw = pd.read_excel(uploaded_file)

    completed_col = resolve_completed_column(raw.columns)

    required_base = [
        "Negocio - ID",
        "Negocio - Negocio creado el",
        "Negocio - Propietario",
        "Actividad - Tipo",
        "Actividad - Asunto",
    ]

    missing = [c for c in required_base if c not in raw.columns]
    if completed_col is None:
        missing.append("Actividad - Hora en que se marco/marcó como completada")

    if missing:
        raise ValueError("Faltan columnas: " + ", ".join(missing))

    df = raw.rename(
        columns={
            "Negocio - ID": "lead_id",
            "Negocio - Negocio creado el": "lead_created_at",
            completed_col: "activity_completed_at",
            "Negocio - Propietario": "agent",
            "Actividad - Tipo": "activity_type",
            "Actividad - Asunto": "activity_subject",
        }
    ).copy()

    df["lead_id"] = df["lead_id"].astype(str).str.strip()
    df["agent"] = df["agent"].astype(str).str.strip()
    df["lead_created_at"] = pd.to_datetime(df["lead_created_at"], errors="coerce")
    df["activity_completed_at"] = pd.to_datetime(df["activity_completed_at"], errors="coerce")
    df["activity_group"] = df["activity_type"].apply(classify_activity)
    df["origin_phone"] = df["activity_subject"].apply(extract_origin_phone)
    df["is_outbound_call"] = df["activity_subject"].apply(is_outbound_call_subject)

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

    df["activity_year"] = df["activity_completed_at"].dt.year
    df["activity_month"] = df["activity_completed_at"].dt.month
    df["activity_month_name"] = df["activity_month"].map(MONTHS_ES)

    df["lead_created_year"] = df["lead_created_at"].dt.year
    df["lead_created_month"] = df["lead_created_at"].dt.month
    df["lead_created_month_name"] = df["lead_created_month"].map(MONTHS_ES)

    df = df.sort_values(["lead_id", "activity_completed_at"]).reset_index(drop=True)
    return df


@st.cache_data
def build_milestones(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in df.groupby("lead_id", sort=False):
        rows.append(extract_lead_milestones(group))
    out = pd.DataFrame(rows)

    expected_cols = {
        "lead_id": None,
        "agent": None,
        "lead_created_at": pd.NaT,
        "normalized_created_at": pd.NaT,
        "was_normalized": False,
        "activity_year": None,
        "activity_month": None,
        "activity_month_name": None,
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

    for col, default_value in expected_cols.items():
        if col not in out.columns:
            out[col] = default_value

    return out


@st.cache_data
def build_carrousel_analysis(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in df.groupby("lead_id", sort=False):
        rows.append(analyze_phone_carrousel(group))

    out = pd.DataFrame(rows)

    expected_cols = {
        "lead_id": None,
        "agent": None,
        "lead_created_at": pd.NaT,
        "activity_year": None,
        "activity_month": None,
        "activity_month_name": None,
        "num_calls_with_phone": 0,
        "unique_origin_phones": 0,
        "expected_unique_phones": 0,
        "unique_origin_phones_first_3": 0,
        "first_3_phones_sequence": "",
        "has_outbound_call_with_phone": False,
        "carrousel_status": "Sin llamadas",
        "phones_sequence": "",
    }

    for col, default_value in expected_cols.items():
        if col not in out.columns:
            out[col] = default_value

    return out


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


st.title("📞 Analisis de leads y llamadas")

with st.sidebar:
    page = st.radio(
        "Selecciona analisis",
        ["Resumen / resultados", "Flujo de tratamiento", "Uso de carrusel telefonico"],
        key="page_selector",
    )

    max_call_1_min = 5
    max_wpp_1_min = 5
    max_call_2_h = 4.0
    max_call_3_h = 12.0
    max_wpp_2_min = 5
    max_call_4_h = 36.0
    max_wpp_3_min = 5

    if page in ["Resumen / resultados", "Flujo de tratamiento"]:
        st.header("Filtros de tiempo")
        max_call_1_min = st.number_input("Limite Llamada 1 (min)", min_value=1, max_value=1440, value=5)
        max_wpp_1_min = st.number_input("Limite WhatsApp 1 (min)", min_value=1, max_value=1440, value=5)
        max_call_2_h = st.number_input("Limite Llamada 2 (h)", min_value=0.0, max_value=240.0, value=4.0, step=0.5)
        max_call_3_h = st.number_input("Limite Llamada 3 (h)", min_value=0.0, max_value=240.0, value=12.0, step=0.5)
        max_wpp_2_min = st.number_input("Limite WhatsApp 2 (min)", min_value=1, max_value=1440, value=5)
        max_call_4_h = st.number_input("Limite Llamada 4 (h)", min_value=0.0, max_value=240.0, value=36.0, step=0.5)
        max_wpp_3_min = st.number_input("Limite WhatsApp 3 (min)", min_value=1, max_value=1440, value=5)

uploaded_file = st.file_uploader("Sube el Excel de actividades", type=["xlsx"])

if not uploaded_file:
    st.info("Sube el Excel para analizar los leads.")
    st.stop()

try:
    df = load_data(uploaded_file)
except Exception as exc:
    st.error(str(exc))
    st.stop()

month_name_to_num = {v: k for k, v in MONTHS_ES.items()}

available_years = sorted([int(y) for y in df["activity_year"].dropna().unique().tolist()])
available_months_num = sorted([int(m) for m in df["activity_month"].dropna().unique().tolist()])
available_months = [MONTHS_ES[m] for m in available_months_num]

with st.sidebar:
    st.header("Filtros generales")
    selected_year = st.selectbox("Año", ["Todos"] + available_years)
    selected_month = st.selectbox("Mes", ["Todos"] + available_months)

df_filtered = apply_general_filters(df, selected_year, selected_month, month_name_to_num)

# =========================
# PAGINA RESUMEN / RESULTADOS
# =========================
if page == "Resumen / resultados":
    milestones = build_milestones(df_filtered)
    carrousel_df = build_carrousel_analysis(df_filtered)

    with st.sidebar:
        st.header("Filtros resumen")
        selected_carrousel_status_resumen = st.selectbox(
            "Estado carrusel para el grafico",
            ["Uso ideal", "Uso parcial", "Incorrecto", "Sin llamadas"],
            key="selected_carrousel_status_resumen",
        )
        only_evaluable_resumen = st.checkbox(
            "Solo leads evaluables en carrusel",
            value=True,
            key="only_evaluable_resumen"
        )

    if milestones.empty:
        st.warning("No hay datos para los filtros seleccionados.")
        st.stop()

    milestones["flow_usage_pct"] = compute_flow_usage_score(milestones)

    milestones["call_1_within_limit"] = milestones["has_call_1"] & (milestones["call_1_delay_min"] <= max_call_1_min)
    milestones["wpp_1_within_limit"] = milestones["has_wpp_1"] & (milestones["wpp_1_delay_min"] <= max_wpp_1_min)
    milestones["call_2_within_limit"] = milestones["has_call_2"] & (milestones["call_2_delay_h"] <= max_call_2_h)
    milestones["call_3_within_limit"] = milestones["has_call_3"] & (milestones["call_3_delay_h"] <= max_call_3_h)
    milestones["wpp_2_within_limit"] = milestones["has_wpp_2"] & (milestones["wpp_2_delay_min"] <= max_wpp_2_min)
    milestones["call_4_within_limit"] = milestones["has_call_4"] & (milestones["call_4_delay_h"] <= max_call_4_h)
    milestones["wpp_3_within_limit"] = milestones["has_wpp_3"] & (milestones["wpp_3_delay_min"] <= max_wpp_3_min)

    limit_cols = [
        "call_1_within_limit",
        "wpp_1_within_limit",
        "call_2_within_limit",
        "call_3_within_limit",
        "wpp_2_within_limit",
        "call_4_within_limit",
        "wpp_3_within_limit",
    ]
    milestones["flow_quality_pct"] = milestones[limit_cols].sum(axis=1) / len(limit_cols) * 100

    flow_agent_summary = (
        milestones.groupby("agent")
        .agg(
            leads=("lead_id", "nunique"),
            uso_flujo_pct=("flow_usage_pct", "mean"),
            calidad_flujo_pct=("flow_quality_pct", "mean"),
        )
        .reset_index()
    )

    carrousel_df_resumen = carrousel_df.copy()
    if only_evaluable_resumen:
        carrousel_df_resumen = carrousel_df_resumen[
            carrousel_df_resumen["has_outbound_call_with_phone"] == True
        ].copy()

    if not carrousel_df_resumen.empty:
        carrousel_agent_summary = (
            carrousel_df_resumen.groupby("agent")
            .agg(
                leads_carrousel=("lead_id", "nunique"),
                uso_ideal_carrusel=("carrousel_status", lambda s: round((s == "Uso ideal").mean() * 100, 1)),
                uso_parcial_carrusel=("carrousel_status", lambda s: round((s == "Uso parcial").mean() * 100, 1)),
                incorrecto_carrusel=("carrousel_status", lambda s: round((s == "Incorrecto").mean() * 100, 1)),
                sin_llamadas_carrusel=("carrousel_status", lambda s: round((s == "Sin llamadas").mean() * 100, 1)),
            )
            .reset_index()
        )
        carrousel_agent_summary["cumplimiento_carrusel"] = (
            carrousel_agent_summary["uso_ideal_carrusel"] +
            carrousel_agent_summary["uso_parcial_carrusel"]
        ).round(1)
    else:
        carrousel_agent_summary = pd.DataFrame(columns=[
            "agent",
            "leads_carrousel",
            "uso_ideal_carrusel",
            "uso_parcial_carrusel",
            "incorrecto_carrusel",
            "sin_llamadas_carrusel",
            "cumplimiento_carrusel",
        ])

    metric_col_map = {
        "Uso ideal": "uso_ideal_carrusel",
        "Uso parcial": "uso_parcial_carrusel",
        "Incorrecto": "incorrecto_carrusel",
        "Sin llamadas": "sin_llamadas_carrusel",
    }
    selected_metric_col = metric_col_map[selected_carrousel_status_resumen]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Leads analizados", len(milestones))
    k2.metric("Agentes", milestones["agent"].nunique())
    k3.metric(
        "Uso medio del flujo",
        f"{flow_agent_summary['uso_flujo_pct'].mean():.1f}%" if not flow_agent_summary.empty else "0.0%"
    )
    k4.metric(
        f"Carrusel · {selected_carrousel_status_resumen}",
        f"{carrousel_agent_summary[selected_metric_col].mean():.1f}%"
        if not carrousel_agent_summary.empty else "0.0%"
    )

    st.subheader("Grafico 1 · Agente por agente · Quien usa el flujo")

    chart_flow_use = (
        flow_agent_summary[["agent", "uso_flujo_pct"]]
        .sort_values("uso_flujo_pct", ascending=False)
        .reset_index(drop=True)
    )

    fig, ax = plt.subplots(figsize=(14, 6))

    bars = ax.bar(
        chart_flow_use["agent"],
        chart_flow_use["uso_flujo_pct"]
    )

    ax.set_ylabel("%")
    ax.set_xlabel("Agente")
    ax.set_title("Uso del flujo por agente")
    ax.set_ylim(0, max(chart_flow_use["uso_flujo_pct"].max() + 10, 10))
    plt.xticks(rotation=90)

    for bar, value in zip(bars, chart_flow_use["uso_flujo_pct"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold"
        )

    st.pyplot(fig)

    st.subheader(
        f"Grafico 2 · Agente por agente · % de leads con carrusel en estado: {selected_carrousel_status_resumen}"
    )
    if not carrousel_agent_summary.empty:
        chart_carrousel = (
            carrousel_agent_summary[["agent", selected_metric_col]]
            .sort_values(selected_metric_col, ascending=False)
            .set_index("agent")
        )
        st.bar_chart(chart_carrousel)
    else:
        st.info("No hay datos de carrusel para los filtros seleccionados.")

    st.subheader("Tabla resumen por agente")
    final_summary = flow_agent_summary.merge(
        carrousel_agent_summary,
        on="agent",
        how="left"
    )
    st.dataframe(final_summary, use_container_width=True, hide_index=True)

    st.stop()

# =========================
# PAGINA CARRUSEL
# =========================
if page == "Uso de carrusel telefonico":
    carrousel_df = build_carrousel_analysis(df_filtered)

    for col, default_value in {
        "lead_id": None,
        "agent": None,
        "num_calls_with_phone": 0,
        "unique_origin_phones": 0,
        "expected_unique_phones": 0,
        "unique_origin_phones_first_3": 0,
        "first_3_phones_sequence": "",
        "has_outbound_call_with_phone": False,
        "carrousel_status": "Sin llamadas",
        "phones_sequence": "",
        "activity_year": None,
        "activity_month_name": None,
    }.items():
        if col not in carrousel_df.columns:
            carrousel_df[col] = default_value

    agents_carrousel = sorted(carrousel_df["agent"].dropna().unique().tolist())

    with st.sidebar:
        st.header("Filtros carrusel")
        selected_agent_carrousel = st.selectbox(
            "Agente",
            ["Todos"] + agents_carrousel,
            key="selected_agent_carrousel"
        )
        selected_carrousel_status = st.selectbox(
            "Estado del carrusel",
            ["Todos", "Uso ideal", "Uso parcial", "Incorrecto", "Sin llamadas"],
            key="selected_carrousel_status"
        )
        only_evaluable = st.checkbox(
            "Solo leads con llamadas salientes evaluables",
            value=True,
            key="only_evaluable_carrousel"
        )

    view = carrousel_df.copy()

    if selected_agent_carrousel != "Todos":
        view = view[view["agent"] == selected_agent_carrousel].copy()

    if only_evaluable:
        view = view[view["has_outbound_call_with_phone"] == True].copy()

    if selected_carrousel_status != "Todos":
        view = view[view["carrousel_status"] == selected_carrousel_status].copy()

    if view.empty:
        st.warning("No hay leads para el filtro seleccionado.")
        st.stop()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Leads evaluados", len(view))
    c2.metric("Uso ideal", f"{round((view['carrousel_status'] == 'Uso ideal').mean() * 100, 1):.1f}%")
    c3.metric("Uso parcial", f"{round((view['carrousel_status'] == 'Uso parcial').mean() * 100, 1):.1f}%")
    c4.metric("Incorrecto", f"{round((view['carrousel_status'] == 'Incorrecto').mean() * 100, 1):.1f}%")
    c5.metric("Cumplimiento", f"{round(((view['carrousel_status'] == 'Uso ideal') | (view['carrousel_status'] == 'Uso parcial')).mean() * 100, 1):.1f}%")

    st.subheader("Resumen por agente")
    summary_carrousel = (
        view.groupby("agent")
        .agg(
            leads=("lead_id", "nunique"),
            llamadas_con_numero=("num_calls_with_phone", "mean"),
            telefonos_unicos=("unique_origin_phones", "mean"),
            telefonos_esperados=("expected_unique_phones", "mean"),
            telefonos_unicos_primeras_3=("unique_origin_phones_first_3", "mean"),
            uso_ideal=("carrousel_status", lambda s: round((s == "Uso ideal").mean() * 100, 1)),
            uso_parcial=("carrousel_status", lambda s: round((s == "Uso parcial").mean() * 100, 1)),
            incorrecto=("carrousel_status", lambda s: round((s == "Incorrecto").mean() * 100, 1)),
        )
        .reset_index()
    )
    summary_carrousel["cumplimiento"] = (
        summary_carrousel["uso_ideal"] + summary_carrousel["uso_parcial"]
    ).round(1)

    summary_carrousel = summary_carrousel.sort_values("cumplimiento", ascending=False)
    st.dataframe(summary_carrousel, use_container_width=True, hide_index=True)

    st.subheader("Distribucion de estados")
    status_dist = (
        view["carrousel_status"]
        .value_counts(dropna=False)
        .rename_axis("estado")
        .reset_index(name="num_leads")
    )
    status_dist["porcentaje"] = (status_dist["num_leads"] / len(view) * 100).round(1)
    st.dataframe(status_dist, use_container_width=True, hide_index=True)

    st.subheader("Detalle por lead")
    detail_cols_carrousel = [
        "lead_id",
        "agent",
        "activity_year",
        "activity_month_name",
        "num_calls_with_phone",
        "unique_origin_phones",
        "expected_unique_phones",
        "unique_origin_phones_first_3",
        "has_outbound_call_with_phone",
        "carrousel_status",
        "first_3_phones_sequence",
        "phones_sequence",
    ]
    available_cols_carrousel = [c for c in detail_cols_carrousel if c in view.columns]
    st.dataframe(view[available_cols_carrousel], use_container_width=True, hide_index=True)
    st.stop()

# =========================
# PAGINA FLUJO
# =========================
milestones = build_milestones(df_filtered)

agents_flow = sorted(milestones["agent"].dropna().unique().tolist())

with st.sidebar:
    st.header("Filtros flujo")
    selected_agent_flow = st.selectbox(
        "Agente",
        ["Todos"] + agents_flow,
        key="selected_agent_flow"
    )

view = milestones if selected_agent_flow == "Todos" else milestones[milestones["agent"] == selected_agent_flow].copy()

if view.empty:
    st.warning("No hay leads para el filtro seleccionado.")
    st.stop()

view["call_1_within_limit"] = view["has_call_1"] & (view["call_1_delay_min"] <= max_call_1_min)
view["wpp_1_within_limit"] = view["has_wpp_1"] & (view["wpp_1_delay_min"] <= max_wpp_1_min)
view["call_2_within_limit"] = view["has_call_2"] & (view["call_2_delay_h"] <= max_call_2_h)
view["call_3_within_limit"] = view["has_call_3"] & (view["call_3_delay_h"] <= max_call_3_h)
view["wpp_2_within_limit"] = view["has_wpp_2"] & (view["wpp_2_delay_min"] <= max_wpp_2_min)
view["call_4_within_limit"] = view["has_call_4"] & (view["call_4_delay_h"] <= max_call_4_h)
view["wpp_3_within_limit"] = view["has_wpp_3"] & (view["wpp_3_delay_min"] <= max_wpp_3_min)

normalized_pct = round(view["was_normalized"].mean() * 100, 1) if len(view) else 0.0

c1, c2, c3 = st.columns(3)
c1.metric("Leads analizados", len(view))
c2.metric("Leads normalizados", f"{normalized_pct:.1f}%")
c3.metric("Agente", selected_agent_flow)

flow_metrics = {
    "Llamada 1": pct(view["has_call_1"]),
    "WhatsApp 1": pct(view["has_wpp_1"]),
    "Llamada 2": pct(view["has_call_2"]),
    "Llamada 3": pct(view["has_call_3"]),
    "WhatsApp 2": pct(view["has_wpp_2"]),
    "Llamada 4": pct(view["has_call_4"]),
    "WhatsApp 3": pct(view["has_wpp_3"]),
}

limit_metrics = {
    "Llamada 1": pct(view["call_1_within_limit"]),
    "WhatsApp 1": pct(view["wpp_1_within_limit"]),
    "Llamada 2": pct(view["call_2_within_limit"]),
    "Llamada 3": pct(view["call_3_within_limit"]),
    "WhatsApp 2": pct(view["wpp_2_within_limit"]),
    "Llamada 4": pct(view["call_4_within_limit"]),
    "WhatsApp 3": pct(view["wpp_3_within_limit"]),
}

st.subheader("Flujo alcanzado")
r1 = st.columns([1, 1, 1, 1])
with r1[0]:
    card("Llamada 1", f"{flow_metrics['Llamada 1']:.1f}%", "del total de leads")
with r1[1]:
    card("Llamada 2", f"{flow_metrics['Llamada 2']:.1f}%", "del total de leads")
with r1[2]:
    card("Llamada 3", f"{flow_metrics['Llamada 3']:.1f}%", "del total de leads")
with r1[3]:
    card("Llamada 4", f"{flow_metrics['Llamada 4']:.1f}%", "del total de leads")

r2 = st.columns([1, 1, 1, 1])
with r2[0]:
    card("WhatsApp 1", f"{flow_metrics['WhatsApp 1']:.1f}%", "del total de leads")
with r2[1]:
    st.write("")
with r2[2]:
    card("WhatsApp 2", f"{flow_metrics['WhatsApp 2']:.1f}%", "del total de leads")
with r2[3]:
    card("WhatsApp 3", f"{flow_metrics['WhatsApp 3']:.1f}%", "del total de leads")

st.subheader("Flujo dentro del limite configurado")
r3 = st.columns([1, 1, 1, 1])
with r3[0]:
    card("Llamada 1", f"{limit_metrics['Llamada 1']:.1f}%", f"<= {max_call_1_min} min")
with r3[1]:
    card("Llamada 2", f"{limit_metrics['Llamada 2']:.1f}%", f"<= {max_call_2_h} h")
with r3[2]:
    card("Llamada 3", f"{limit_metrics['Llamada 3']:.1f}%", f"<= {max_call_3_h} h")
with r3[3]:
    card("Llamada 4", f"{limit_metrics['Llamada 4']:.1f}%", f"<= {max_call_4_h} h")

r4 = st.columns([1, 1, 1, 1])
with r4[0]:
    card("WhatsApp 1", f"{limit_metrics['WhatsApp 1']:.1f}%", f"<= {max_wpp_1_min} min")
with r4[1]:
    st.write("")
with r4[2]:
    card("WhatsApp 2", f"{limit_metrics['WhatsApp 2']:.1f}%", f"<= {max_wpp_2_min} min")
with r4[3]:
    card("WhatsApp 3", f"{limit_metrics['WhatsApp 3']:.1f}%", f"<= {max_wpp_3_min} min")

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

    time_rows.append(
        {
            "Paso": step_name,
            "Leads que llegaron al paso": total_step,
            "Leads dentro de limite": int(within),
            "% dentro de limite": pct_within,
            "Limite aplicado": f"{limit_value} {unit}",
        }
    )


add_time_row("Llamada 1", "has_call_1", "call_1_delay_min", max_call_1_min, "min")
add_time_row("WhatsApp 1", "has_wpp_1", "wpp_1_delay_min", max_wpp_1_min, "min")
add_time_row("Llamada 2", "has_call_2", "call_2_delay_h", max_call_2_h, "h")
add_time_row("Llamada 3", "has_call_3", "call_3_delay_h", max_call_3_h, "h")
add_time_row("WhatsApp 2", "has_wpp_2", "wpp_2_delay_min", max_wpp_2_min, "min")
add_time_row("Llamada 4", "has_call_4", "call_4_delay_h", max_call_4_h, "h")
add_time_row("WhatsApp 3", "has_wpp_3", "wpp_3_delay_min", max_wpp_3_min, "min")

st.subheader("Cumplimiento temporal sobre los leads que si llegaron al paso")
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
    ],
    key="selected_step_flow"
)

step_map = {
    "Llamada 1": ("has_call_1", "call_1_delay_min", max_call_1_min),
    "WhatsApp 1": ("has_wpp_1", "wpp_1_delay_min", max_wpp_1_min),
    "Llamada 2": ("has_call_2", "call_2_delay_h", max_call_2_h),
    "Llamada 3": ("has_call_3", "call_3_delay_h", max_call_3_h),
    "WhatsApp 2": ("has_wpp_2", "wpp_2_delay_min", max_wpp_2_min),
    "Llamada 4": ("has_call_4", "call_4_delay_h", max_call_4_h),
    "WhatsApp 3": ("has_wpp_3", "wpp_3_delay_min", max_wpp_3_min),
}

exists_col, delay_col, limit_value = step_map[selected_step]
step_detail = view[view[exists_col] == True].copy()

if not step_detail.empty:
    step_detail["within_limit"] = step_detail[delay_col] <= limit_value
else:
    step_detail["within_limit"] = pd.Series(dtype=bool)

st.subheader(f"Detalle temporal · {selected_step}")
st.write(f"Mostrando solo leads que si llegaron a {selected_step.lower()}.")

detail_cols = [
    "lead_id",
    "agent",
    "activity_year",
    "activity_month_name",
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
summary_flow = (
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

st.dataframe(summary_flow, use_container_width=True, hide_index=True)
