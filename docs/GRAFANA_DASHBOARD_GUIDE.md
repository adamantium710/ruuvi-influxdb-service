# Grafana Dashboard Configuration Guide - Phase 2 Weather Forecast System

## Overview

This guide provides comprehensive instructions for configuring Grafana dashboards to visualize the Phase 2 weather forecast analysis system data. The system stores data in three main InfluxDB measurements:

- **`weather_sensors`** (or `ruuvi_measurements`): Actual sensor readings
- **`weather_forecasts`**: Weather forecast data with forecast metadata
- **`weather_forecast_errors`**: Calculated forecast accuracy errors

## Prerequisites

### System Requirements
- **Grafana**: Version 8.0+ (recommended: 9.0+)
- **InfluxDB**: Version 2.x with Flux query language support
- **Data Source**: InfluxDB 2.x data source configured in Grafana
- **Permissions**: Read access to weather forecast buckets

### InfluxDB Data Source Configuration

1. **Add InfluxDB Data Source**:
   - Go to Configuration → Data Sources → Add data source
   - Select "InfluxDB"
   - Configure connection:
     ```
     URL: http://localhost:8086
     Organization: your_org
     Token: your_influxdb_token
     Default Bucket: weather_forecasts
     ```

2. **Test Connection**: Ensure the data source connects successfully

## Dashboard 1: Live Weather & Forecast Comparison

This dashboard provides real-time comparison between actual sensor readings and weather forecasts.

### Dashboard Configuration

**Dashboard Settings**:
- **Title**: "Weather Forecast vs Actual Comparison"
- **Tags**: `weather`, `forecast`, `comparison`
- **Time Range**: Last 7 days (default)
- **Refresh**: 5 minutes

### Panel 1: Actual vs. Forecast Temperature (Time Series)

**Panel Configuration**:
- **Type**: Time series
- **Title**: "Temperature: Actual vs Forecast"
- **Unit**: Celsius (°C)
- **Y-Axis**: Dual axis for better comparison

**Query A - Actual Temperature**:
```flux
from(bucket: "ruuvi_sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "ruuvi_measurements")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "actual_temperature")
```

**Query B - Forecast Temperature (24h horizon)**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> filter(fn: (r) => r["data_type"] == "forecast")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "24")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "forecast_24h")
```

**Query C - Forecast Temperature (6h horizon)**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> filter(fn: (r) => r["data_type"] == "forecast")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "6")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "forecast_6h")
```

**Display Options**:
- **Actual Temperature**: Solid blue line, width 2
- **24h Forecast**: Dashed red line, width 1.5
- **6h Forecast**: Dotted green line, width 1.5
- **Legend**: Bottom placement, show values (min, max, current)

### Panel 2: Actual vs. Forecast Humidity/Pressure (Time Series)

**Panel Configuration**:
- **Type**: Time series
- **Title**: "Humidity & Pressure: Actual vs Forecast"
- **Dual Y-Axis**: Left for humidity (%), Right for pressure (hPa)

**Query A - Actual Humidity**:
```flux
from(bucket: "ruuvi_sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "ruuvi_measurements")
  |> filter(fn: (r) => r["_field"] == "humidity")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "actual_humidity")
```

**Query B - Forecast Humidity**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
  |> filter(fn: (r) => r["_field"] == "humidity")
  |> filter(fn: (r) => r["data_type"] == "forecast")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "24")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "forecast_humidity")
```

**Query C - Actual Pressure**:
```flux
from(bucket: "ruuvi_sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "ruuvi_measurements")
  |> filter(fn: (r) => r["_field"] == "pressure")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "actual_pressure")
```

**Query D - Forecast Pressure**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
  |> filter(fn: (r) => r["_field"] == "pressure")
  |> filter(fn: (r) => r["data_type"] == "forecast")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "24")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "forecast_pressure")
```

**Field Overrides**:
- **Humidity fields**: Left Y-axis, unit: percent (0-100)
- **Pressure fields**: Right Y-axis, unit: hPa

### Panel 3: Current Forecast (Table/Stat)

**Panel Configuration**:
- **Type**: Stat
- **Title**: "Current Weather Forecast"
- **Layout**: Horizontal orientation

