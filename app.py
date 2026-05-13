import streamlit as st
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(layout="wide")

# -----------------------------------
# LOAD FINAL DATA
# -----------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("df_all.csv")

    df["date"] = pd.to_datetime(df["date"])

    return df.sort_values("date")


df_all = load_data()

# -----------------------------------
# SIDEBAR CONTROLS
# -----------------------------------
st.sidebar.header("Controls")

y_col = st.sidebar.selectbox(
    "Select metric",
    ["price", "cpi", "inflation_rate"]
)

# -----------------------------------
# METRIC LABELS
# -----------------------------------
metric_label = {
    "price": "Price",
    "cpi": "CPI",
    "inflation_rate": "Inflation (%)"
}

# -----------------------------------
# ITEM SELECT
# -----------------------------------
items = sorted(df_all["item"].dropna().unique())

item = st.sidebar.selectbox(
    "Select item",
    items
)

df_item = df_all[df_all["item"] == item].copy()

# -----------------------------------
# COLORS
# -----------------------------------
color_palette = [
    "#004876",
    "#FF671B",
    "#555759",
    "#FFC000",
    "#8FAAE5",
    "#D34600"
]

premises = sorted(df_all["premise"].dropna().unique())

premise_color = {
    p: color_palette[i % len(color_palette)]
    for i, p in enumerate(premises)
}

# -----------------------------------
# BRIDGE FUNCTION
# -----------------------------------
def get_bridges(dff, y_col):

    dff = dff.sort_values("date").reset_index(drop=True)

    is_nan = dff[y_col].isna()

    nan_start = is_nan & ~is_nan.shift(fill_value=False)
    nan_end = is_nan & ~is_nan.shift(-1, fill_value=False)

    starts = dff.index[nan_start]
    ends = dff.index[nan_end]

    bridges = []

    for s, e in zip(starts, ends):

        prev = dff.loc[:s-1].dropna(subset=[y_col])
        nxt = dff.loc[e+1:].dropna(subset=[y_col])

        if prev.empty or nxt.empty:
            continue

        prev_row = prev.iloc[-1]
        next_row = nxt.iloc[0]

        bridges.append((
            [prev_row["date"], next_row["date"]],
            [prev_row[y_col], next_row[y_col]]
        ))

    return bridges

# -----------------------------------
# PLOT
# -----------------------------------
fig = go.Figure()

for premise in premises:

    dff = df_item[df_item["premise"] == premise].copy()
    dff = dff.sort_values("date")

    color = premise_color[premise]

    # Main line
    fig.add_trace(
        go.Scatter(
            x=dff["date"],
            y=dff[y_col],
            mode="lines",
            name=premise,
            line=dict(color=color),
            legendgroup=premise
        )
    )

    # Missing-data bridges
    bridges = get_bridges(dff, y_col)

    bx, by = [], []

    for xseg, yseg in bridges:
        bx += list(xseg) + [None]
        by += list(yseg) + [None]

    fig.add_trace(
        go.Scatter(
            x=bx,
            y=by,
            mode="lines",
            line=dict(
                dash="dash",
                color=color
            ),
            showlegend=False,
            legendgroup=premise
        )
    )

# -----------------------------------
# REMARK
# -----------------------------------
fig.add_annotation(
    text="Remark: dashed line refers to periods with no observation.",
    xref="paper",
    yref="paper",
    x=0,
    y=-0.15,
    showarrow=False,
    align="left"
)

# -----------------------------------
# LAYOUT
# -----------------------------------
fig.update_layout(
    template="plotly_white",
    height=700,
    title=f"{metric_label[y_col]} across premises",
    xaxis=dict(
        title="Date",
        type="date"
    ),
    yaxis=dict(
        title=metric_label[y_col]
    ),
    legend_title="Premise Type"
)

# -----------------------------------
# RENDER
# -----------------------------------
st.plotly_chart(
    fig,
    use_container_width=True
)