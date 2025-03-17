
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timezone

import time
import json

# Streamlit UI configuration
st.set_page_config(page_title="JSON Battery Data Analyzer", layout="wide")
st.title("📊 JSON Battery Data Analyzer")

# Main function
def main():
    # File uploader for JSON files
    uploaded_file = st.file_uploader("📂 Upload JSON File", type=["json"])
    
    if uploaded_file:
        # Show a spinner while loading
        with st.spinner("⚡ Processing data... Please wait ⚡"):
            # Add a small delay to make the spinner visible
            time.sleep(1)
            
            # Process the uploaded file
            process_file(uploaded_file)
    else:
        st.info("Please upload a JSON file to begin the analysis.")
        st.write("This app analyzes battery and solar data from JSON format logs, visualizing voltage, current, and calculating battery health metrics.")

def process_file(uploaded_file):
    # Create tabs for different views
    viewer_tab, battery_tab = st.tabs(["📈 Data Visualization", "🔋 Battery Analysis"])
    
    # Load JSON data
    uploaded_file.seek(0)
    try:
        data = json.load(uploaded_file)
    except json.JSONDecodeError:
        st.error("Error: The uploaded file is not a valid JSON file.")
        return
    
    # Extract log data
    try:
        logs = data[0].get("Logs", [])
        if not logs:
            st.error("No logs found in the JSON data. Please check the file format.")
            return
    except (IndexError, AttributeError):
        st.error("Invalid JSON structure. Please check the file format.")
        return

    # Dictionary to store DataFrames for each data series
    series_data = {}

    # Process each series independently
    for log in logs:
        name = log.get("Name")
        values = log.get("Values", [])
        
        if not name or not values:
            continue

        # Ensure there is more than one entry before dropping the first one
        if len(values) > 1:
            values = values[1:]  # Drop the first entry

        # Convert to DataFrame
        series_df = pd.DataFrame(values)
        
        # Skip if DataFrame is empty or missing expected columns
        if series_df.empty or "T" not in series_df.columns or "V" not in series_df.columns:
            continue

        # Ensure correct timestamp formatting
        series_df["T"] = pd.to_datetime(series_df["T"])
        series_df.rename(columns={"T": "Timestamp", "V": name}, inplace=True)

        # Store the processed DataFrame
        series_data[name] = series_df

    # If no valid series were found
    if not series_data:
        st.error("No valid data series found in the JSON file.")
        return

    # Define color mapping
    color_mapping = {
        "Voltage-Battery": "red", "Voltage-Solar": "blue",
        "Current-Battery": "green", "Current-Solar": "orange",
        "UpTime": "purple"
    }

    # UI Switches for enabling/disabling series
    st.sidebar.header("🔘 Data Visibility")
    show_voltage_battery = st.sidebar.checkbox("Voltage-Battery", value=True)
    show_voltage_solar = st.sidebar.checkbox("Voltage-Solar", value=True)
    show_current_battery = st.sidebar.checkbox("Current-Battery", value=True)
    show_current_solar = st.sidebar.checkbox("Current-Solar", value=True)
    show_uptime = st.sidebar.checkbox("Show Uptime", value=True)

    # Function to plot multiple series in one graph
    def plot_series(series_names, title, y_label, visibility):
        fig = go.Figure()
        for name in series_names:
            if name in series_data and visibility[name]:
                df = series_data[name]
                fig.add_trace(go.Scatter(
                    x=df["Timestamp"], y=df[name], mode="lines+markers", name=name, 
                    line=dict(color=color_mapping.get(name, "gray"))
                ))

        fig.update_layout(
            title=title,
            xaxis_title="Time",
            yaxis_title=y_label,
            template="plotly_dark",
            hovermode="x unified"
        )
        return fig

    with viewer_tab:
        st.write("Visualization of Voltage, Current, and Uptime trends from your data.")
        
        # Voltage Graph
        st.subheader("🔋 Voltage Data (V)")
        voltage_fig = plot_series(
            ["Voltage-Battery", "Voltage-Solar"],
            "Voltage Trends",
            "Voltage (V)",
            {"Voltage-Battery": show_voltage_battery, "Voltage-Solar": show_voltage_solar}
        )
        st.plotly_chart(voltage_fig, use_container_width=True)

        # Current Graph
        st.subheader("⚡ Current Data (A)")
        current_fig = plot_series(
            ["Current-Battery", "Current-Solar"],
            "Current Trends",
            "Current (A)",
            {"Current-Battery": show_current_battery, "Current-Solar": show_current_solar}
        )
        st.plotly_chart(current_fig, use_container_width=True)

        # Uptime Graph
        if show_uptime and "UpTime" in series_data:
            st.subheader("⏳ Uptime (s)")
            uptime_fig = plot_series(
                ["UpTime"],
                "System Uptime",
                "Uptime (s)",
                {"UpTime": show_uptime}
            )
            st.plotly_chart(uptime_fig, use_container_width=True)

        # Show raw data if needed
        with st.expander("📄 View Raw Data"):
            for name, df in series_data.items():
                st.write(f"### {name}")
                st.dataframe(df)

    with battery_tab:
        st.header("🔋 Battery Analysis")

        voltage_battery_df = series_data.get("Voltage-Battery")
        
        if voltage_battery_df is not None:
            # Field to edit maximum charge voltage
            voltage_full_charge = st.number_input("Full Charge Voltage (V):", key="battery_voltage", value=13.0, step=0.1, format="%.1f")
            
            try:
                # Create DataFrame with date only (without time)
                voltage_battery_df_copy = voltage_battery_df.copy()
                
                # Convert timestamp to date
                voltage_battery_df_copy['Date'] = voltage_battery_df_copy["Timestamp"].dt.date
                
                # Group by date and calculate statistics
                daily_stats = voltage_battery_df_copy.groupby('Date').agg({
                    'Voltage-Battery': ['min', 'max', 'mean']
                }).reset_index()
                
                # Flatten the multi-index columns
                daily_stats.columns = ['Date', 'Min Voltage', 'Max Voltage', 'Avg Voltage']
                
                # Calculate Depth of Discharge (DoD) using the entered full charge voltage
                daily_stats['DoD (%)'] = ((voltage_full_charge - daily_stats['Min Voltage']) / voltage_full_charge * 100).round(2)
                
                # Calculate overall average DoD
                avg_dod = daily_stats['DoD (%)'].mean().round(2)
                
                # Calculate the number of valid days (for cycle counting)
                valid_days = len(daily_stats)
                
                # Calculate battery cycles using the formula y = -9x + 1180
                # where x is the average DoD
                total_cycles = -9 * avg_dod + 1180
                remaining_cycles = total_cycles - valid_days
                
                # Format the cycle numbers
                total_cycles = max(0, total_cycles.round(2))
                remaining_cycles = max(0, remaining_cycles.round(2))
                
                # Create a gauge chart to display average DoD
                st.subheader("Overall Battery Depth of Discharge")
                
                # Create two columns for better layout
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    # Create gauge chart for DoD
                    fig_gauge = go.Figure(go.Indicator(
                        mode="gauge+number+delta",
                        value=avg_dod,
                        domain={'x': [0, 1], 'y': [0, 1]},
                        title={'text': "Average DoD (%)"},
                        gauge={
                            'axis': {'range': [0, 100], 'tickwidth': 1},
                            'bar': {'color': "darkred"},
                            'steps': [
                                {'range': [0, 20], 'color': "green"},
                                {'range': [20, 40], 'color': "lightgreen"},
                                {'range': [40, 60], 'color': "yellow"},
                                {'range': [60, 80], 'color': "orange"},
                                {'range': [80, 100], 'color': "red"}
                            ],
                            'threshold': {
                                'line': {'color': "black", 'width': 4},
                                'thickness': 0.75,
                                'value': 80
                            }
                        }
                    ))
                    
                    fig_gauge.update_layout(
                        height=300,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(fig_gauge, use_container_width=True)
                
                with col2:
                    # Display key stats
                    st.markdown("### Key Statistics")
                    st.markdown(f"**Average DoD:** {avg_dod}%")
                    st.markdown(f"**Max DoD:** {daily_stats['DoD (%)'].max().round(2)}%")
                    st.markdown(f"**Min DoD:** {daily_stats['DoD (%)'].min().round(2)}%")
                    
                    # Battery health assessment based on DoD
                    if avg_dod < 30:
                        status = "Excellent"
                        color = "green"
                    elif avg_dod < 50:
                        status = "Good"
                        color = "lightgreen"
                    elif avg_dod < 70:
                        status = "Fair"
                        color = "yellow"
                    elif avg_dod < 85:
                        status = "Poor"
                        color = "orange"
                    else:
                        status = "Critical"
                        color = "red"
                    
                    st.markdown(f"**Battery Status:** <span style='color:{color};font-weight:bold'>{status}</span>", unsafe_allow_html=True)
                
                # Add a new section for battery cycles
                st.subheader("Battery Cycles Analysis")
                
                # Create two columns for the cycle gauges
                cycle_col1, cycle_col2 = st.columns(2)
                
                with cycle_col1:
                    # Create gauge chart for total cycles
                    fig_total_cycles = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=total_cycles,
                        domain={'x': [0, 1], 'y': [0, 1]},
                        title={'text': "Total Estimated Cycles"},
                        gauge={
                            'axis': {'range': [0, 1200], 'tickwidth': 1},
                            'bar': {'color': "blue"},
                            'steps': [
                                {'range': [0, 400], 'color': "lightgray"},
                                {'range': [400, 800], 'color': "gray"},
                                {'range': [800, 1200], 'color': "darkgray"}
                            ]
                        }
                    ))
                    
                    fig_total_cycles.update_layout(
                        height=300,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(fig_total_cycles, use_container_width=True)
                
                with cycle_col2:
                    # Create gauge chart for remaining cycles
                    # Determine color based on remaining cycles
                    if remaining_cycles > 800:
                        cycle_color = "green"
                    elif remaining_cycles > 500:
                        cycle_color = "lightgreen"
                    elif remaining_cycles > 300:
                        cycle_color = "yellow"
                    elif remaining_cycles > 100:
                        cycle_color = "orange"
                    else:
                        cycle_color = "red"
                        
                    fig_remaining_cycles = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=remaining_cycles,
                        domain={'x': [0, 1], 'y': [0, 1]},
                        title={'text': "Remaining Cycles"},
                        gauge={
                            'axis': {'range': [0, 1200], 'tickwidth': 1},
                            'bar': {'color': cycle_color},
                            'steps': [
                                {'range': [0, 100], 'color': "red"},
                                {'range': [100, 300], 'color': "orange"},
                                {'range': [300, 500], 'color': "yellow"},
                                {'range': [500, 800], 'color': "lightgreen"},
                                {'range': [800, 1200], 'color': "green"}
                            ],
                            'threshold': {
                                'line': {'color': "black", 'width': 4},
                                'thickness': 0.75,
                                'value': 100
                            }
                        }
                    ))
                    
                    fig_remaining_cycles.update_layout(
                        height=300,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(fig_remaining_cycles, use_container_width=True)
                
                # Display cycle information
                st.markdown("### Battery Cycle Information")
                st.markdown(f"**Formula Used:** Cycles = -9 × DoD + 1180")
                st.markdown(f"**Average DoD:** {avg_dod}%")
                st.markdown(f"**Total Estimated Cycles:** {total_cycles}")
                st.markdown(f"**Days with Valid Data:** {valid_days}")
                st.markdown(f"**Remaining Cycles:** {remaining_cycles}")
                
                # Battery lifecycle assessment
                lifecycle_percent = (remaining_cycles / total_cycles * 100).round(2) if total_cycles > 0 else 0
                st.markdown(f"**Battery Lifecycle Remaining:** {lifecycle_percent}%")
                
                # Display the DataFrame
                st.subheader("Daily Battery Analysis")
                st.dataframe(daily_stats)
                
                # DoD chart by day
                st.subheader("Daily Depth of Discharge (DoD) Chart")
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=daily_stats['Date'],
                    y=daily_stats['DoD (%)'],
                    name='DoD (%)',
                    marker_color='red'
                ))
                fig.update_layout(
                    title="Daily Depth of Discharge",
                    xaxis_title="Date",
                    yaxis_title="DoD (%)",
                    template="plotly_dark"
                )
                st.plotly_chart(fig, use_container_width=True)


               

                
