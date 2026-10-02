import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import io

# Set page config
st.set_page_config(
    page_title="⚡ Electricity Consumption Analyzer Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #ff6b6b, #4ecdc4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #4ecdc4;
    }
    .stTab {
        padding-top: 1.5rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Title and description
st.markdown('<h1 class="main-header">⚡ Electricity Consumption Analyzer Pro</h1>', unsafe_allow_html=True)
st.markdown("""
<div style='text-align: center; margin-bottom: 2rem; color: #666;'>
    Advanced interactive analytics for interval meter readings • Real-time cost analysis • Anomaly detection • Consumption patterns
</div>
""", unsafe_allow_html=True)

def process_uci_format(df_raw):
    """Process the UCI Household Power Consumption dataset format"""
    try:
        # Check if this looks like UCI format
        expected_columns = ['Date', 'Time', 'Global_active_power', 'Global_reactive_power',
                           'Voltage', 'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3']

        # Check if we have the expected columns (case-insensitive)
        df_cols_lower = [col.strip().lower() for col in df_raw.columns]
        expected_lower = [col.lower() for col in expected_columns]

        # If it's semicolon separated and has the right columns, process as UCI format
        if len(df_raw.columns) >= 8 and all(any(exp in col for col in df_cols_lower) for exp in expected_lower[:2]):
            # Read with proper handling of missing values
            df_processed = df_raw.copy()

            # Combine Date and Time into timestamp
            df_processed['timestamp'] = pd.to_datetime(
                df_processed['Date'] + ' ' + df_processed['Time'],
                format='%d/%m/%Y %H:%M:%S',
                errors='coerce'
            )

            # Define power columns (sub-metering as departments)
            power_columns = ['Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3']
            # Also consider Global_active_power as a total option

            # Melt the data to long format: each row is a timestamp-department combination
            df_melted = []

            for _, row in df_processed.iterrows():
                if pd.isna(row['timestamp']):
                    continue

                timestamp = row['timestamp']

                # Add each sub-metering as a department
                for i, col in enumerate(power_columns, 1):
                    if col in df_processed.columns and not pd.isna(row[col]) and row[col] != '?':
                        try:
                            power_val = float(row[col])
                            df_melted.append({
                                'timestamp': timestamp,
                                'department': f'Sub_metering_{i}',
                                'power_kW': power_val
                            })
                        except (ValueError, TypeError):
                            continue

                # Optionally add Global_active_power as a "Total" department
                if 'Global_active_power' in df_processed.columns and not pd.isna(row['Global_active_power']) and row['Global_active_power'] != '?':
                    try:
                        power_val = float(row['Global_active_power'])
                        df_melted.append({
                            'timestamp': timestamp,
                            'department': 'Total_Consumption',
                            'power_kW': power_val
                        })
                    except (ValueError, TypeError):
                        pass

            if df_melted:
                result_df = pd.DataFrame(df_melted)
                # Sort by timestamp for consistency
                result_df = result_df.sort_values('timestamp').reset_index(drop=True)
                return result_df
            else:
                return None
        else:
            return None
    except Exception:
        return None

# Sidebar for controls
with st.sidebar:
    st.markdown("## ⚙️ Control Panel")

    # File upload
    uploaded_file = st.file_uploader(
        "📤 Upload CSV with meter readings",
        type=['csv', 'txt'],
        help="CSV/TXT should contain timestamp, department tags, and power consumption (kW or kWh). Supports UCI household power consumption format."
    )

    # Tariff settings
    st.markdown("### 💰 Tariff Settings")
    base_rate = st.number_input(
        "Base rate ($/kWh)",
        min_value=0.0,
        value=0.12,
        step=0.01,
        help="Base electricity rate per kWh"
    )

    use_tod_rates = st.checkbox(
        "⏰ Use Time-of-Day rates",
        value=False,
        help="Enable different rates for peak/off-peak hours"
    )

    if use_tod_rates:
        col1, col2 = st.columns(2)
        with col1:
            peak_rate = st.number_input(
                "Peak rate ($/kWh)",
                min_value=0.0,
                value=0.18,
                step=0.01
            )
            peak_start = st.slider(
                "Peak start",
                min_value=0,
                max_value=23,
                value=17,
                format="%d:00"
            )
        with col2:
            off_peak_rate = st.number_input(
                "Off-peak rate ($/kWh)",
                min_value=0.0,
                value=0.08,
                step=0.01
            )
            peak_end = st.slider(
                "Peak end",
                min_value=0,
                max_value=23,
                value=21,
                format="%d:00"
            )

    # Anomaly detection settings
    st.markdown("### 🚨 Anomaly Detection")
    window_size = st.slider(
        "📊 Rolling window (hours)",
        min_value=1,
        max_value=168,  # 1 week
        value=24,
        help="Window size for rolling average calculation"
    )
    z_threshold = st.slider(
        "📈 Z-score threshold",
        min_value=1.0,
        max_value=5.0,
        value=2.5,
        step=0.1,
        help="Number of standard deviations for anomaly detection"
    )

    # Sample data option
    st.markdown("### 📊 Sample Data")
    use_sample = st.checkbox("Use sample data (UCI Power Dataset)", value=False)

    if use_sample:
        if st.button("🔄 Load Sample Data", type="primary"):
            # Generate sample data similar to UCI dataset
            np.random.seed(42)
            dates = pd.date_range(start='2023-01-01', end='2023-01-14', freq='h')
            n_hours = len(dates)

            # Simulate 5 departments
            departments = ['Lighting', 'HVAC', 'Machinery', 'IT_Systems', 'Utilities']

            # Create DataFrame
            data = []
            for dept in departments:
                # Base consumption pattern with daily and weekly cycles
                base_load = np.random.uniform(10, 50)  # kW base load
                daily_pattern = np.sin(np.arange(n_hours) * 2 * np.pi / 24) * 0.3 + 1
                weekly_pattern = np.sin(np.arange(n_hours) * 2 * np.pi / (24*7)) * 0.2 + 1
                noise = np.random.normal(1, 0.1, n_hours)

                consumption = base_load * daily_pattern * weekly_pattern * noise
                consumption = np.maximum(consumption, 0)  # No negative consumption

                for i, (timestamp, cons) in enumerate(zip(dates, consumption)):
                    data.append({
                        'timestamp': timestamp,
                        'department': dept,
                        'power_kW': cons,
                        # Add some random tags for variety
                        'area': np.random.choice(['North', 'South', 'East', 'West']),
                        'equipment_type': np.random.choice(['Primary', 'Secondary', 'Backup'])
                    })

            df = pd.DataFrame(data)
            st.session_state['data'] = df
            st.success("✅ Sample data loaded!")
            st.balloons()

# Initialize session state
if 'data' not in st.session_state:
    st.session_state['data'] = None
if 'processed_data' not in st.session_state:
    st.session_state['processed_data'] = None

# Main application logic
if uploaded_file is not None or (st.session_state['data'] is not None and len(st.session_state['data']) > 0):
    try:
        # Load data
        if uploaded_file is not None:
            # First, try to read the file to see its format
            # Try different separators and encodings
            try:
                # Try semicolon first (UCI format)
                df_raw = pd.read_csv(uploaded_file, sep=';', low_memory=False)
                # Check if this looks like UCI format
                if 'Date' in df_raw.columns and 'Time' in df_raw.columns and 'Global_active_power' in df_raw.columns:
                    st.info("🔍 Detected UCI Household Power Consumption format. Processing...")
                    df = process_uci_format(df_raw)
                    if df is not None:
                        st.session_state['data'] = df
                        st.success("✅ UCI format processed successfully!")
                    else:
                        st.error("❌ Failed to process UCI format. Trying standard CSV reading...")
                        # Reset file pointer and try standard CSV
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file)
                        st.session_state['data'] = df
                else:
                    # Not UCI format, try standard CSV
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file)
                    st.session_state['data'] = df
            except Exception as e:
                # If semicolon fails, try comma
                uploaded_file.seek(0)
                try:
                    df = pd.read_csv(uploaded_file)
                    st.session_state['data'] = df
                except Exception:
                    st.error(f"❌ Could not read file. Please ensure it's a valid CSV or UCI format text file.")
                    st.stop()
        else:
            df = st.session_state['data']

        # Display data info with metrics
        st.markdown("## 📋 Data Overview")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("📊 Total Records", f"{len(df):,}")
        with col2:
            if 'timestamp' in df.columns:
                date_range = f"{pd.to_datetime(df['timestamp']).min().strftime('%b %d')} to {pd.to_datetime(df['timestamp']).max().strftime('%b %d, %Y')}"
            else:
                date_range = "N/A"
            st.metric("📅 Date Range", date_range)
        with col3:
            dept_count = df['department'].nunique() if 'department' in df.columns else "N/A"
            st.metric("🏭 Departments", dept_count)
        with col4:
            if 'power_kW' in df.columns or any(x in df.columns.str.lower() for x in ['power', 'kwh', 'kw']):
                power_col_guess = [col for col in df.columns if any(x in col.lower() for x in ['power', 'kwh', 'kw', 'consumption'])]
                if power_col_guess:
                    avg_power = df[power_col_guess[0]].mean()
                    st.metric("⚡ Avg Power", f"{avg_power:.1f} kW")
                else:
                    st.metric("⚡ Avg Power", "N/A")
            else:
                st.metric("⚡ Avg Power", "N/A")
        with col5:
            st.metric("🔢 Columns", len(df.columns))

        # Show data preview with styling
        with st.expander("👀 View Raw Data Sample", expanded=False):
            st.dataframe(
                df.head(100),
                use_container_width=True,
                height=300
            )

        # Data preprocessing section
        st.markdown("## 🔧 Data Configuration")

        col1, col2, col3 = st.columns(3)

        with col1:
            # Timestamp column selection
            timestamp_cols = [col for col in df.columns if 'time' in col.lower() or 'date' in col.lower()]
            if timestamp_cols:
                timestamp_col = st.selectbox("🕒 Timestamp column", timestamp_cols, index=0)
            else:
                # If no obvious timestamp column, let user choose
                timestamp_col = st.selectbox("🕒 Timestamp column", df.columns.tolist())

        with col2:
            # Power/consumption column selection
            power_cols = [col for col in df.columns if any(x in col.lower() for x in ['power', 'kwh', 'kw', 'consumption', 'usage'])]
            if power_cols:
                power_col = st.selectbox("⚡ Power column", power_cols, index=0)
            else:
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if numeric_cols:
                    power_col = st.selectbox("⚡ Power column", numeric_cols, index=0)
                else:
                    st.error("❌ No numeric columns found for power consumption")
                    st.stop()

        with col3:
            # Department column selection
            dept_cols = [col for col in df.columns if 'dept' in col.lower() or 'area' in col.lower() or 'zone' in col.lower() or 'department' in col.lower()]
            if dept_cols:
                dept_col = st.selectbox("🏭 Department column", dept_cols, index=0)
            else:
                dept_col = st.selectbox("🏭 Department column", df.columns.tolist())

        # Process data button
        if st.button("🚀 Process Data & Analyze", type="primary", use_container_width=True):
            with st.spinner("🔄 Processing data... This may take a moment for large datasets"):
                try:
                    # Select relevant columns
                    df_clean = df[[timestamp_col, power_col, dept_col]].copy()
                    df_clean.columns = ['timestamp', 'power_kW', 'department']

                    # Convert timestamp and set as index
                    df_clean['timestamp'] = pd.to_datetime(df_clean['timestamp'])
                    df_clean = df_clean.set_index('timestamp')

                    # Remove rows with NaN
                    df_clean = df_clean.dropna()

                    # Resample options
                    freq_options = {
                        '15min': '15 minutes',
                        '30min': '30 minutes',
                        'h': 'Hourly',
                        '2h': '2 Hourly',
                        '6h': '6 Hourly',
                        'd': 'Daily'
                    }
                    freq_display_map = {
                        '15min': '15 minutes',
                        '30min': '30 minutes',
                        'h': 'Hourly',
                        '2h': '2 Hourly',
                        '6h': '6 Hourly',
                        'd': 'Daily'
                    }
                    freq = st.selectbox(
                        "⏱️ Resampling frequency",
                        options=list(freq_options.keys()),
                        format_func=lambda x: freq_display_map[x],
                        index=2  # Default to hourly
                    )

                    # Process each department
                    resampled_data = []
                    for dept in df_clean['department'].unique():
                        dept_data = df_clean[df_clean['department'] == dept][['power_kW']]
                        # Resample and sum (convert power to energy)
                        resampled = dept_data.resample(freq).sum()
                        resampled['department'] = dept
                        resampled_data.append(resampled)

                    if resampled_data:
                        df_resampled = pd.concat(resampled_data).reset_index()
                        df_resampled = df_resampled.rename(columns={'index': 'timestamp'})

                        # Add time features
                        df_resampled['hour'] = df_resampled['timestamp'].dt.hour
                        df_resampled['day_of_week'] = df_resampled['timestamp'].dt.day_name()
                        df_resampled['date'] = df_resampled['timestamp'].dt.date
                        df_resampled['week'] = df_resampled['timestamp'].dt.isocalendar().week

                        # Define shifts (8-hour shifts)
                        def get_shift(hour):
                            if 6 <= hour < 14:
                                return 'Day Shift (6AM-2PM)'
                            elif 14 <= hour < 22:
                                return 'Evening Shift (2PM-10PM)'
                            else:
                                return 'Night Shift (10PM-6AM)'

                        df_resampled['shift'] = df_resampled['hour'].apply(get_shift)

                        # Apply tariff
                        def get_rate(timestamp):
                            if not use_tod_rates:
                                return base_rate
                            hour = timestamp.hour
                            if peak_start <= hour < peak_end:
                                return peak_rate
                            else:
                                return off_peak_rate

                        df_resampled['rate_per_kWh'] = df_resampled['timestamp'].apply(get_rate)
                        df_resampled['cost'] = df_resampled['power_kW'] * df_resampled['rate_per_kWh']

                        # Calculate rolling statistics for anomaly detection
                        df_resampled['rolling_mean'] = df_resampled.groupby('department')['power_kW'].transform(
                            lambda x: x.rolling(window=window_size, min_periods=1).mean()
                        )
                        df_resampled['rolling_std'] = df_resampled.groupby('department')['power_kW'].transform(
                            lambda x: x.rolling(window=window_size, min_periods=1).std()
                        )
                        # Avoid division by zero
                        df_resampled['rolling_std'] = df_resampled['rolling_std'].replace(0, np.nan)
                        df_resampled['z_score'] = np.where(
                            df_resampled['rolling_std'].notna(),
                            (df_resampled['power_kW'] - df_resampled['rolling_mean']) / df_resampled['rolling_std'],
                            0
                        )
                        df_resampled['is_anomaly'] = np.abs(df_resampled['z_score']) > z_threshold

                        # Store processed data
                        st.session_state['processed_data'] = df_resampled
                        st.success("✅ Data processed successfully!")
                    else:
                        st.error("❌ Unable to process data. Please check your column selections.")
                        st.stop()

                except Exception as e:
                    st.error(f"❌ Error processing data: {str(e)}")
                    st.exception(e)

        # Display results if processed data exists
        if st.session_state['processed_data'] is not None and len(st.session_state['processed_data']) > 0:
            df_result = st.session_state['processed_data']

            # Success metrics
            st.markdown("## 📈 Analysis Results")
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

            with metric_col1:
                total_cost = df_result['cost'].sum()
                st.metric(
                    label="💰 Total Cost",
                    value=f"${total_cost:,.2f}",
                    delta=f"{total_cost/len(df_result):.2f} avg/period"
                )

            with metric_col2:
                total_energy = df_result['power_kW'].sum()
                st.metric(
                    label="⚡ Total Energy",
                    value=f"{total_energy:,.0f} kWh",
                    delta=f"{total_energy/len(df_result):.1f} kWh/period"
                )

            with metric_col3:
                anomaly_count = df_result['is_anomaly'].sum()
                anomaly_pct = (anomaly_count / len(df_result)) * 100
                st.metric(
                    label="🚨 Anomalies Detected",
                    value=f"{anomaly_count}",
                    delta=f"{anomaly_pct:.1f}% of readings"
                )

            with metric_col4:
                avg_cost_per_kwh = df_result['cost'].sum() / df_result['power_kW'].sum() if df_result['power_kW'].sum() > 0 else 0
                st.metric(
                    label="📊 Effective Rate",
                    value=f"${avg_cost_per_kwh:.3f}/kWh",
                    delta=f"{(avg_cost_per_kwh/base_rate - 1)*100:+.1f}% vs base"
                )

            # Create tabs for different analyses
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📊 Cost Analysis",
                "📈 Consumption Trends",
                "🔥 Interactive Heatmap",
                "🚨 Anomaly Explorer",
                "📋 Department Comparison"
            ])

            with tab1:
                st.markdown("### 💰 Cost Breakdown by Shift & Department")

                # Cost summary
                cost_summary = df_result.groupby(['shift', 'department'])['cost'].sum().reset_index()

                # Create interactive bar chart with plotly
                fig_cost = px.bar(
                    cost_summary,
                    x='shift',
                    y='cost',
                    color='department',
                    title="Electricity Cost by Shift and Department",
                    labels={'cost': 'Cost ($)', 'shift': 'Work Shift'},
                    text_auto='$.2f',
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_cost.update_layout(
                    xaxis_tickangle=-45,
                    legend_title_text='Department',
                    hovermode='x unified',
                    barmode='group'
                )
                fig_cost.update_traces(textposition='outside')
                st.plotly_chart(fig_cost, use_container_width=True)

                # Cost pivot table
                cost_pivot = cost_summary.pivot(index='shift', columns='department', values='cost').fillna(0)
                st.markdown("#### 📋 Detailed Cost Table")
                st.dataframe(
                    cost_pivot.style
                    .format("${:.2f}")
                    .background_gradient(cmap='Greens', axis=None),
                    use_container_width=True
                )

                # Daily cost trend
                daily_cost = df_result.groupby('date')['cost'].sum().reset_index()
                fig_daily = px.line(
                    daily_cost,
                    x='date',
                    y='cost',
                    title="Daily Cost Trend",
                    labels={'cost': 'Daily Cost ($)', 'date': 'Date'},
                    markers=True
                )
                fig_daily.update_traces(line_color='#ff6b6b', marker_size=8)
                st.plotly_chart(fig_daily, use_container_width=True)

            with tab2:
                st.markdown("### ⚡ Consumption Trends Analysis")

                # Hourly patterns with department selection
                st.markdown("#### 🕒 Hourly Consumption Patterns")

                # Department selector for hourly chart
                selected_depts = st.multiselect(
                    "Select departments to display:",
                    options=sorted(df_result['department'].unique()),
                    default=sorted(df_result['department'].unique())[:3]  # Default to first 3
                )

                if selected_depts:
                    # Filter data for selected departments
                    filtered_df = df_result[df_result['department'].isin(selected_depts)]

                    # Hourly average
                    hourly_avg = filtered_df.groupby(['hour', 'department'])['power_kW'].mean().reset_index()

                    fig_hourly = px.line(
                        hourly_avg,
                        x='hour',
                        y='power_kW',
                        color='department',
                        title="Average Hourly Consumption by Department",
                        labels={'power_kW': 'Average Power (kW)', 'hour': 'Hour of Day'},
                        markers=True
                    )
                    fig_hourly.update_layout(
                        xaxis=dict(tickmode='linear', tick0=0, dtick=2),
                        hovermode='x unified',
                        legend_title_text='Department'
                    )
                    fig_hourly.update_traces(marker_size=6)
                    st.plotly_chart(fig_hourly, use_container_width=True)

                # Daily patterns
                st.markdown("#### 📅 Day of Week Consumption Patterns")
                dow_avg = df_result.groupby(['day_of_week', 'department'])['power_kW'].mean().reset_index()

                # Reorder days correctly
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                dow_avg['day_of_week'] = pd.Categorical(dow_avg['day_of_week'], categories=day_order, ordered=True)
                dow_avg = dow_avg.sort_values('day_of_week')

                fig_dow = px.bar(
                    dow_avg,
                    x='day_of_week',
                    y='power_kW',
                    color='department',
                    title="Average Consumption by Day of Week",
                    labels={'power_kW': 'Average Power (kW)', 'day_of_week': 'Day of Week'},
                    barmode='group'
                )
                fig_dow.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_dow, use_container_width=True)

                # Weekly pattern (if we have multiple weeks)
                if df_result['week'].nunique() > 1:
                    st.markdown("#### 📆 Weekly Consumption Pattern")
                    weekly_avg = df_result.groupby(['week', 'department'])['power_kW'].sum().reset_index()
                    fig_weekly = px.line(
                        weekly_avg,
                        x='week',
                        y='power_kW',
                        color='department',
                        title="Weekly Total Consumption by Department",
                        labels={'power_kW': 'Total Power (kWh)', 'week': 'Week Number'},
                        markers=True
                    )
                    st.plotly_chart(fig_weekly, use_container_width=True)

            with tab3:
                st.markdown("### 🔥 Interactive Consumption Heatmap")

                # Controls for heatmap
                heatmap_col1, heatmap_col2 = st.columns([2, 1])

                with heatmap_col1:
                    # Department selection for heatmap
                    heatmap_dept = st.selectbox(
                        "🏭 Select department for heatmap:",
                        options=['All Departments'] + sorted(df_result['department'].unique())
                    )

                with heatmap_col2:
                    # Color scheme selector
                    color_scheme = st.selectbox(
                        "🎨 Color Scheme:",
                        options=['Viridis', 'Plasma', 'Inferno', 'Magma', 'Cividis', 'Blues', 'Reds', 'YlOrRd'],
                        index=0
                    )

                # Prepare data for heatmap
                if heatmap_dept == 'All Departments':
                    heatmap_data = df_result.groupby(['day_of_week', 'hour'])['power_kW'].mean().reset_index()
                    title_suffix = "All Departments"
                else:
                    heatmap_data = df_result[df_result['department'] == heatmap_dept].groupby(['day_of_week', 'hour'])['power_kW'].mean().reset_index()
                    title_suffix = f"{heatmap_dept} Department"

                # Create pivot table for heatmap
                heatmap_pivot = heatmap_data.pivot(index='day_of_week', columns='hour', values='power_kW')
                heatmap_pivot = heatmap_pivot.reindex(day_order)  # Order days correctly

                # Create interactive heatmap with plotly
                fig_heatmap = go.Figure(data=go.Heatmap(
                    z=heatmap_pivot.values,
                    x=list(range(24)),
                    y=day_order,
                    colorscale=color_scheme.lower(),
                    hoverongaps=False,
                    hovertemplate='<b>%{y}</b><br>Hour: %{x}:00<br>Power: %{z:.2f} kW<extra></extra>'
                ))

                fig_heatmap.update_layout(
                    title=f"Average Power Consumption Heatmap: {title_suffix}",
                    xaxis_title="Hour of Day",
                    yaxis_title="Day of Week",
                    xaxis=dict(tickmode='linear', tick0=0, dtick=2),
                    height=500
                )

                st.plotly_chart(fig_heatmap, use_container_width=True)

                # Additional insights
                st.markdown("#### 💡 Heatmap Insights")
                insight_col1, insight_col2 = st.columns(2)

                with insight_col1:
                    # Peak consumption time
                    if not heatmap_pivot.isna().all().all():
                        max_idx = heatmap_pivot.stack().idxmax()
                        peak_hour, peak_day = max_idx
                        st.info(f"🔥 **Peak Consumption**: {peak_day} at {peak_hour}:00")

                with insight_col2:
                    # Lowest consumption time
                    if not heatmap_pivot.isna().all().all():
                        min_idx = heatmap_pivot.stack().idxmin()
                        min_hour, min_day = min_idx
                        st.info(f"😴 **Lowest Consumption**: {min_day} at {min_hour}:00")

            with tab4:
                st.markdown("### 🚨 Anomaly Detection & Analysis")

                anomalies = df_result[df_result['is_anomaly']].copy()

                if len(anomalies) > 0:
                    st.warning(f"⚠️ {len(anomalies)} anomalous readings detected ({(len(anomalies)/len(df_result)*100):.1f}% of total)")

                    # Anomaly timeline
                    fig_anomaly_time = px.scatter(
                        anomalies,
                        x='timestamp',
                        y='power_kW',
                        color='z_score',
                        size='cost',
                        hover_data=['department', 'shift', 'cost'],
                        title="Anomalies Over Time (Color = Z-Score, Size = Cost)",
                        labels={
                            'power_kW': 'Power Consumption (kW)',
                            'timestamp': 'Timestamp',
                            'z_score': 'Z-Score'
                        },
                        color_continuous_scale='RdBu_r'
                    )
                    fig_anomaly_time.update_layout(height=400)
                    st.plotly_chart(fig_anomaly_time, use_container_width=True)

                    # Anomaly distribution by department
                    anomaly_by_dept = anomalies.groupby('department').agg({
                        'power_kW': ['mean', 'std', 'count'],
                        'z_score': ['mean', 'std'],
                        'cost': 'sum'
                    }).round(3)

                    anomaly_by_dept.columns = ['Avg Power (kW)', 'Power StdDev', 'Count', 'Avg Z-Score', 'Z-Score StdDev', 'Total Cost ($)']
                    anomaly_by_dept = anomaly_by_dept.reset_index()

                    st.markdown("#### 📊 Anomaly Statistics by Department")
                    st.dataframe(
                        anomaly_by_dept.style
                        .background_gradient(subset=['Count', 'Total Cost ($)'], cmap='Reds')
                        .format({
                            'Avg Power (kW)': '{:.2f}',
                            'Power StdDev': '{:.2f}',
                            'Avg Z-Score': '{:.2f}',
                            'Z-Score StdDev': '{:.2f}',
                            'Total Cost ($)': '${:.2f}'
                        }),
                        use_container_width=True
                    )

                    # Detailed anomaly table
                    st.markdown("#### 📋 Detailed Anomaly Report")
                    anomaly_display = anomalies[['timestamp', 'department', 'shift', 'power_kW', 'z_score', 'cost']].copy()
                    anomaly_display['timestamp'] = anomaly_display['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    anomaly_display = anomaly_display.sort_values('z_score', key=abs, ascending=False)

                    st.dataframe(
                        anomaly_display.style
                        .background_gradient(subset=['z_score'], cmap='RdBu_r', vmin=-z_threshold*2, vmax=z_threshold*2)
                        .format({
                            'power_kW': '{:.2f} kW',
                            'z_score': '{:.2f}',
                            'cost': '${:.2f}'
                        }),
                        use_container_width=True,
                        height=400
                    )

                    # Export anomalies
                    csv = anomalies.to_csv(index=False)
                    st.download_button(
                        label="💾 Export Anomalies as CSV",
                        data=csv,
                        file_name=f"anomalies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.success("✅ No anomalies detected with current sensitivity settings")
                    st.info(f"💡 Try lowering the Z-score threshold (currently {z_threshold}) to detect more subtle anomalies")

            with tab5:
                st.markdown("### 📊 Department Comparison & Analytics")

                # Department comparison metrics
                dept_stats = df_result.groupby('department').agg({
                    'power_kW': ['sum', 'mean', 'std'],
                    'cost': ['sum', 'mean'],
                    'is_anomaly': 'sum'
                }).round(3)

                dept_stats.columns = [
                    'Total Energy (kWh)',
                    'Avg Power (kW)',
                    'Power StdDev',
                    'Total Cost ($)',
                    'Avg Cost ($)',
                    'Anomaly Count'
                ]
                dept_stats = dept_stats.reset_index()

                # Comparison charts
                comp_col1, comp_col2 = st.columns(2)

                with comp_col1:
                    fig_energy = px.bar(
                        dept_stats,
                        x='department',
                        y='Total Energy (kWh)',
                        title="Total Energy Consumption by Department",
                        color='Total Energy (kWh)',
                        color_continuous_scale='Viridis',
                        text_auto='.0f'
                    )
                    fig_energy.update_layout(showlegend=False, xaxis_tickangle=-45)
                    st.plotly_chart(fig_energy, use_container_width=True)

                with comp_col2:
                    fig_cost = px.bar(
                        dept_stats,
                        x='department',
                        y='Total Cost ($)',
                        title="Total Electricity Cost by Department",
                        color='Total Cost ($)',
                        color_continuous_scale='Plasma',
                        text_auto='$.2f'
                    )
                    fig_cost.update_layout(showlegend=False, xaxis_tickangle=-45)
                    st.plotly_chart(fig_cost, use_container_width=True)

                # Efficiency metrics
                st.markdown("#### ⚡ Efficiency Metrics")
                dept_stats['Energy per $'] = dept_stats['Total Energy (kWh)'] / dept_stats['Total Cost ($)']
                dept_stats['Cost per kWh'] = dept_stats['Total Cost ($)'] / dept_stats['Total Energy (kWh)']

                eff_col1, eff_col2 = st.columns(2)

                with eff_col1:
                    fig_eff = px.bar(
                        dept_stats,
                        x='department',
                        y='Energy per $',
                        title="Energy Efficiency (kWh per $)",
                        color='Energy per $',
                        color_continuous_scale='Greens',
                        text_auto='.1f'
                    )
                    fig_eff.update_layout(showlegend=False, xaxis_tickangle=-45)
                    st.plotly_chart(fig_eff, use_container_width=True)

                with eff_col2:
                    fig_rate = px.bar(
                        dept_stats,
                        x='department',
                        y='Cost per kWh',
                        title="Effective Cost Rate ($/kWh)",
                        color='Cost per kWh',
                        color_continuous_scale='Reds',
                        text_auto='$.3f'
                    )
                    fig_rate.update_layout(showlegend=False, xaxis_tickangle=-45)
                    st.plotly_chart(fig_rate, use_container_width=True)

                st.dataframe(
                    dept_stats.style
                    .background_gradient(subset=['Total Energy (kWh)', 'Total Cost ($)', 'Energy per $'], cmap='Blues')
                    .format({
                        'Total Energy (kWh)': '{:,.0f}',
                        'Avg Power (kW)': '{:.2f}',
                        'Power StdDev': '{:.2f}',
                        'Total Cost ($)': '${:,.2f}',
                        'Avg Cost ($)': '${:.2f}',
                        'Anomaly Count': '{:0}',
                        'Energy per $': '{:.1f}',
                        'Cost per kWh': '${:.3f}'
                    }),
                    use_container_width=True
                )

                # Export options
                st.markdown("#### 💾 Export Analysis Results")
                export_col1, export_col2, export_col3 = st.columns(3)

                with export_col1:
                    if st.button("📊 Export Full Dataset", use_container_width=True):
                        csv = df_result.to_csv(index=False)
                        st.download_button(
                            label="⬇️ Download CSV",
                            data=csv,
                            file_name=f"electricity_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                with export_col2:
                    if st.button("💰 Export Cost Summary", use_container_width=True):
                        cost_summary = df_result.groupby(['shift', 'department'])['cost'].sum().reset_index()
                        csv = cost_summary.to_csv(index=False)
                        st.download_button(
                            label="⬇️ Download CSV",
                            data=csv,
                            file_name=f"cost_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                with export_col3:
                    if st.button("📈 Export Department Stats", use_container_width=True):
                        csv = dept_stats.to_csv(index=False)
                        st.download_button(
                            label="⬇️ Download CSV",
                            data=csv,
                            file_name=f"department_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

        else:
            st.info("👆 Configure your data columns above and click 'Process Data & Analyze' to begin")

    except Exception as e:
        st.error(f"❌ An error occurred: {str(e)}")
        st.exception(e)

else:
    # Welcome screen when no data is loaded
    st.markdown("## 👋 Welcome to Electricity Consumption Analyzer Pro")

    welcome_col1, welcome_col2 = st.columns([2, 1])

    with welcome_col1:
        st.markdown("""
        ### 🚀 Features:
        - **📊 Interactive Analytics**: Real-time dashboards with Plotly charts
        - **💰 Smart Cost Analysis**: Flexible tariff settings (flat & time-of-day)
        - **🚨 Advanced Anomaly Detection**: Z-score based with rolling windows
        - **🔥 Consumption Patterns**: Hourly, daily, and weekly heatmaps
        - 📈 Department Comparison: Side-by-side analytics and efficiency metrics
        - 💾 One-Click Export: Download results as CSV for further analysis

        ### 📋 Getting Started:
        1. **Upload your CSV data** using the sidebar, or
        2. **Use sample data** to test all features instantly
        3. **Configure columns** for timestamp, power consumption, and department
        4. **Process and analyze** with interactive controls
        5. **Explore insights** through dynamic visualizations
        """)

    with welcome_col2:
        st.markdown("### 📊 Sample Data Preview")
        # Create a small sample preview
        sample_preview = pd.DataFrame({
            'timestamp': pd.date_range('2023-01-01', periods=5, freq='h'),
            'department': ['Lighting', 'HVAC', 'Machinery', 'IT_Systems', 'Utilities'],
            'power_kW': [12.5, 25.3, 18.7, 8.2, 15.6],
            'area': ['North', 'South', 'East', 'West', 'North']
        })
        st.dataframe(sample_preview, use_container_width=True)

        if st.button("🔬 Try Sample Data", type="primary", use_container_width=True):
            st.session_state['use_sample'] = True
            st.rerun()

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 1rem;'>
        <p>⚡ Electricity Consumption Analyzer Pro • Built with Streamlit & Plotly</p>
        <p><small>Features real-time interactivity, advanced analytics, and export capabilities</small></p>
    </div>
    """,
    unsafe_allow_html=True
)