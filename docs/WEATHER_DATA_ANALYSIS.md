# Weather Data Analysis Documentation

This document describes the data analysis features implemented in Phase 2 of the weather infrastructure project, including automated data profiling and association rule mining for sensor data.

## Overview

The weather data analysis system provides two main capabilities:

1. **Automated Data Profiling**: Generate comprehensive HTML reports using `ydata-profiling`
2. **Association Rule Mining**: Discover patterns in sensor data using `mlxtend`

Both features are designed to work with historical sensor data stored in InfluxDB and integrate seamlessly with the existing weather infrastructure.

## Features

### Data Profiling

- **Comprehensive Reports**: Generate detailed HTML reports with statistics, distributions, correlations, and data quality insights
- **Automatic Directory Creation**: Creates `reports/` directory structure automatically
- **Configurable Output**: Customizable report paths and configurations
- **Data Quality Analysis**: Identifies missing values, outliers, and data quality issues
- **Interactive Visualizations**: HTML reports with interactive charts and graphs

### Association Rule Mining

- **Pattern Discovery**: Automatically discover "if X then Y" patterns in sensor data
- **Data Discretization**: Convert continuous sensor data to categorical bins (low, medium, high)
- **Configurable Thresholds**: Adjustable support, confidence, and lift parameters
- **Rule Filtering**: Filter rules by significance metrics
- **Console Output**: Print significant rules to console/logs for immediate insights

## Architecture

### Core Components

#### WeatherDataAnalyzer

The main class that orchestrates all analysis operations:

```python
from src.weather.analysis import WeatherDataAnalyzer

analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
```

**Key Methods:**

- [`generate_sensor_data_profile_report()`](src/weather/analysis.py:95): Generate HTML profiling reports
- [`discover_sensor_association_rules()`](src/weather/analysis.py:205): Mine association rules from sensor data
- [`run_comprehensive_analysis()`](src/weather/analysis.py:385): Execute both profiling and rule mining

#### Data Flow

1. **Data Retrieval**: Query sensor data from InfluxDB using existing client patterns
2. **Data Processing**: Clean and prepare data for analysis
3. **Analysis Execution**: Run profiling and/or rule mining
4. **Output Generation**: Create reports and display results

## Usage

### Basic Data Profiling

```python
import asyncio
from src.weather.analysis import WeatherDataAnalyzer
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor

async def generate_profile_report():
    # Initialize components
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        await analyzer.connect()
        
        # Retrieve sensor data (last 30 days)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=30)
        
        df_sensor = await analyzer.get_sensor_data_for_analysis(
            start_time=start_time,
            end_time=end_time
        )
        
        # Generate profile report
        analyzer.generate_sensor_data_profile_report(
            df_sensor=df_sensor,
            output_path="reports/sensor_data_profile_report.html"
        )
        
        print("Profile report generated successfully!")
        
    finally:
        await analyzer.disconnect()

# Run the analysis
asyncio.run(generate_profile_report())
```

### Association Rule Mining

```python
async def discover_patterns():
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        await analyzer.connect()
        
        # Get sensor data
        df_sensor = await analyzer.get_sensor_data_for_analysis(
            start_time=datetime.utcnow() - timedelta(days=14)
        )
        
        # Discover association rules
        rules_df = analyzer.discover_sensor_association_rules(
            df_sensor=df_sensor,
            columns_to_bin=['temperature', 'humidity', 'pressure'],
            n_bins=3,
            min_support=0.05,
            min_confidence=0.5,
            min_lift=1.0
        )
        
        print(f"Found {len(rules_df)} significant rules")
        
    finally:
        await analyzer.disconnect()
```

### Comprehensive Analysis

```python
async def run_full_analysis():
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        await analyzer.connect()
        
        # Run both profiling and rule mining
        results = await analyzer.run_comprehensive_analysis(
            days_back=30,
            profile_report=True,
            association_rules=True,
            min_support=0.08,
            min_confidence=0.6,
            min_lift=1.1
        )
        
        print(f"Analysis completed:")
        print(f"- Data points: {results['data_points']}")
        print(f"- Profile report: {results['profile_report']['generated']}")
        print(f"- Rules found: {results['association_rules']['rules_found']}")
        
    finally:
        await analyzer.disconnect()
```

## Function Reference

### generate_sensor_data_profile_report()

Generate comprehensive data profiling report for sensor data.

**Signature:**
```python
def generate_sensor_data_profile_report(
    df_sensor: pd.DataFrame, 
    output_path: str = "reports/sensor_data_profile_report.html"
) -> None
```

**Parameters:**
- `df_sensor`: Sensor data DataFrame with time index
- `output_path`: Output path for HTML report (default: "reports/sensor_data_profile_report.html")

**Raises:**
- `InsufficientDataError`: If DataFrame is empty or has < 10 rows
- `DataAnalysisError`: If report generation fails