try:
    st.subheader("🔌 Battery State of Health (SOH) - Coulomb Counting")
    
                    # Inputs from user
                    col1, col2, col3 = st.columns(3)
    
                    with col1:
                        nominal_capacity = st.number_input(
                            "Nominal Battery Capacity (Ah):",
                            value=33.0,
                            min_value=1.0,
                            step=0.1,
                            help="Enter the original nominal capacity (Ah) of your battery."
                        )
    
                    with col2:
                        t1_date = st.date_input(
                            "Integration Start Date (t1):",
                            value=voltage_battery_df["Timestamp"].min().date()
                        )
    
                    with col3:
                        t2_date = st.date_input(
                            "Integration End Date (t2):",
                            value=voltage_battery_df["Timestamp"].max().date()
                        )
    
                    # Timestamps UTC explícitos
                    t1 = pd.Timestamp(datetime.combine(t1_date, datetime.min.time()), tz='UTC')
                    t2 = pd.Timestamp(datetime.combine(t2_date, datetime.max.time()), tz='UTC')
    
                    # Asegúrate que el DataFrame esté disponible
                    current_battery_df = series_data.get("Current-Battery")
    
                    if current_battery_df is not None:
                        mask = (current_battery_df["Timestamp"] >= t1) & (current_battery_df["Timestamp"] <= t2)
                        integration_df = current_battery_df.loc[mask]
    
                        if integration_df.empty:
                            st.warning("No Current-Battery data within selected time range.")
                        else:
                            integration_df = integration_df.sort_values(by="Timestamp")
                            integration_df['Time_diff'] = integration_df['Timestamp'].diff().dt.total_seconds().fillna(0) / 3600
                            integration_df['Capacity'] = integration_df['Current-Battery'] * integration_df['Time_diff']
    
                            actual_capacity = abs(integration_df['Capacity'].sum())
                            soh_percent = (actual_capacity / nominal_capacity) * 100
    
                            # SOH Result Display
                            st.markdown("### 🔋 Battery SOH Result")
                            st.metric(
                                label="Estimated SOH (%)",
                                value=f"{soh_percent:.2f}%",
                                delta=f"Actual Capacity: {actual_capacity:.2f} Ah"
                            )
    
                            # Gauge Chart SOH
                            fig_soh = go.Figure(go.Indicator(
                                mode="gauge+number",
                                value=soh_percent,
                                title={'text': "Battery SOH (%)"},
                                gauge={
                                    'axis': {'range': [0, 100]},
                                    'bar': {'color': "cyan"},
                                    'steps': [
                                        {'range': [0, 50], 'color': "red"},
                                        {'range': [50, 70], 'color': "orange"},
                                        {'range': [70, 85], 'color': "yellow"},
                                        {'range': [85, 100], 'color': "green"}
                                    ],
                                    'threshold': {
                                        'line': {'color': "black", 'width': 4},
                                        'thickness': 0.75,
                                        'value': 80
                                    }
                                }
                            ))
    
                            fig_soh.update_layout(height=300, template="plotly_dark")
                            st.plotly_chart(fig_soh, use_container_width=True)
    
                            # Explanation
                            st.markdown("""
                            **How SOH is Calculated:**
                            - Integrates battery current over the period (`t1` to `t2`).
                            - Compares the resulting capacity (Ah) against the nominal battery capacity.
                            - Displays SOH as the remaining battery health percentage.
                            """)
    
                    else:
                        st.error("Current-Battery data not found in the uploaded JSON.")