**Query A - Current Forecast Summary**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: -1h, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
  |> filter(fn: (r) => r["data_type"] == "forecast")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "1")
  |> filter(fn: (r) => r["_field"] == "temperature" or r["_field"] == "humidity" or r["_field"] == "pressure")
  |> last()
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> yield(name: "current_forecast")
```

**Display Configuration**:
- **Temperature**: Green background, °C unit
- **Humidity**: Blue background, % unit  
- **Pressure**: Orange background, hPa unit
- **Text Size**: Large
- **Show Sparkline**: Enabled

## Dashboard 2: Forecast Accuracy Analysis

This dashboard provides comprehensive analysis of forecast accuracy and bias patterns.

### Dashboard Configuration

**Dashboard Settings**:
- **Title**: "Weather Forecast Accuracy Analysis"
- **Tags**: `weather`, `forecast`, `accuracy`, `analysis`
- **Time Range**: Last 30 days (default)
- **Refresh**: 15 minutes

### Dashboard Variables

Create the following template variables:

**Variable 1: Forecast Horizon**
- **Name**: `forecast_horizon`
- **Type**: Query
- **Query**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> keep(columns: ["forecast_horizon_hours"])
  |> distinct(column: "forecast_horizon_hours")
  |> yield(name: "horizons")
```
- **Multi-value**: Enabled
- **Include All**: Enabled

**Variable 2: Data Source**
- **Name**: `data_source`
- **Type**: Query
- **Query**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> keep(columns: ["source"])
  |> distinct(column: "source")
  |> yield(name: "sources")
```

### Panel 1: Temperature Absolute Error Over Time (Time Series)

**Panel Configuration**:
- **Type**: Time series
- **Title**: "Temperature Absolute Error Over Time"
- **Unit**: Celsius (°C)
- **Y-Axis**: Min: 0

**Query A - Temperature Absolute Error**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_abs_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> filter(fn: (r) => contains(value: r["source"], set: [${data_source:json}]))
  |> aggregateWindow(every: 6h, fn: mean, createEmpty: false)
  |> yield(name: "temp_abs_error")
```

**Query B - Rolling Average (24h)**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_abs_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> timedMovingAverage(every: 1h, period: 24h)
  |> yield(name: "temp_abs_error_24h_avg")
```

**Display Options**:
- **Absolute Error**: Blue line, width 1
- **24h Rolling Average**: Red line, width 2
- **Thresholds**: Warning at 2°C, Critical at 5°C

### Panel 2: Temperature Signed Error (Bias) Over Time (Time Series)

**Panel Configuration**:
- **Type**: Time series
- **Title**: "Temperature Forecast Bias (Signed Error)"
- **Unit**: Celsius (°C)
- **Y-Axis**: Center on 0

**Query A - Temperature Signed Error**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_signed_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> aggregateWindow(every: 6h, fn: mean, createEmpty: false)
  |> yield(name: "temp_signed_error")
```

**Query B - Bias Trend Line**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_signed_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> timedMovingAverage(every: 1h, period: 48h)
  |> yield(name: "bias_trend")
```

**Display Options**:
- **Zero Line**: Horizontal reference line at y=0
- **Positive Bias**: Red area (over-prediction)
- **Negative Bias**: Blue area (under-prediction)
- **Trend Line**: Black dashed line

### Panel 3: Error Distribution (Histogram)

**Panel Configuration**:
- **Type**: Histogram
- **Title**: "Temperature Error Distribution"
- **Bucket Size**: 0.5°C

**Query A - Error Distribution Data**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_signed_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> keep(columns: ["_time", "_value"])
  |> yield(name: "error_distribution")
```

**Display Options**:
- **Bucket Count**: 20
- **Color**: Gradient from blue (negative) to red (positive)
- **Statistics Overlay**: Mean, median, std deviation

### Panel 4: MAE/RMSE/Bias Stats (Stat Panels)

**Panel Configuration**:
- **Type**: Stat
- **Title**: "Forecast Accuracy Statistics"
- **Layout**: Grid (2x2)

**Query A - Mean Absolute Error (MAE)**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_abs_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> mean()
  |> yield(name: "MAE")
```

**Query B - Root Mean Square Error (RMSE)**:
```flux
import "math"

from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_signed_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> map(fn: (r) => ({ r with _value: r._value * r._value }))
  |> mean()
  |> map(fn: (r) => ({ r with _value: math.sqrt(x: r._value) }))
  |> yield(name: "RMSE")
```

**Query C - Mean Bias**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_signed_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> mean()
  |> yield(name: "Bias")
```

**Query D - Standard Deviation**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_signed_error")
  |> filter(fn: (r) => contains(value: r["forecast_horizon_hours"], set: [${forecast_horizon:json}]))
  |> stddev()
  |> yield(name: "StdDev")
```

**Display Configuration**:
- **MAE**: Green background, °C unit, "Lower is better"
- **RMSE**: Orange background, °C unit, "Lower is better"
- **Bias**: Blue background, °C unit, "Closer to 0 is better"
- **StdDev**: Purple background, °C unit, "Lower is better"

### Panel 5: Actual vs. Forecast Scatter Plot (XY Chart)

**Panel Configuration**:
- **Type**: XY Chart (or Scatter plot)
- **Title**: "Actual vs Forecast Temperature Correlation"
- **X-Axis**: Actual Temperature (°C)
- **Y-Axis**: Forecast Temperature (°C)

**Query A - Correlation Data**:
```flux
actual = from(bucket: "ruuvi_sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "ruuvi_measurements")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)

forecast = from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> filter(fn: (r) => r["data_type"] == "forecast")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "24")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)

