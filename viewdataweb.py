import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime
import time

# Streamlit UI configuration
st.set_page_config(page_title="JSON Battery Data Analyzer", layout="wide")
st.title("📊 JSON Battery Data Analyzer")

# Reset button
if st.button("🔄 Reset App"):
    st.cache_data.clear()
    st.rerun()

# Main function
def main():
    uploaded_file = st.file_uploader("📂 Upload JSON File", type=["json"], key="main_file")

    if uploaded_file:
        with st.spinner("Processing data..."):
            time.sleep(1)
            data = load_json(uploaded_file)
            series_data = extract_series(data)

        tab1, tab2, tab3 = st.tabs(["📈 Data Visualization", "🔋 Battery Analysis", "🧮 Compression Analysis"])

        with tab1:
            visualize_data(series_data)

        with tab2:
            process_battery(series_data)

        with tab3:
            code = st.text_input("Enter access code for Compression Analysis:", type="password")
            if code == "1988":
                file_full = st.file_uploader("📂 Upload Full Data JSON", type=["json"], key="full")
                file_sample = st.file_uploader("📂 Upload Échantillonnage JSON", type=["json"], key="sample")
                if file_full and file_sample:
                    analyze_compression(file_full, file_sample)
            else:
                st.warning("Access code required.")
    else:
        st.info("Upload a JSON file to begin analysis.")

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
        if name and values:
            df = pd.DataFrame(values)
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
            fig.add_trace(go.Scatter(x=df["Timestamp"], y=df[name], mode="lines+markers", name=name,
                                     line=dict(color=colors.get(name, "gray"))))
    fig.update_layout(title=title, xaxis_title="Time", yaxis_title=y_label,
                      template="plotly_dark", hovermode="x unified")
    return fig

def visualize_data(series_data):
    st.subheader("🔋 Voltage Data")
    st.plotly_chart(plot_series(series_data, ["Voltage-Battery", "Voltage-Solar"],
                                "Voltage Trends", "Voltage (V)"), use_container_width=True)

    st.subheader("⚡ Current Data")
    st.plotly_chart(plot_series(series_data, ["Current-Battery", "Current-Solar"],
                                "Current Trends", "Current (A)"), use_container_width=True)

    if "UpTime" in series_data:
        st.subheader("⏳ Uptime")
        st.plotly_chart(plot_series(series_data, ["UpTime"], "System Uptime", "Uptime (s)"),
                        use_container_width=True)

def process_battery(series_data):
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
    lifecycle_percent = (remaining_cycles / total_cycles * 100).round(2) if total_cycles > 0 else 0

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Average DoD (%)", avg_dod)
        st.metric("Estimated Total Cycles", total_cycles)
        st.metric("Remaining Cycles", remaining_cycles)
        st.metric("Battery Lifecycle Remaining (%)", lifecycle_percent)

    with col2:
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=lifecycle_percent,
            title={"text": "Battery Life Remaining %"},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 20], 'color': "red"},
                    {'range': [20, 40], 'color': "orange"},
                    {'range': [40, 60], 'color': "yellow"},
                    {'range': [60, 80], 'color': "lightgreen"},
                    {'range': [80, 100], 'color': "green"}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': 20
                }
            }
        ))
        gauge_fig.update_layout(height=300, template="plotly_dark")
        st.plotly_chart(gauge_fig, use_container_width=True)

    st.subheader("Daily Depth of Discharge (DoD) Chart")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily['Date'], y=daily['DoD (%)'], name='DoD (%)', marker_color='red'))
    fig.update_layout(title="Daily Depth of Discharge", xaxis_title="Date", yaxis_title="DoD (%)", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(daily)

def analyze_compression(file_full, file_sample):
    full_data = load_json(file_full)
    sample_data = load_json(file_sample)
    full_series = extract_series(full_data)
    sample_series = extract_series(sample_data)

    keys = ["Voltage-Battery", "Current-Battery"]
    for idx, key in enumerate(keys):
        full_count = len(full_series.get(key, pd.DataFrame()))
        sample_count = len(sample_series.get(key, pd.DataFrame()))
        compression = 100 - round((sample_count / full_count) * 100, 2) if full_count else 100
        st.subheader(f"Compression Ratio for {key}")
        fig = go.Figure(go.Indicator(mode="gauge+number", value=compression,
                                     gauge={'axis': {'range': [0, 100]},
                                            'bar': {'color': "orange"}},
                                     title={'text': f"Compression %"}))
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True, key=f"compression_chart_{idx}")

    def get_lifecycle(series):
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

    full_remaining = get_lifecycle(full_series)
    sample_remaining = get_lifecycle(sample_series)
    abs_error = abs(full_remaining - sample_remaining)

    st.metric("Full Data Remaining Cycles", round(full_remaining, 2))
    st.metric("Sample Data Remaining Cycles", round(sample_remaining, 2))
    st.metric("Absolute Error", round(abs_error, 2))

if __name__ == "__main__":
    main()
