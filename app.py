import streamlit as st
import pandas as pd

st.set_page_config(page_title="Flujo de Leads Perdidos", layout="wide")

# =========================
# Configuración / helpers
# =========================

CALL_TYPES = {
    "Lead pendiente de llamar",
    "Llamada informativa",
    "Llamada de seguimiento",
    "Llamada comprometida",
}

WHATSAPP_TYPES = {
    "Whatsapp chat",
}


def classify_activity(value: str) -> str:
    if pd.isna(value):
        return "other"
    value = str(value).strip()
    if value in WHATSAPP_TYPES:
        return "whatsapp"
    if value in CALL_TYPES:
        return "call"
    return "other"


def mins_between(a, b):
    return (b - a).total_seconds() / 60.0


def hours_between(a, b):
    return (b - a).total_seconds() / 3600.0


def find_next_activity(df, start_time, activity_group):
    subset = df[
        (df["activity_group"] == activity_group)
        & (df["activity_completed_at"] >= start_time)
    ].sort_values("activity_completed_at")
    if subset.empty:
        return None
    return subset.iloc[0]


def in_window(value, target, tolerance):
    return (target - tolerance) <= value <= (target + tolerance)


def evaluate_lead(group, immediate_max_min, tol_90_min, tol_half_day_h, tol_day_half_h):
    group = group.sort_values("activity_completed_at").copy()

    lead_id = group["lead_id"].iloc[0]
    agent = group["agent"].iloc[0]
    created_at = group["lead_created_at"].iloc[0]

    result = {
        "lead_id": lead_id,
        "agent": agent,
        "lead_created_at": created_at,
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
    }

    # 1) Llamada 1 dentro de 5 min desde creación
    first_call = find_next_activity(group, created_at, "call")
    if first_call is None:
        result["fail_step"] = "Sin llamada 1"
        return result

    result["call_1_at"] = first_call["activity_completed_at"]
    delta_call_1 = mins_between(created_at, first_call["activity_completed_at"])
    if delta_call_1 <= 5:
        result["call_1_ok"] = True
    else:
        result["fail_step"] = "Llamada 1 fuera de 5 min"
        return result

    # 2) WhatsApp 1 inmediato tras llamada 1
    whatsapp_1 = find_next_activity(group, first_call["activity_completed_at"], "whatsapp")
    if whatsapp_1 is None:
        result["fail_step"] = "Sin WhatsApp 1"
        return result

    result["whatsapp_1_at"] = whatsapp_1["activity_completed_at"]
    delta_wpp_1 = mins_between(first_call["activity_completed_at"], whatsapp_1["activity_completed_at"])
    if 0 <= delta_wpp_1 <= immediate_max_min:
        result["whatsapp_1_ok"] = True
    else:
        result["fail_step"] = "WhatsApp 1 no inmediato"
        return result

    # 3) Llamada 2 ~ 90 min después de WhatsApp 1
    call_2 = find_next_activity(group, whatsapp_1["activity_completed_at"], "call")
    if call_2 is None:
        result["fail_step"] = "Sin llamada 2"
        return result

    result["call_2_at"] = call_2["activity_completed_at"]
    delta_call_2 = mins_between(whatsapp_1["activity_completed_at"], call_2["activity_completed_at"])
    if in_window(delta_call_2, 90, tol_90_min):
        result["call_2_ok"] = True
    else:
        result["fail_step"] = "Llamada 2 fuera de ventana 90 min"
        return result

    # 4) Llamada 3 ~ 0,5 días después de llamada 2
    call_3 = find_next_activity(group, call_2["activity_completed_at"], "call")
    if call_3 is None:
        result["fail_step"] = "Sin llamada 3"
        return result

    result["call_3_at"] = call_3["activity_completed_at"]
    delta_call_3_h = hours_between(call_2["activity_completed_at"], call_3["activity_completed_at"])
    if in_window(delta_call_3_h, 12, tol_half_day_h):
        result["call_3_ok"] = True
    else:
        result["fail_step"] = "Llamada 3 fuera de ventana 0,5 días"
        return result

    # 5) WhatsApp 2 inmediato tras llamada 3
    whatsapp_2 = find_next_activity(group, call_3["activity_completed_at"], "whatsapp")
    if whatsapp_2 is None:
        result["fail_step"] = "Sin WhatsApp 2"
        return result

    result["whatsapp_2_at"] = whatsapp_2["activity_completed_at"]
    delta_wpp_2 = mins_between(call_3["activity_completed_at"], whatsapp_2["activity_completed_at"])
    if 0 <= delta_wpp_2 <= immediate_max_min:
        result["whatsapp_2_ok"] = True
    else:
        result["fail_step"] = "WhatsApp 2 no inmediato"
        return result

    # 6) Llamada 4 ~ 1,5 días después de WhatsApp 2
    call_4 = find_next_activity(group, whatsapp_2["activity_completed_at"], "call")
    if call_4 is None:
        result["fail_step"] = "Sin llamada 4"
        return result

    result["call_4_at"] = call_4["activity_completed_at"]
    delta_call_4_h = hours_between(whatsapp_2["activity_completed_at"], call_4["activity_completed_at"])
    if in_window(delta_call_4_h, 36, tol_day_half_h):
        result["call_4_ok"] = True
    else:
        result["fail_step"] = "Llamada 4 fuera de ventana 1,5 días"
        return result

    # 7) WhatsApp 3 inmediato tras llamada 4
    whatsapp_3 = find_next_activity(group, call_4["activity_completed_at"], "whatsapp")
    if whatsapp_3 is None:
        result["fail_step"] = "Sin WhatsApp 3"
        return result

    result["whatsapp_3_at"] = whatsapp_3["activity_completed_at"]
    delta_wpp_3 = mins_between(call_4["activity_completed_at"], whatsapp_3["activity_completed_at"])
    if 0 <= delta_wpp_3 <= immediate_max_min:
        result["whatsapp_3_ok"] = True
    else:
        result["fail_step"] = "WhatsApp 3 no inmediato"
        return result

    result["full_flow_ok"] = True
    result["fail_step"] = "Cumple todo"
    return result


