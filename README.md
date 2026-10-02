# Electricity Consumption Analyzer

An interactive platform for analyzing interval meter readings to break down electricity costs per shift and department, detect anomalies, and visualize consumption patterns.

## Features

- **Interval Ingestion**: Accepts CSV files with minute/hour granularity meter readings
- **Cost Engine**: Applies tariff rates (flat or time-of-day) to compute costs per shift and department
- **Anomaly Detection**: Flags abnormal consumption using z-score on rolling averages
- **Trends & Heatmaps**: Visualizes hourly/daily patterns and hour×day consumption heatmaps
- **Interactive Controls**: Adjustable tariff settings, detection sensitivity, and time aggregation
- **Export Options**: Download processed data, cost summaries, and anomaly reports

## Installation

1. Clone this repository or download the files
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the Streamlit application:
```bash
streamlit run electricity_analyzer.py
```

### Data Requirements

Your CSV file should contain:
- A timestamp column (auto-detected)
- Power consumption values (in kW or kWh)
- Department/area tags
- Optional: other metadata columns

### Sample Data

The application includes a sample data generator based on the UCI Household Electric Power Dataset. To use sample data:
1. Check "Use sample data" in the sidebar
2. Click "Load Sample Data"

## How It Works

1. **Data Ingestion**: Loads CSV and allows column mapping for timestamp, power, and department
2. **Time Aggregation**: Resamples data to selected frequency (15min, 30min, hourly, etc.)
3. **Shift Classification**: Automatically categorizes readings into 8-hour shifts
4. **Cost Calculation**: Applies tariff rates to compute energy costs
5. **Anomaly Detection**: Uses rolling z-score to identify abnormal consumption patterns
6. **Visualization**: Generates interactive charts and heatmaps for pattern analysis

## Customization

### Tariff Settings
- Set base rate ($/kWh)
- Enable time-of-day rates with custom peak/off-peak pricing
- Define peak hours for TOU rates

### Anomaly Detection
- Adjust rolling window size (hours)
- Set z-score threshold for anomaly detection

### Visualization
- Switch between different time aggregations
- View department-specific patterns
- Export results as CSV

## Expected Output

Upon successful analysis, you will see:
- Cost breakdown tables by shift and department
- Anomaly alerts with timestamps and magnitudes
- Hourly consumption trends
- Day-of-week consumption patterns
- Hour×day heatmaps showing consumption intensity
- Interactive controls to adjust parameters in real-time

## Dependencies

- streamlit>=1.28.0
- pandas>=2.0.0
- numpy>=1.24.0
- seaborn>=0.12.0
- matplotlib>=3.7.0

## Notes

- The application processes data in memory; very large datasets may require sampling
- All calculations are performed client-side - no data is uploaded to external servers
- For best results, ensure your timestamp column is in a standard datetime format