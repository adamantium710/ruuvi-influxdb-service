# AI Code Assistant Project Specification: Enhanced Weather Data Analysis & Forecast Accuracy Tracking

## 1. Project Overview & Goal

The primary goal is to **enhance the existing Python codebase** to perform advanced analysis on historical sensor data *and* track the accuracy of external weather forecasts over time. This will enable insights into forecast biases and discrepancies, by storing all relevant data in InfluxDB, which will then be consumed by Grafana for dynamic and interactive visualizations. The Python script will focus solely on data processing and storage, not on direct visualization.

## 2. Current Codebase Context

### 2.1. Core Application: InfluxDB Data Retrieval

* **Description:** Existing Python application retrieves sensor data (pressure, temperature, humidity) from InfluxDB.
* **Key Files/Modules:** `influxdb_data_retriever.py` (or similar).
* **Assumed Function Signature (if applicable):**
    ```python
    def get_sensor_data_from_influxdb(
        measurement: str,
        fields: list[str],
        time_range: str = '30 days',
        group_by_interval: str = '1h'
    ) -> pd.DataFrame:
        # Existing implementation details (e.g., uses influxdb_client_3, connects to a specific host/db/token)
        pass
    ```
* **In-scope Modifications:** This function might need minor adjustments to retrieve newly stored forecast data.
* **Out-of-scope Modifications:** Do not rewrite the entire InfluxDB connection logic unless explicitly necessary.

### 2.2. Existing Data Structures

* **Primary Data Structure:** `pandas.DataFrame`.
* **Key Sensor Columns:**
    * `time`: (datetime64[ns], DataFrame index) - Crucial for time-series operations.
    * `pressure`: (float) - Hectopascals (hPa).
    * `temperature`: (float) - Degrees Celsius (°C).
    * `humidity`: (float) - Percentage (%).
* **Expected Data State:** Raw, possibly with missing values.

## 3. New Features & Requirements (Python Script Focus)

The following features need to be integrated or developed within the Python script. These will process and store data, which Grafana will then consume.

### 3.1. Feature: Fetch & Store Weather Forecast Data in InfluxDB

* **Objective:** Periodically fetch weather forecast data from an external API and store it in InfluxDB, enriched with metadata about *when the forecast was made*. This will create a historical archive of predictions.
* **Sub-requirements:**
    * **API Selection:**
        * **Recommendation:** **Open-Meteo.com's Historical Forecast API** is strongly recommended as it supports retrieving past forecasts. OpenWeatherMap is also an option for current forecasts but less suited for historical comparison.
        * **API Key:** Assume a placeholder for the API key (e.g., `OPENMETEO_API_KEY`) loaded from environment variables or a configuration file.
    * **Data Points to Fetch:** Minimum: `temperature`, `humidity`, `pressure`, `precipitation` (rain/snow amount), `wind_speed`, `cloud_cover`. Prioritize hourly data.
    * **Location:** Fixed to Berlin, Germany. Latitude and longitude for Berlin (e.g., `lat=52.5200, lon=13.4050`).
    * **Forecast Retrieval Strategy:**
        * The system should be designed to run periodically (e.g., via a cron job or systemd timer).
        * Each time it runs, it should fetch the *current forecast* for the next 5-7 days (or as much as the API provides reliably, hourly data is preferred).
    * **InfluxDB Storage Schema:** This is critical for accurate analysis of forecast vs. actual.
        * **Measurement:** A new measurement, e.g., `weather_forecasts`.
        * **Timestamp (`_time`):** The **forecasted time** (the timestamp the prediction is *for*).
        * **Fields:** All forecast variables (e.g., `temperature`, `humidity`, `pressure`, `precipitation`, `wind_speed`, `cloud_cover`).
        * **Tags:**
            * `source`: `openmeteo` (or `openweathermap`, etc.)
            * `forecast_run_time`: **Crucially, a tag representing the timestamp (ISO 8601 string or Unix timestamp) of *when this specific forecast was retrieved/generated***. This tag ensures that different forecasts made for the *same future timestamp* are uniquely identifiable.
            * `forecast_horizon_hours`: (Optional but useful) An integer tag representing the number of hours from `forecast_run_time` to the `_time` of the data point. (e.g., a forecast made at 10:00 for 12:00 has a horizon of 2 hours).
    * **New Functions:**
        * `fetch_forecast_data(location_lat: float, location_lon: float, api_key: str) -> pd.DataFrame`: Fetches the raw forecast data.
        * `prepare_forecast_for_influxdb(df_forecast_raw: pd.DataFrame, forecast_run_time: datetime, source: str) -> list[Point]`: Transforms the raw DataFrame into InfluxDB `Point` objects with appropriate fields and tags.
        * `write_forecast_to_influxdb(points: list[Point], bucket: str, org: str) -> None`: Writes the prepared points to InfluxDB.