def build_results(df, immediate_max_min, tol_90_min, tol_half_day_h, tol_day_half_h):
    rows = []
    for _, group in df.groupby("lead_id", sort=False):
        rows.append(
            evaluate_lead(
                group,
                immediate_max_min=immediate_max_min,
                tol_90_min=tol_90_min,
                tol_half_day_h=tol_half_day_h,
                tol_day_half_h=tol_day_half_h,
            )
        )
    return pd.DataFrame(rows)


def pct(series):
    if len(series) == 0:
        return 0.0
    return round(series.mean() * 100, 1)


def render_box(label, percentage, subtitle=""):
    width = max(0, min(100, float(percentage)))
    return f"""
    <div style="width:180px;">
      <div style="
          border:2px solid #444;
          border-radius:8px;
          background:#f5f5f5;
          height:88px;
          position:relative;
          overflow:hidden;
          box-shadow: 0 1px 2px rgba(0,0,0,0.08);
      ">
        <div style="
            position:absolute;
            left:0; top:0; bottom:0;
            width:{width}%;
            background:#9fd3a8;
            opacity:0.9;
        "></div>
        <div style="
            position:relative;
            z-index:2;
            height:100%;
            display:flex;
            flex-direction:column;
            justify-content:center;
            align-items:center;
            font-family: sans-serif;
            text-align:center;
            padding:6px;
        ">
          <div style="font-size:16px; font-weight:700; color:#222;">{label}</div>
          <div style="font-size:22px; font-weight:800; color:#111;">{percentage:.1f}%</div>
          <div style="font-size:11px; color:#555;">{subtitle}</div>
        </div>
      </div>
    </div>
    """