join(tables: {actual: actual, forecast: forecast}, on: ["_time"])
  |> map(fn: (r) => ({
      _time: r._time,
      actual: r._value_actual,
      forecast: r._value_forecast
    }))
  |> yield(name: "correlation")
```

**Display Options**:
- **Perfect Correlation Line**: Diagonal line (y=x)
- **Point Color**: Based on time (gradient)
- **Point Size**: 3px
- **Correlation Coefficient**: Display in legend

## Advanced Configuration

### Dashboard Linking

**Cross-Dashboard Navigation**:
- Add dashboard links in the top navigation
- Use URL parameters to maintain time range and variable selections
- Create drill-down links from summary to detailed views

### Alerting Configuration

**Temperature Error Alert**:
```flux
from(bucket: "weather_forecasts")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_abs_error")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "24")
  |> mean()
  |> yield(name: "avg_error")
```

**Alert Conditions**:
- **Warning**: MAE > 3°C for 2 hours
- **Critical**: MAE > 5°C for 1 hour
- **Recovery**: MAE < 2°C for 30 minutes

### Performance Optimization

**Query Optimization Tips**:
1. **Use appropriate time ranges**: Avoid querying excessive historical data
2. **Leverage aggregateWindow**: Pre-aggregate data for better performance
3. **Filter early**: Apply filters before aggregations
4. **Use variables**: Parameterize queries for reusability
5. **Cache settings**: Configure appropriate cache TTL for panels

**Recommended Refresh Intervals**:
- **Live comparison dashboard**: 5 minutes
- **Accuracy analysis dashboard**: 15 minutes
- **Historical analysis**: 1 hour

## Troubleshooting

### Common Issues

**1. No Data Displayed**
- **Check data source connection**: Verify InfluxDB connectivity
- **Verify bucket names**: Ensure correct bucket references in queries
- **Check time ranges**: Confirm data exists in selected time range
- **Validate field names**: Ensure field names match actual data schema

**2. Query Performance Issues**
- **Reduce time range**: Use shorter time windows for complex queries
- **Add aggregation**: Use `aggregateWindow()` to reduce data points
- **Optimize filters**: Apply most selective filters first
- **Check indexes**: Ensure proper InfluxDB indexing

**3. Visualization Problems**
- **Unit configuration**: Set appropriate units for each field
- **Y-axis scaling**: Configure min/max values for better visualization
- **Color schemes**: Use consistent colors across related panels
- **Legend placement**: Position legends to avoid overlapping data

### Debug Queries

**Test Data Availability**:
```flux
// Check if forecast data exists
from(bucket: "weather_forecasts")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
  |> count()

// Check if error data exists  
from(bucket: "weather_forecasts")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> count()

// Check sensor data
from(bucket: "ruuvi_sensors")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "ruuvi_measurements")
  |> count()
```

## Dashboard Export/Import

### Exporting Dashboards

1. **Navigate to dashboard**
2. **Click Settings (gear icon)**
3. **Select "JSON Model"**
4. **Copy JSON content**
5. **Save to file** (e.g., `weather-forecast-dashboard.json`)

### Importing Dashboards

1. **Go to Dashboards → Import**
2. **Upload JSON file** or paste JSON content
3. **Configure data source** mapping
4. **Set dashboard folder** and permissions
5. **Click Import**

### Version Control

**Recommended Practices**:
- Store dashboard JSON files in version control
- Use descriptive commit messages for dashboard changes
- Tag stable dashboard versions
- Document breaking changes in dashboard structure

## Integration with Existing Dashboards

### Adding Weather Panels to Sensor Dashboards

**Panel Integration Steps**:
1. **Open existing sensor dashboard**
2. **Add new panel**
3. **Use weather forecast queries**
4. **Configure shared time range variables**
5. **Align styling with existing panels**

**Shared Variables**:
Create dashboard-level variables that work across sensor and weather data:
- **Time Range**: Synchronized across all panels
- **Location Filter**: If monitoring multiple locations
- **Aggregation Window**: Consistent time grouping

### Unified Dashboard Approach

**Combined Sensor + Weather Dashboard**:
- **Top Row**: Current conditions (sensor + forecast)
- **Middle Rows**: Historical trends and comparisons
- **Bottom Row**: Accuracy analysis and statistics

**Layout Recommendations**:
- **Grid**: 24 columns for flexible panel sizing
- **Panel Heights**: Consistent heights for visual alignment
- **Color Scheme**: Unified color palette across all panels
- **Typography**: Consistent font sizes and styles

This comprehensive guide provides all the necessary information to configure professional-grade Grafana dashboards for the Phase 2 weather forecast analysis system. The dashboards will provide valuable insights into forecast accuracy and help identify patterns in weather prediction performance.