**Features:**
- Dataset overview and statistics
- Variable distributions and histograms
- Correlation analysis (Pearson, Spearman, Kendall, Phi-K, Cramér's V)
- Missing value analysis with visualizations
- Data quality warnings and recommendations
- Sample data preview (head, tail, random samples)

### discover_sensor_association_rules()

Discover association rules in sensor data using Apriori algorithm.

**Signature:**
```python
def discover_sensor_association_rules(
    df_sensor: pd.DataFrame, 
    columns_to_bin: list[str], 
    n_bins: int = 3, 
    min_support: float = 0.05, 
    min_confidence: float = 0.5, 
    min_lift: float = 1.0
) -> pd.DataFrame
```

**Parameters:**
- `df_sensor`: Sensor data DataFrame
- `columns_to_bin`: List of columns to discretize for rule mining
- `n_bins`: Number of bins for discretization (default: 3)
- `min_support`: Minimum support threshold (default: 0.05)
- `min_confidence`: Minimum confidence threshold (default: 0.5)
- `min_lift`: Minimum lift threshold (default: 1.0)

**Returns:**
- `pd.DataFrame`: Association rules with metrics (support, confidence, lift)

**Raises:**
- `InsufficientDataError`: If DataFrame is empty or has < 20 rows
- `DataAnalysisError`: If rule mining fails

**Process:**
1. Discretize continuous data into categorical bins
2. Create transactions for Apriori algorithm
3. Find frequent itemsets using minimum support
4. Generate association rules with minimum confidence
5. Filter rules by minimum lift
6. Sort by lift and confidence (descending)

## Configuration

### Analysis Parameters

The analysis system supports various configuration parameters:

#### Data Profiling Configuration

```python
profile_config = {
    "title": "Ruuvi Sensor Data Profile Report",
    "dataset": {
        "description": "Environmental sensor data description",
        "creator": "Ruuvi Weather Analysis System"
    },
    "correlations": {
        "auto": {"calculate": True},
        "pearson": {"calculate": True},
        "spearman": {"calculate": True},
        "kendall": {"calculate": True}
    },
    "missing_diagrams": {
        "bar": True,
        "matrix": True,
        "heatmap": True
    }
}
```

#### Association Rule Mining Parameters

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `n_bins` | Number of discretization bins | 3 | 2-5 |
| `min_support` | Minimum support threshold | 0.05 | 0.01-0.5 |
| `min_confidence` | Minimum confidence threshold | 0.5 | 0.1-0.9 |
| `min_lift` | Minimum lift threshold | 1.0 | 1.0-3.0 |

### Recommended Settings

#### For Exploratory Analysis
```python
{
    "n_bins": 3,
    "min_support": 0.05,
    "min_confidence": 0.5,
    "min_lift": 1.0
}
```

#### For Conservative Rules
```python
{
    "n_bins": 3,
    "min_support": 0.1,
    "min_confidence": 0.7,
    "min_lift": 1.2
}
```

## Data Requirements

### Minimum Data Requirements

- **Data Profiling**: Minimum 10 data points
- **Association Rule Mining**: Minimum 20 data points
- **Recommended**: 100+ data points for meaningful analysis

### Data Format

The analysis system expects sensor data in the following format:

```python
# DataFrame with time index
df_sensor = pd.DataFrame({
    'temperature': [20.5, 21.0, 19.8, ...],  # Celsius
    'humidity': [65.0, 63.2, 67.1, ...],     # Percentage
    'pressure': [1013.25, 1014.0, 1012.8, ...] # hPa
}, index=pd.DatetimeIndex([...]))  # Time index required
```

### Data Quality Considerations

- **Missing Values**: Handled automatically during analysis
- **Outliers**: Identified in profile reports
- **Data Types**: Numeric data required for analysis
- **Time Series**: Time index recommended for temporal analysis

## Output Formats

### Profile Report Output

The HTML profile report includes:

1. **Overview Section**
   - Dataset statistics
   - Variable types
   - Warnings and alerts

2. **Variables Section**
   - Individual variable analysis
   - Distributions and histograms
   - Descriptive statistics

3. **Interactions Section**
   - Scatter plots
   - Correlation matrices

4. **Correlations Section**
   - Multiple correlation methods
   - Heatmaps and matrices

5. **Missing Values Section**
   - Missing value patterns
   - Visualizations

6. **Sample Section**
   - First/last rows
   - Random samples

### Association Rules Output

Rules are returned as a pandas DataFrame with columns:

| Column | Description | Type |
|--------|-------------|------|
| `antecedents` | Rule conditions (frozenset) | frozenset |
| `consequents` | Rule outcomes (frozenset) | frozenset |
| `antecedents_str` | Readable conditions | string |
| `consequents_str` | Readable outcomes | string |
| `support` | Rule support | float |
| `confidence` | Rule confidence | float |
| `lift` | Rule lift | float |
| `leverage` | Rule leverage | float |
| `conviction` | Rule conviction | float |

### Console Output Example

```
=== SIGNIFICANT ASSOCIATION RULES ===
Rule 1: temperature_high → humidity_low (Support: 0.150, Confidence: 0.750, Lift: 1.500)
Rule 2: pressure_low → humidity_high (Support: 0.120, Confidence: 0.680, Lift: 1.350)
Rule 3: temperature_low, pressure_high → humidity_medium (Support: 0.080, Confidence: 0.650, Lift: 1.200)

Rule Mining Summary:
Total rules found: 15
Average confidence: 0.642
Average lift: 1.285
Highest lift: 1.750
```

## Integration

### With Existing Weather Infrastructure

The analysis system integrates seamlessly with existing components:

```python
# Use existing InfluxDB client
from src.influxdb.client import RuuviInfluxDBClient

influxdb_client = RuuviInfluxDBClient(config, logger, performance_monitor)
analyzer = WeatherDataAnalyzer(config, logger, performance_monitor, influxdb_client)
```

### With Forecast Accuracy System

```python
# Combine with forecast accuracy analysis
from src.weather.accuracy import ForecastAccuracyCalculator
from src.weather.analysis import WeatherDataAnalyzer

# Run both analyses
accuracy_calc = ForecastAccuracyCalculator(config, logger, performance_monitor)
analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)

# Analyze forecast accuracy
accuracy_results = await accuracy_calc.calculate_forecast_accuracy(...)

# Analyze sensor data patterns
analysis_results = await analyzer.run_comprehensive_analysis(...)
```

## Error Handling

### Exception Types

- **`DataAnalysisError`**: Base exception for analysis operations
- **`InsufficientDataError`**: Insufficient data for analysis
- **Standard exceptions**: `ValueError`, `TypeError`, etc.

### Error Handling Patterns

```python
try:
    results = await analyzer.run_comprehensive_analysis(days_back=30)
except InsufficientDataError as e:
    logger.warning(f"Insufficient data: {e}")
    # Handle gracefully - maybe reduce time range
except DataAnalysisError as e:
    logger.error(f"Analysis failed: {e}")
    # Handle analysis failure
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    # Handle unexpected errors
```

## Performance Considerations

### Memory Usage

- **Profile Reports**: Memory usage scales with data size
- **Association Rules**: Memory intensive for large datasets
- **Recommendations**: 
  - Limit analysis to 10,000 data points for large datasets
  - Use time-based filtering for recent data analysis

### Processing Time

- **Profile Reports**: 1-10 seconds for typical datasets
- **Association Rules**: 5-30 seconds depending on parameters
- **Optimization**: Use higher support thresholds for faster processing

### Monitoring

The system records performance metrics:

```python
# Metrics recorded
performance_monitor.record_metric("profile_report_generation_time", time_seconds)
performance_monitor.record_metric("profile_report_data_points", data_count)
performance_monitor.record_metric("association_rules_found", rules_count)
performance_monitor.record_metric("frequent_itemsets_found", itemsets_count)
```

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
python -m pytest tests/unit/test_weather_analysis.py -v
```

### Integration Tests

Test with real data:

```bash
python scripts/test_weather_analysis.py
```

### Example Usage

Run the example script:

```bash
python examples/weather_analysis_example.py
```

## Troubleshooting

### Common Issues

#### 1. No Data Retrieved

**Problem**: `InsufficientDataError: No sensor data found`

**Solutions:**
- Check InfluxDB connection
- Verify measurement name (`ruuvi_environmental`)
- Adjust time range
- Check sensor MAC address filter

#### 2. Profile Report Generation Fails

**Problem**: `DataAnalysisError: Profile report generation failed`

**Solutions:**
- Ensure sufficient data (>10 points)
- Check output directory permissions
- Verify pandas DataFrame format
- Check available memory

#### 3. No Association Rules Found

**Problem**: Empty rules DataFrame returned

**Solutions:**
- Lower support/confidence thresholds
- Increase data time range
- Check data discretization
- Verify data has patterns

#### 4. Memory Issues

**Problem**: Out of memory during analysis

**Solutions:**
- Reduce data time range
- Increase system memory
- Use data sampling
- Process in smaller batches

### Debug Mode

Enable debug logging for detailed information:

```python
import logging
logging.getLogger('src.weather.analysis').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features

1. **Advanced Analytics**
   - Time series analysis
   - Seasonal pattern detection
   - Anomaly detection

2. **Enhanced Reporting**
   - PDF report generation
   - Custom report templates
   - Automated report scheduling

3. **Machine Learning**
   - Predictive modeling
   - Classification algorithms
   - Clustering analysis

4. **Performance Optimization**
   - Parallel processing
   - Incremental analysis
   - Caching mechanisms

### Contributing

To contribute to the analysis system:

1. Follow existing code patterns
2. Add comprehensive tests
3. Update documentation
4. Consider performance implications
5. Maintain backward compatibility

## References

- [ydata-profiling Documentation](https://docs.profiling.ydata.ai/)
- [mlxtend Documentation](http://rasbt.github.io/mlxtend/)
- [Association Rule Mining Theory](https://en.wikipedia.org/wiki/Association_rule_learning)
- [Pandas Documentation](https://pandas.pydata.org/docs/)