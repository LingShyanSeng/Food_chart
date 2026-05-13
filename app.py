import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import os

st.set_page_config(layout="wide")

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
# METADATA
# -----------------------------------
metadata = {
    "premise": pd.read_csv("metadata/metadata_premise.csv"),
    "item": pd.read_csv("metadata/metadata_item.csv")
}

metadata["premise"]["premise_type"] = (
    metadata["premise"]["premise_type"].str.strip()
)

id_cols = ["item_code", "item", "unit", "item_group", "item_category"]

# -----------------------------------
# PREMISE LIST
# -----------------------------------
premise_types = [
    "Pasar Mini",
    "Pasar Raya / Supermarket",
    "Kedai Runcit",
    "Pasar Basah",
    "Hypermarket",
    "Restoran Melayu",
    "Restoran India Muslim",
    "Restoran Cina",
    "Medan Selera",
    "Foodcourt",
    "Borong",
    "Kedai Serbaneka"
]

color_palette = [
    "#004876", "#FF671B", "#555759",
    "#FFC000", "#8FAAE5", "#D34600"
]

premise_color = {
    p: color_palette[i % len(color_palette)]
    for i, p in enumerate(premise_types)
}

# -----------------------------------
# ITEM SELECT (SIDEBAR)
# -----------------------------------
# temporary df_all placeholder (defined later, so we compute items after load)
# -----------------------------------

def safe_folder_name(name):
    return name.replace("/", "_").replace("\\", "_").strip()


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
# LOAD TIME SERIES
# -----------------------------------
@st.cache_data
def load_time_series(base_path, prefix):
    dfs = []

    for year in range(2022, 2027):
        for month in range(1, 13):

            file_path = f"{base_path}/{year}/{prefix}_{year}-{month:02d}.csv"

            if not os.path.exists(file_path):
                continue

            df = pd.read_csv(file_path)
            df = df.set_index(id_cols)
            dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, axis=1).reset_index()


# -----------------------------------
# LOAD ALL DATA
# -----------------------------------
@st.cache_data
def load_all():
    premise_data = {}

    for premise in premise_types:

        folder = safe_folder_name(premise)

        price_path = f"premise_type/{folder}/time_series/price"
        count_path = f"premise_type/{folder}/time_series/count"

        df_price = load_time_series(price_path, "price")

        premise_data[premise] = df_price

    food_list = pd.read_csv("lookup_item(in).csv")

    included_items = (
        food_list.loc[food_list["To include"] == "Y", "item_code"]
        .dropna()
        .unique()
    )

    filtered = {}

    for premise, df in premise_data.items():
        df = df[df["item_code"].isin(included_items)]
        filtered[premise] = df

    long_data = {}

    for premise, df in filtered.items():

        date_cols = df.columns.difference(id_cols)

        long_df = df.melt(
            id_vars=id_cols,
            value_vars=date_cols,
            var_name="date",
            value_name="price"
        )

        long_df["date"] = pd.to_datetime(long_df["date"], errors="coerce")

        long_data[premise] = long_df

    return long_data


long_data = load_all()

# -----------------------------------
# BUILD PANEL
# -----------------------------------
premise_monthly_prices = {}

for premise, df in long_data.items():

    df = df.sort_values(["item_code", "date"])

    grouped = (
        df.groupby([
            "item_code",
            "item",
            "unit",
            "item_category",
            "item_group",
            pd.Grouper(key="date", freq="W")
        ])["price"]
        .mean()
        .reset_index()
    )

    grouped["base_price"] = grouped.groupby("item_code")["price"].transform(
        lambda x: x.dropna().iloc[0] if x.notna().any() else None
    )

    grouped["cpi"] = grouped["price"] / grouped["base_price"]

    grouped = grouped.sort_values(["item_code", "date"])

    grouped["inflation_rate"] = (
        grouped.groupby("item_code")["cpi"].pct_change() * 100
    )

    premise_monthly_prices[premise] = grouped


df_all = pd.concat(
    [df.assign(premise=p) for p, df in premise_monthly_prices.items()],
    ignore_index=True
)

df_all = df_all.sort_values("date")

items = sorted(df_all["item"].dropna().unique())

# -----------------------------------
# SIDEBAR ITEM SELECT
# -----------------------------------
item = st.sidebar.selectbox("Select item", items)

df_item = df_all[df_all["item"] == item].copy()

# -----------------------------------
# COLOR MAP
# -----------------------------------
premises = sorted(df_all["premise"].unique())

premise_color = {
    p: color_palette[i % len(color_palette)]
    for i, p in enumerate(premises)
}

# -----------------------------------
# PLOT
# -----------------------------------
fig = go.Figure()

for premise in premises:

    dff = df_item[df_item["premise"] == premise].copy()
    dff = dff.sort_values("date")

    color = premise_color[premise]

    # MAIN LINE
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

    # BRIDGES
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
            line=dict(dash="dash", color=color),
            showlegend=False,
            legendgroup=premise
        )
    )

fig.add_annotation(
    text=(
        "Dashed lines = no observations (data gaps bridged)<br>"
        "CPI base = first week's price per item per premise"
    ),
    xref="paper",
    yref="paper",
    x=0,
    y=0.35,
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
    xaxis=dict(title="Date", type="date"),
    yaxis=dict(title=metric_label[y_col]),
    legend_title="Premise Type"
)

# -----------------------------------
# RENDER
# -----------------------------------
st.plotly_chart(fig, use_container_width=True)