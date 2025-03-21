import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime, timezone
import time

# Streamlit UI configuration
st.set_page_config(page_title="JSON Battery Data Analyzer", layout="wide")
st.title("\ud83d\udcca JSON Battery Data Analyzer")

# Reset button
if st.button("\ud83d\udd04 Reset App"):
    st.experimental_rerun()

# Main function
def main():
    tab1, tab2, tab3 = st.tabs(["\ud83d\udcc8 Data Visualization", "\ud83d\udd0b Battery Analysis", "\ud83d\udd22 Compression Analysis"])

    with tab1:
        json_file = st.file_uploader("\ud83d\udcc2 Upload JSON File", type=["json"])
        if json_file:
            with st.spinner("Processing data..."):
                time.sleep(1)
                process_file(json_file)
        else:
            st.info("Upload a JSON file to begin analysis.")

    with tab2:
        json_file = st.file_uploader("\ud83d\udcc2 Upload JSON File for Battery Analysis", type=["json"], key="battery_file")
        if json_file:
            with st.spinner("Analyzing battery..."):
                process_battery(json_file)

    with tab3:
        code = st.text_input("Enter access code for Compression Analysis:", type="password")
        if code == "1988":
            file_full = st.file_uploader("Upload Full Data JSON", type=["json"], key="full")
            file_sample = st.file_uploader("Upload Échantillonnage JSON", type=["json"], key="sample")
            if file_full and file_sample:
                analyze_compression(file_full, file_sample)
        else:
            st.warning("Access code required.")

# Utility functions

def load_json(uploaded_file):
    uploaded_file.seek(0)
    return json.load(uploaded_file)

def extract_series(data):
    logs = data[0].get("Logs", [])
    series_data = {}
    for log in logs:
        name = log.get("Name")
        values = log.get("Values", [])
        if name and values and len(values) > 1:
            df = pd.DataFrame(values[1:])
            df["T"] = pd.to_datetime(df["T"])
            df.rename(columns={"T": "Timestamp", "V": name}, inplace=True)
            series_data[name] = df
    return series_data

def plot_series(series_data, names, title, y_label):
    fig = go.Figure()
    colors = {"Voltage-Battery": "red", "Voltage-Solar": "blue",
              "Current-Battery": "green", "Current-Solar": "orange", "UpTime": "purple"}
    for name in names:
        if name in series_data:
            df = series_data[name]
            fig.add_trace(go.Scatter(x=df["Timestamp"], y=df[name], mode="lines", name=name,
                                     line=dict(color=colors.get(name, "gray"))))
    fig.update_layout(title=title, xaxis_title="Time", yaxis_title=y_label,
                      template="plotly_dark", hovermode="x unified")
    return fig

def process_file(uploaded_file):
    data = load_json(uploaded_file)
    series_data = extract_series(data)

    st.subheader("\ud83d\udd0b Voltage Data")
    st.plotly_chart(plot_series(series_data, ["Voltage-Battery", "Voltage-Solar"],
                                "Voltage Trends", "Voltage (V)"), use_container_width=True)

    st.subheader("\u26a1 Current Data")
    st.plotly_chart(plot_series(series_data, ["Current-Battery", "Current-Solar"],
                                "Current Trends", "Current (A)"), use_container_width=True)

    if "UpTime" in series_data:
        st.subheader("\u23f3 Uptime")
        st.plotly_chart(plot_series(series_data, ["UpTime"], "System Uptime", "Uptime (s)"),
                        use_container_width=True)

def process_battery(uploaded_file):
    data = load_json(uploaded_file)
    series_data = extract_series(data)
    voltage_df = series_data.get("Voltage-Battery")
    if voltage_df is None:
        st.error("Voltage-Battery data missing.")
        return

    voltage_full_charge = st.number_input("Full Charge Voltage (V):", value=13.0, step=0.1, format="%.1f")
    voltage_df["Date"] = voltage_df["Timestamp"].dt.date
    daily = voltage_df.groupby("Date").agg({"Voltage-Battery": ["min"]}).reset_index()
    daily.columns = ["Date", "Min Voltage"]
    daily["DoD (%)"] = ((voltage_full_charge - daily["Min Voltage"]) / voltage_full_charge * 100).round(2)
    avg_dod = daily["DoD (%)"].mean().round(2)
    total_cycles = max(0, round(0.0622*avg_dod**2 - 19.599*avg_dod + 1461.6, 2))
    remaining_cycles = max(0, round(total_cycles - len(daily), 2))
    st.metric("Average DoD (%)", avg_dod)
    st.metric("Estimated Total Cycles", total_cycles)
    st.metric("Remaining Cycles", remaining_cycles)


def analyze_compression(file_full, file_sample):
    full_data = load_json(file_full)
    sample_data = load_json(file_sample)
    full_series = extract_series(full_data)
    sample_series = extract_series(sample_data)

    for key in ["Voltage-Battery", "Current-Battery"]:
        full_count = len(full_series.get(key, pd.DataFrame()))
        sample_count = len(sample_series.get(key, pd.DataFrame()))
        compression = 100 - round((sample_count / full_count) * 100, 2) if full_count else 100
        st.subheader(f"Compression Ratio for {key}")
        fig = go.Figure(go.Indicator(mode="gauge+number", value=compression,
                                     gauge={'axis': {'range': [0, 100]},
                                            'bar': {'color': "orange"}},
                                     title={'text': f"Compression %"}))
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # Battery Lifecycle Remaining
    def get_lifecycle(data):
        series = extract_series(data)
        voltage_df = series.get("Voltage-Battery")
        if voltage_df is None:
            return 0
        voltage_df["Date"] = voltage_df["Timestamp"].dt.date
        daily = voltage_df.groupby("Date").agg({"Voltage-Battery": ["min"]}).reset_index()
        daily.columns = ["Date", "Min Voltage"]
        dod = ((13.0 - daily["Min Voltage"]) / 13.0 * 100).round(2)
        avg_dod = dod.mean().round(2)
        total_cycles = max(0, round(0.0622*avg_dod**2 - 19.599*avg_dod + 1461.6, 2))
        return total_cycles - len(daily)

    full_remaining = get_lifecycle(full_data)
    sample_remaining = get_lifecycle(sample_data)
    abs_error = abs(full_remaining - sample_remaining)

    st.metric("Full Data Remaining Cycles", round(full_remaining, 2))
    st.metric("Sample Data Remaining Cycles", round(sample_remaining, 2))
    st.metric("Absolute Error", round(abs_error, 2))

if __name__ == "__main__":
    main()