except Exception as e:
    st.error(f"Error in SOH Calculation: {str(e)}")





                st.subheader("🔌 Battery State of Health (SOH) - Coulomb Counting")

                # Inputs from user
                col1, col2, col3 = st.columns(3)

                with col1:
                    nominal_capacity = st.number_input(
                        "Nominal Battery Capacity (Ah):",
                        value=33.0,
                        min_value=1.0,
                        step=0.1,
                        help="Enter the original nominal capacity (Ah) of your battery."
                    )

                with col2:
                    t1_date = st.date_input(
                        "Integration Start Date (t1):",
                        value=voltage_battery_df["Timestamp"].min().date()
                    )

                with col3:
                    t2_date = st.date_input(
                        "Integration End Date (t2):",
                        value=voltage_battery_df["Timestamp"].max().date()
                    )

                # Timestamps UTC explícitos
                t1 = pd.Timestamp(datetime.combine(t1_date, datetime.min.time()), tz='UTC')
                t2 = pd.Timestamp(datetime.combine(t2_date, datetime.max.time()), tz='UTC')

                # Asegúrate que el DataFrame esté disponible
                current_battery_df = series_data.get("Current-Battery")

                if current_battery_df is not None:
                    mask = (current_battery_df["Timestamp"] >= t1) & (current_battery_df["Timestamp"] <= t2)
                    integration_df = current_battery_df.loc[mask]

                    if integration_df.empty:
                        st.warning("No Current-Battery data within selected time range.")
                    else:
                        integration_df = integration_df.sort_values(by="Timestamp")
                        integration_df['Time_diff'] = integration_df['Timestamp'].diff().dt.total_seconds().fillna(0) / 3600
                        integration_df['Capacity'] = integration_df['Current-Battery'] * integration_df['Time_diff']

                        actual_capacity = abs(integration_df['Capacity'].sum())
                        soh_percent = (actual_capacity / nominal_capacity) * 100

                        # SOH Result Display
                        st.markdown("### 🔋 Battery SOH Result")
                        st.metric(
                            label="Estimated SOH (%)",
                            value=f"{soh_percent:.2f}%",
                            delta=f"Actual Capacity: {actual_capacity:.2f} Ah"
                        )

                        # Gauge Chart SOH
                        fig_soh = go.Figure(go.Indicator(
                            mode="gauge+number",
                            value=soh_percent,
                            title={'text': "Battery SOH (%)"},
                            gauge={
                                'axis': {'range': [0, 100]},
                                'bar': {'color': "cyan"},
                                'steps': [
                                    {'range': [0, 50], 'color': "red"},
                                    {'range': [50, 70], 'color': "orange"},
                                    {'range': [70, 85], 'color': "yellow"},
                                    {'range': [85, 100], 'color': "green"}
                                ],
                                'threshold': {
                                    'line': {'color': "black", 'width': 4},
                                    'thickness': 0.75,
                                    'value': 80
                                }
                            }
                        ))

                        fig_soh.update_layout(height=300, template="plotly_dark")
                        st.plotly_chart(fig_soh, use_container_width=True)

                        # Explanation
                        st.markdown("""
                        **How SOH is Calculated:**
                        - Integrates battery current over the period (`t1` to `t2`).
                        - Compares the resulting capacity (Ah) against the nominal battery capacity.
                        - Displays SOH as the remaining battery health percentage.
                        """)

                else:
                    st.error("Current-Battery data not found in the uploaded JSON.")

if __name__ == "__main__":
    main()