### 3.2. Feature: Calculate and Store Forecast Accuracy Metrics

* **Objective:** For historical time points where both sensor data and corresponding forecasts are available, calculate forecast errors and store these errors in InfluxDB. This pre-computation will simplify Grafana queries.
* **Sub-requirements:**
    * **Retrieval of Actuals & Forecasts:** Query historical sensor data (`weather_sensors`) and historical forecast data (`weather_forecasts`) for overlapping time ranges, ensuring to fetch forecasts made for specific `forecast_run_time` and `forecast_horizon_hours` (e.g., the 24-hour-ahead forecast).
    * **Alignment:** Align actual sensor data with relevant forecast data points. This will involve matching `_time` values.
    * **Error Calculation:**
        * Calculate the **absolute error** (`|actual - forecast|`) for `temperature`, `pressure`, and `humidity`.
        * Calculate the **signed error** (`forecast - actual`) for `temperature`, `pressure`, and `humidity` (to identify bias).
    * **InfluxDB Storage Schema for Errors:**
        * **Measurement:** A new measurement, e.g., `weather_forecast_errors`.
        * **Timestamp (`_time`):** The `_time` of the actual event (when the sensor reading occurred).
        * **Fields:**
            * `temp_abs_error`: (float)
            * `temp_signed_error`: (float)
            * `pressure_abs_error`: (float)
            * `pressure_signed_error`: (float)
            * `humidity_abs_error`: (float)
            * (and so on for other relevant variables if desired).
        * **Tags:**
            * `source`: `openmeteo` (or `openweathermap`, etc.)
            * `forecast_horizon_hours`: (int) The horizon of the forecast this error refers to (e.g., 24 hours). This is crucial for analyzing how error changes with forecast lead time.
    * **New Function:** `calculate_and_store_forecast_errors(bucket_sensor: str, bucket_forecast: str, bucket_errors: str, org: str, lookback_time: str = '48h') -> None`. This function would be designed to run periodically and process newly available actuals and their corresponding past forecasts.

### 3.3. Feature: Automated Data Profiling (Python)

* **Objective:** Generate a comprehensive report for data quality and initial insights from the *sensor data only*. This will still be a useful internal report for the developer.
* **Tool:** `ydata-profiling`.
* **Output:** Generate an HTML report file in a `reports/` directory. This report will be a static artifact, not directly integrated into Grafana.
* **New Function:** `generate_sensor_data_profile_report(df_sensor: pd.DataFrame, output_path: str = "reports/sensor_data_profile_report.html") -> None`.

### 3.4. Feature: Association Rule Mining (Python)

* **Objective:** Automatically discover "if X and Y, then Z" patterns in the historical *sensor data*. This analysis remains valuable for understanding inherent relationships in your local environment, independent of forecasts.
* **Tool:** `mlxtend.frequent_patterns.apriori` and `association_rules`.
* **Process:**
    1.  **Discretization:** Convert continuous numerical data (pressure, temperature, humidity) from the sensor data into discrete categories (e.g., 'low', 'medium', 'high').
    2.  **Rule Generation:** Apply Apriori and extract association rules.
* **Output:** Print the most significant rules (based on configurable `min_support`, `min_confidence`, `min_lift`) to the console or log file.
* **New Function:** `discover_sensor_association_rules(df_sensor: pd.DataFrame, columns_to_bin: list[str], n_bins: int = 3, min_support: float = 0.05, min_confidence: float = 0.5, min_lift: float = 1.0) -> pd.DataFrame`.

## 4. Grafana Visualization Requirements (No Python Implementation Needed Here)

The Python script will **not** generate visualizations directly. Instead, it will ensure all necessary data is correctly structured and stored in InfluxDB so that Grafana can be configured manually to create the following dashboards and panels:

* **Dashboard 1: Live Weather & Forecast Comparison**
    * **Panel: Actual vs. Forecast Temperature (Time Series)**
        * Plots `weather_sensors.temperature` and `weather_forecasts.temperature` (filtered by `forecast_horizon_hours=X` and `forecast_run_time` within a reasonable recent window).
    * **Panel: Actual vs. Forecast Humidity/Pressure (Time Series)**
        * Similar to temperature, but for other variables.
    * **Panel: Current Forecast (Table/Stat)**
        * Shows current forecast for various variables for the next 24 hours.

* **Dashboard 2: Forecast Accuracy Analysis**
    * **Panel: Temperature Absolute Error Over Time (Time Series)**
        * Plots `weather_forecast_errors.temp_abs_error` (filtered by `forecast_horizon_hours`).
    * **Panel: Temperature Signed Error (Bias) Over Time (Time Series)**
        * Plots `weather_forecast_errors.temp_signed_error` (filtered by `forecast_horizon_hours`).
    * **Panel: Error Distribution (Histogram)**
        * For `temp_signed_error` or `temp_abs_error` for specific `forecast_horizon_hours`.
    * **Panel: MAE/RMSE/Bias Stats (Stat Panels)**
        * Single value panels showing `mean(temp_abs_error)`, `mean(temp_signed_error)` over a selected time range, grouped by `forecast_horizon_hours`.
    * **Panel: Actual vs. Forecast Scatter Plot (XY Chart)**
        * Plots `actual_temp` vs. `forecast_temp` for a specific `forecast_horizon_hours` (this would require a Flux query that can join actuals and forecasts for comparison, which might be easier if the combined data is already stored as calculated errors).

## 5. Technical Requirements & Constraints (Python Script)

* **Language:** Python 3.9+
* **Dependencies:**
    * `pandas`
    * `influxdb-client-3`
    * `requests` (for API calls)
    * `ydata-profiling`
    * `mlxtend`
    * `pytz` (for robust timezone handling with API data)
* **Code Style:** Adhere to PEP 8.
* **Modularity:** Encapsulate new functionality in functions/classes within appropriate modules (`data_ingestion.py`, `weather_api.py`, `data_storage.py`, `forecast_accuracy.py`, `analysis.py`, `reporting.py`).
* **Configuration:** API keys, database credentials, location (Berlin lat/lon), forecast API endpoint, InfluxDB bucket/measurement names, and analysis parameters (time ranges, binning strategies, support/confidence thresholds) should be configurable. **Do not hardcode sensitive information.**
* **Error Handling:** Robust error handling for API calls, network issues, InfluxDB connection/write problems.
* **Docstrings:** All new functions and classes must have clear docstrings.
* **Testing:** Provide basic unit tests for new functions, including mocked API responses and InfluxDB interactions.

## 6. Deliverables (Python Script)

The AI code assistant should output:

1.  **Modified/New Python Code:**
    * Updated existing modules.
    * New modules for forecast data fetching, storage, and accuracy calculation (`weather_api.py`, `data_storage.py`, `forecast_accuracy.py`).
    * An updated `requirements.txt`.
    * A main script (`main.py`) to orchestrate the process:
        1.  Fetch *current* forecast.
        2.  Store forecast in `weather_forecasts` measurement in InfluxDB.
        3.  Periodically fetch relevant historical sensor data and corresponding historical forecast data.
        4.  Calculate and store forecast errors in `weather_forecast_errors` measurement in InfluxDB.
        5.  Run data profiling on sensor data and generate HTML report.
        6.  Run association rule mining on sensor data and print/log results.
2.  **HTML Report:** The `sensor_data_profile_report.html` file in a `reports/` directory.
3.  **Console Output:** A summary of the most significant association rules found from sensor data.
4.  **ReadMe/Explanation:** Clear instructions on how to set up (API keys, InfluxDB), how to run the Python script (e.g., suggestions for cron/systemd setup), and crucially, **detailed guidance on how to configure Grafana dashboards to visualize the data** from the `weather_sensors`, `weather_forecasts`, and `weather_forecast_errors` measurements, including example Flux queries for the panels described in section 4.

## 7. Development Iteration / Feedback Loop

The AI code assistant should ask clarifying questions for any ambiguity and propose improvements.

## 8. Tone and Style

* **Code:** Clean, readable, well-commented, Pythonic.
* **Explanations:** Clear, concise, and helpful, particularly for setting up Grafana.