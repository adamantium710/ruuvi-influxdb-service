# Grafana Dashboards

This directory contains pre-configured Grafana dashboard JSON files for the Ruuvi Weather Forecast Analysis System (Phase 2).

## Available Dashboards

### 1. Live Weather & Forecast Comparison
**File**: [`dashboard-live-weather-comparison.json`](dashboard-live-weather-comparison.json)
**UID**: `ruuvi-weather-live`

**Purpose**: Real-time comparison between actual sensor readings and weather forecasts

**Panels**:
- Temperature: Actual vs Forecast (1h, 6h, 24h horizons)
- Humidity: Actual vs Forecast (1h, 6h horizons)  
- Pressure: Actual vs Forecast (1h horizon)
- Current 1h Temperature Error (stat panel)
- Current 1h Humidity Error (stat panel)

**Time Range**: Last 6 hours (30-second refresh)
**Best For**: Monitoring current forecast accuracy and real-time performance

### 2. Forecast Accuracy Analysis
**File**: [`dashboard-forecast-accuracy-analysis.json`](dashboard-forecast-accuracy-analysis.json)
**UID**: `ruuvi-forecast-accuracy`

**Purpose**: Historical analysis of forecast accuracy metrics across different time horizons

**Panels**:
- Temperature MAE by Forecast Horizon (1h, 6h, 24h, 48h)
- Temperature RMSE by Forecast Horizon
- Humidity MAE by Forecast Horizon
- Temperature Bias (Signed Error) by Horizon
- Average MAE Statistics (stat panels for different metrics and horizons)

**Time Range**: Last 7 days (5-minute refresh)
**Best For**: Long-term accuracy analysis and performance trends

## Import Instructions

### Method 1: Grafana UI Import

1. **Access Grafana**: Open http://localhost:3000 (default credentials: admin/admin)

2. **Navigate to Import**:
   - Click the "+" icon in the left sidebar
   - Select "Import"

3. **Upload JSON**:
   - Click "Upload JSON file"
   - Select one of the dashboard JSON files from this directory
   - Click "Load"

4. **Configure Import**:
   - **Name**: Keep default or customize
   - **Folder**: Select appropriate folder (or create new)
   - **UID**: Keep default (ensures uniqueness)
   - **Datasource**: Select your InfluxDB datasource

5. **Import**: Click "Import" to complete

### Method 2: API Import

```bash
# Import Live Weather Comparison Dashboard
curl -X POST \
  http://admin:admin@localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @grafana/dashboard-live-weather-comparison.json

# Import Forecast Accuracy Analysis Dashboard  
curl -X POST \
  http://admin:admin@localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @grafana/dashboard-forecast-accuracy-analysis.json
```

### Method 3: Provisioning (Automated)

Create a provisioning configuration:

```yaml
# /etc/grafana/provisioning/dashboards/ruuvi.yml
apiVersion: 1

providers:
  - name: 'ruuvi-dashboards'
    orgId: 1
    folder: 'Ruuvi Weather'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /path/to/ruuvi/grafana
```

## Prerequisites

### Required Datasource

Both dashboards require an InfluxDB datasource configured in Grafana:

1. **Datasource Type**: InfluxDB
2. **Query Language**: Flux
3. **URL**: http://localhost:8086
4. **Organization**: Your InfluxDB org
5. **Token**: Your InfluxDB token
6. **Default Bucket**: ruuvi

### Required Data

The dashboards expect these InfluxDB measurements:

#### Core Sensor Data
```
Measurement: weather_sensors
Fields: temperature, humidity, pressure
Tags: sensor_id, location
```

#### Forecast Data  
```
Measurement: weather_forecasts
Fields: temperature, humidity, pressure
Tags: api_source, forecast_horizon (1h, 6h, 24h, 48h)
```

#### Error Data
```
Measurement: weather_forecast_errors  
Fields: absolute_error, signed_error, mae, rmse
Tags: metric, forecast_horizon, api_source
```

## Customization

### Modifying Queries

Each panel's query can be customized by:

1. **Edit Panel**: Click panel title → Edit
2. **Query Tab**: Modify Flux queries as needed
3. **Apply**: Save changes

### Common Customizations

#### Change Time Aggregation
```flux
# Original (5-minute windows)
|> aggregateWindow(every: 5m, fn: mean, createEmpty: false)

# Custom (1-hour windows)  
|> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
```

#### Filter by Sensor
```flux
# Add sensor filter
|> filter(fn: (r) => r.sensor_id == "XX:XX:XX:XX:XX:XX")
```

#### Change Forecast Horizon
```flux
# Original (1h forecasts)
|> filter(fn: (r) => r.forecast_horizon == "1h")

# Custom (24h forecasts)
|> filter(fn: (r) => r.forecast_horizon == "24h")
```

### Visual Customization

#### Colors
- Edit panel → Field tab → Standard options → Color scheme
- Override specific series colors in Overrides tab

#### Units
- Temperature: celsius, fahrenheit
- Humidity: percent (0-100)
- Pressure: pressurehpa, pressurembar

#### Thresholds
- Stat panels: Field tab → Thresholds
- Time series: Field tab → Thresholds → Show thresholds

## Troubleshooting

### No Data Displayed

1. **Check Datasource**: Verify InfluxDB connection in Grafana
2. **Verify Data**: Run queries directly in InfluxDB:
   ```bash
   influx query 'from(bucket:"ruuvi") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "weather_sensors") |> limit(n:10)'
   ```
3. **Time Range**: Adjust dashboard time range to match data availability
4. **Bucket Name**: Ensure queries use correct bucket name

### Query Errors

1. **Syntax**: Validate Flux query syntax
2. **Fields**: Check field names match your data schema
3. **Tags**: Verify tag names and values exist

### Performance Issues

1. **Time Range**: Reduce query time range
2. **Aggregation**: Increase aggregation window (e.g., 5m → 15m)
3. **Refresh**: Increase refresh interval

## Dashboard Maintenance

### Regular Updates

1. **Export Modified Dashboards**:
   - Dashboard settings → JSON Model → Copy to clipboard
   - Save to version control

2. **Backup Dashboards**:
   ```bash
   # Export all dashboards
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:3000/api/search?type=dash-db | \
        jq -r '.[] | .uid' | \
        xargs -I {} curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:3000/api/dashboards/uid/{} > backup_{}.json
   ```

### Version Control

Track dashboard changes in git:
```bash
git add grafana/*.json
git commit -m "Update Grafana dashboards"
```

## Support

For dashboard-specific issues:

1. **Check Logs**: Grafana logs in `/var/log/grafana/`
2. **Query Inspector**: Use Grafana's query inspector for debugging
3. **Documentation**: See [`GRAFANA_DASHBOARD_GUIDE.md`](../docs/GRAFANA_DASHBOARD_GUIDE.md) for detailed setup
4. **Troubleshooting**: See [`TROUBLESHOOTING.md`](../docs/TROUBLESHOOTING.md) for common issues

## Contributing

When modifying dashboards:

1. **Test Thoroughly**: Verify all panels display correctly
2. **Document Changes**: Update this README if adding new dashboards
3. **Export Clean JSON**: Remove personal settings before committing
4. **Validate JSON**: Ensure valid JSON syntax

---

**Note**: These dashboards are designed for the Phase 2 Weather Forecast Analysis System. Ensure your system is properly configured according to the main project documentation before importing.