def render_flow(metrics):
    html = f"""
    <div style="font-family:sans-serif;">
      <div style="margin-bottom:8px; font-size:18px; font-weight:700;">Flujo esperado</div>
      <div style="display:flex; align-items:flex-start; gap:22px; flex-wrap:wrap;">
        
        <div style="display:flex; flex-direction:column; gap:18px; align-items:center;">
          {render_box("Llamada 1", metrics["call_1_ok_pct"], "≤ 5 min desde creación")}
          {render_box("WhatsApp 1", metrics["whatsapp_1_ok_pct"], "inmediato")}
        </div>

        <div style="font-size:34px; padding-top:62px;">→</div>

        <div style="display:flex; flex-direction:column; gap:18px; align-items:center; padding-top:0px;">
          {render_box("Llamada 2", metrics["call_2_ok_pct"], "90 min")}
        </div>

        <div style="font-size:34px; padding-top:62px;">→</div>

        <div style="display:flex; flex-direction:column; gap:18px; align-items:center;">
          {render_box("Llamada 3", metrics["call_3_ok_pct"], "0,5 días")}
          {render_box("WhatsApp 2", metrics["whatsapp_2_ok_pct"], "inmediato")}
        </div>

        <div style="font-size:34px; padding-top:62px;">→</div>

        <div style="display:flex; flex-direction:column; gap:18px; align-items:center;">
          {render_box("Llamada 4", metrics["call_4_ok_pct"], "1,5 días")}
          {render_box("WhatsApp 3", metrics["whatsapp_3_ok_pct"], "inmediato")}
        </div>

      </div>

      <div style="margin-top:28px; max-width:260px;">
        {render_box("Cumple flujo completo", metrics["full_flow_ok_pct"], "lead perdido correctamente")}
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# =========================
# UI
# =========================

st.title("📞 Control de flujo de leads perdidos")
st.write(
    "Sube el Excel de actividades para comprobar, por agente, qué porcentaje de leads perdidos siguió el flujo correcto."
)

with st.sidebar:
    st.header("Parámetros")
    immediate_max_min = st.number_input(
        "Máximo minutos para considerar WhatsApp inmediato",
        min_value=0,
        max_value=60,
        value=10,
        step=1,
    )
    tol_90_min = st.number_input(
        "Tolerancia de la llamada 2 (minutos alrededor de 90)",
        min_value=0,
        max_value=180,
        value=30,
        step=5,
    )
    tol_half_day_h = st.number_input(
        "Tolerancia llamada 3 (horas alrededor de 12)",
        min_value=0,
        max_value=24,
        value=4,
        step=1,
    )
    tol_day_half_h = st.number_input(
        "Tolerancia llamada 4 (horas alrededor de 36)",
        min_value=0,
        max_value=48,
        value=8,
        step=1,
    )

uploaded_file = st.file_uploader("Sube el Excel", type=["xlsx"])

if not uploaded_file:
    st.info("Esperando archivo Excel.")
    st.stop()

try:
    raw = pd.read_excel(uploaded_file)
except Exception as exc:
    st.error(f"No se pudo leer el Excel: {exc}")
    st.stop()

required_cols = [
    "Negocio - ID",
    "Negocio - Negocio creado el",
    "Actividad - Hora en que se marcó como completada",
    "Negocio - Propietario",
    "Actividad - Tipo",
]

missing = [c for c in required_cols if c not in raw.columns]
if missing:
    st.error("Faltan columnas requeridas: " + ", ".join(missing))
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

if df.empty:
    st.warning("No hay datos válidos tras limpiar el archivo.")
    st.stop()

results = build_results(
    df,
    immediate_max_min=immediate_max_min,
    tol_90_min=tol_90_min,
    tol_half_day_h=tol_half_day_h,
    tol_day_half_h=tol_day_half_h,
)

agents = sorted(results["agent"].dropna().unique().tolist())
selected_agent = st.selectbox("Selecciona agente", ["Todos"] + agents)

view = results.copy()
if selected_agent != "Todos":
    view = view[view["agent"] == selected_agent].copy()

if view.empty:
    st.warning("No hay leads para el filtro seleccionado.")
    st.stop()

metrics = {
    "call_1_ok_pct": pct(view["call_1_ok"]),
    "whatsapp_1_ok_pct": pct(view["whatsapp_1_ok"]),
    "call_2_ok_pct": pct(view["call_2_ok"]),
    "call_3_ok_pct": pct(view["call_3_ok"]),
    "whatsapp_2_ok_pct": pct(view["whatsapp_2_ok"]),
    "call_4_ok_pct": pct(view["call_4_ok"]),
    "whatsapp_3_ok_pct": pct(view["whatsapp_3_ok"]),
    "full_flow_ok_pct": pct(view["full_flow_ok"]),
}

c1, c2, c3 = st.columns(3)
c1.metric("Leads analizados", f"{len(view):,}")
c2.metric("Cumplen flujo completo", f"{metrics['full_flow_ok_pct']:.1f}%")
c3.metric("Agente", selected_agent)

st.markdown("---")
render_flow(metrics)
st.markdown("---")

st.subheader("Resumen por agente")

summary = (
    results.groupby("agent", dropna=False)
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

st.subheader("Dónde fallan los leads")
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
    "call_3_at",
    "whatsapp_2_at",
    "call_4_at",
    "whatsapp_3_at",
]
st.dataframe(view[detail_cols], use_container_width=True, hide_index=True)
