"""
Weather data analysis module for sensor data profiling and association rule mining.
Implements Phase 2 data analysis features as specified in the project requirements.
"""

import os
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# Data profiling
from ydata_profiling import ProfileReport
from ydata_profiling.config import Settings

# Association rule mining
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

from ..influxdb.client import RuuviInfluxDBClient
from ..utils.config import Config
from ..utils.logging import ProductionLogger, PerformanceMonitor


class DataAnalysisError(Exception):
    """Base exception for data analysis operations."""
    pass


class InsufficientDataError(DataAnalysisError):
    """Exception raised when there's insufficient data for analysis."""
    pass


class WeatherDataAnalyzer:
    """
    Weather data analyzer for sensor data profiling and association rule mining.
    
    Features:
    - Automated data profiling using ydata-profiling
    - Association rule mining using mlxtend
    - Data discretization for continuous variables
    - Integration with existing InfluxDB patterns
    """
    
    def __init__(self, config: Config, logger: ProductionLogger, 
                 performance_monitor: PerformanceMonitor,
                 influxdb_client: Optional[RuuviInfluxDBClient] = None):
        """
        Initialize weather data analyzer.
        
        Args:
            config: Application configuration
            logger: Logger instance
            performance_monitor: Performance monitoring instance
            influxdb_client: Optional existing InfluxDB client
        """
        self.config = config
        self.logger = logger
        self.performance_monitor = performance_monitor
        
        # Use existing client or create new one
        if influxdb_client:
            self.influxdb_client = influxdb_client
            self._owns_client = False
        else:
            self.influxdb_client = RuuviInfluxDBClient(config, logger, performance_monitor)
            self._owns_client = True
        
        # Analysis configuration
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
        
        self.logger.info("WeatherDataAnalyzer initialized")
    
    async def connect(self) -> bool:
        """Connect to InfluxDB if we own the client."""
        if self._owns_client:
            return await self.influxdb_client.connect()
        return self.influxdb_client.is_connected()
    
    async def disconnect(self):
        """Disconnect from InfluxDB if we own the client."""
        if self._owns_client:
            await self.influxdb_client.disconnect()
    
    async def get_sensor_data_for_analysis(self, 
                                         start_time: datetime,
                                         end_time: Optional[datetime] = None,
                                         mac_address: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieve sensor data from InfluxDB for analysis.
        
        Args:
            start_time: Start time for data retrieval
            end_time: End time for data retrieval (defaults to now)
            mac_address: Optional MAC address filter
            
        Returns:
            pd.DataFrame: Sensor data with time index
            
        Raises:
            DataAnalysisError: If data retrieval fails
            InsufficientDataError: If insufficient data is available
        """
        if end_time is None:
            end_time = datetime.utcnow()
        
        try:
            # Build Flux query for environmental sensor data
            flux_query = f'''
            from(bucket: "{self.influxdb_client.bucket}")
              |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
              |> filter(fn: (r) => r["_measurement"] == "ruuvi_environmental")
            '''
            
            if mac_address:
                flux_query += f'  |> filter(fn: (r) => r["sensor_mac"] == "{mac_address}")\n'
            
            flux_query += '''
              |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
              |> sort(columns: ["_time"])
            '''
            
            # Execute query
            results = await self.influxdb_client.query(flux_query)
            
            if not results:
                raise InsufficientDataError("No sensor data found for the specified time range")
            
            # Convert to DataFrame
            df = pd.DataFrame(results)
            
            # Set time as index if available
            if '_time' in df.columns:
                df['_time'] = pd.to_datetime(df['_time'])
                df.set_index('_time', inplace=True)
            
            # Select relevant columns for analysis
            analysis_columns = ['temperature', 'humidity', 'pressure']
            available_columns = [col for col in analysis_columns if col in df.columns]
            
            if not available_columns:
                raise InsufficientDataError("No environmental sensor data columns found")
            
            # Filter to analysis columns and remove rows with all NaN values
            df_analysis = df[available_columns].dropna(how='all')
            
            if df_analysis.empty:
                raise InsufficientDataError("No valid sensor data after filtering")
            
            self.logger.info(f"Retrieved {len(df_analysis)} sensor data points for analysis")
            return df_analysis
            
        except Exception as e:
            if isinstance(e, (DataAnalysisError, InsufficientDataError)):
                raise
            self.logger.error(f"Error retrieving sensor data for analysis: {e}")
            raise DataAnalysisError(f"Data retrieval failed: {e}")
    
    def generate_sensor_data_profile_report(self, 
                                          df_sensor: pd.DataFrame,
                                          output_path: str = "reports/sensor_data_profile_report.html") -> None:
        """
        Generate comprehensive data profiling report for sensor data using ydata-profiling.
        
        Args:
            df_sensor: Sensor data DataFrame
            output_path: Output path for HTML report
            
        Raises:
            DataAnalysisError: If report generation fails
            InsufficientDataError: If DataFrame is empty or invalid
        """
        try:
            # Validate input data
            if df_sensor.empty:
                raise InsufficientDataError("Cannot generate profile report: DataFrame is empty")
            
            # Check for minimum data requirements
            if len(df_sensor) < 10:
                raise InsufficientDataError(
                    f"Insufficient data for profiling: {len(df_sensor)} rows (minimum 10 required)"
                )
            
            self.logger.info(f"Generating data profile report for {len(df_sensor)} sensor data points")
            
            # Ensure output directory exists
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Configure profile report using Settings object
            profile_config = Settings()
            profile_config.title = "Ruuvi Sensor Data Profile Report"
            profile_config.dataset.description = "Environmental sensor data from Ruuvi sensors including temperature, humidity, and pressure measurements."
            profile_config.dataset.creator = "Ruuvi Weather Analysis System"
            profile_config.dataset.author = "Weather Data Analyzer"
            profile_config.dataset.copyright_holder = "Ruuvi Project"
            profile_config.dataset.copyright_year = datetime.now().year
            
            # Variable descriptions
            profile_config.variables.descriptions = {
                "temperature": "Temperature measurement in degrees Celsius",
                "humidity": "Relative humidity percentage (0-100%)",
                "pressure": "Atmospheric pressure in hectopascals (hPa)"
            }
            
            # Enable correlations (access as dictionary)
            profile_config.correlations["auto"].calculate = True
            profile_config.correlations["pearson"].calculate = True
            profile_config.correlations["spearman"].calculate = True
            profile_config.correlations["kendall"].calculate = True
            profile_config.correlations["phi_k"].calculate = True
            profile_config.correlations["cramers"].calculate = True
            
            # Enable missing value diagrams (access as dictionary)
            profile_config.missing_diagrams["bar"] = True
            profile_config.missing_diagrams["matrix"] = True
            profile_config.missing_diagrams["heatmap"] = True
            if "dendrogram" in profile_config.missing_diagrams:
                profile_config.missing_diagrams["dendrogram"] = True
            
            # Enable interactions (access as attributes)
            profile_config.interactions.continuous = True
            
            # Sample settings (access as attributes)
            profile_config.samples.head = 10
            profile_config.samples.tail = 10
            profile_config.samples.random = 10
            
            # Generate profile report
            start_time = datetime.now()
            
            profile = ProfileReport(
                df_sensor,
                config=profile_config,
                minimal=False,
                explorative=True
            )
            
            # Save report
            profile.to_file(output_path)
            
            generation_time = (datetime.now() - start_time).total_seconds()
            
            # Update performance metrics
            self.performance_monitor.record_metric("profile_report_generation_time", generation_time)
            self.performance_monitor.record_metric("profile_report_data_points", len(df_sensor))
            
            self.logger.info(f"Data profile report generated successfully in {generation_time:.2f}s")
            self.logger.info(f"Report saved to: {output_path.absolute()}")
            
        except Exception as e:
            if isinstance(e, (DataAnalysisError, InsufficientDataError)):
                raise
            self.logger.error(f"Error generating data profile report: {e}")
            raise DataAnalysisError(f"Profile report generation failed: {e}")
    
    def _discretize_continuous_data(self, 
                                  df: pd.DataFrame, 
                                  columns_to_bin: List[str], 
                                  n_bins: int = 3) -> pd.DataFrame:
        """
        Discretize continuous sensor data into categorical bins.
        
        Args:
            df: Input DataFrame with continuous data
            columns_to_bin: List of column names to discretize
            n_bins: Number of bins for discretization
            
        Returns:
            pd.DataFrame: DataFrame with discretized columns
            
        Raises:
            DataAnalysisError: If discretization fails
        """
        try:
            df_discretized = df.copy()
            bin_info = {}
            
            for column in columns_to_bin:
                if column not in df.columns:
                    self.logger.warning(f"Column '{column}' not found in DataFrame, skipping")
                    continue
                
                # Remove NaN values for binning
                valid_data = df[column].dropna()
                
                if len(valid_data) < n_bins:
                    self.logger.warning(f"Insufficient data for binning column '{column}', skipping")
                    continue
                
                # Create bins using quantiles for equal-frequency binning
                try:
                    # First, create the quantile bins to get the bin edges
                    qcut_result = pd.qcut(valid_data, q=n_bins, duplicates='drop')
                    bin_edges = qcut_result.cat.categories
                    
                    # Extract the right edges for pd.cut (add left edge of first bin)
                    cut_bins = [bin_edges[0].left] + [edge.right for edge in bin_edges]
                    
                    # Apply binning to the full column (preserving NaN)
                    df_discretized[f"{column}_binned"] = pd.cut(
                        df[column],
                        bins=cut_bins,
                        labels=['low', 'medium', 'high'][:n_bins],
                        include_lowest=True
                    )
                    
                    # Store bin information for logging
                    bin_info[column] = {
                        'bins': n_bins,
                        'edges': [f"{edge.left:.2f}-{edge.right:.2f}" for edge in bin_edges]
                    }
                    
                except ValueError as e:
                    self.logger.warning(f"Could not create {n_bins} bins for '{column}': {e}")
                    # Fallback to fewer bins
                    try:
                        qcut_result = pd.qcut(valid_data, q=2, duplicates='drop')
                        bin_edges = qcut_result.cat.categories
                        cut_bins = [bin_edges[0].left] + [edge.right for edge in bin_edges]
                        
                        df_discretized[f"{column}_binned"] = pd.cut(
                            df[column],
                            bins=cut_bins,
                            labels=['low', 'high'],
                            include_lowest=True
                        )
                        bin_info[column] = {'bins': 2, 'fallback': True}
                    except ValueError:
                        self.logger.warning(f"Could not discretize column '{column}' at all, skipping")
                        continue
            
            # Log binning information
            for column, info in bin_info.items():
                if 'edges' in info:
                    self.logger.info(f"Discretized '{column}' into {info['bins']} bins: {info['edges']}")
                else:
                    self.logger.info(f"Discretized '{column}' with fallback to {info['bins']} bins")
            
            return df_discretized
            
        except Exception as e:
            self.logger.error(f"Error discretizing continuous data: {e}")
            raise DataAnalysisError(f"Data discretization failed: {e}")
    
    def discover_sensor_association_rules(self, 
                                        df_sensor: pd.DataFrame,
                                        columns_to_bin: List[str],
                                        n_bins: int = 3,
                                        min_support: float = 0.05,
                                        min_confidence: float = 0.5,
                                        min_lift: float = 1.0) -> pd.DataFrame:
        """
        Discover association rules in sensor data using Apriori algorithm.
        
        Args:
            df_sensor: Sensor data DataFrame
            columns_to_bin: List of columns to discretize for rule mining
            n_bins: Number of bins for discretization (default: 3)
            min_support: Minimum support threshold (default: 0.05)
            min_confidence: Minimum confidence threshold (default: 0.5)
            min_lift: Minimum lift threshold (default: 1.0)
            
        Returns:
            pd.DataFrame: Association rules with metrics
            
        Raises:
            DataAnalysisError: If rule mining fails
            InsufficientDataError: If insufficient data for analysis
        """
        try:
            # Validate input data
            if df_sensor.empty:
                raise InsufficientDataError("Cannot mine association rules: DataFrame is empty")
            
            if len(df_sensor) < 20:
                raise InsufficientDataError(
                    f"Insufficient data for association rule mining: {len(df_sensor)} rows (minimum 20 required)"
                )
            
            self.logger.info(f"Starting association rule mining on {len(df_sensor)} sensor data points")
            
            # Discretize continuous data
            df_discretized = self._discretize_continuous_data(df_sensor, columns_to_bin, n_bins)
            
            # Select binned columns for transaction encoding
            binned_columns = [f"{col}_binned" for col in columns_to_bin if f"{col}_binned" in df_discretized.columns]
            
            if not binned_columns:
                raise InsufficientDataError("No successfully discretized columns available for rule mining")
            
            # Remove rows with any NaN values in binned columns
            df_clean = df_discretized[binned_columns].dropna()
            
            if df_clean.empty:
                raise InsufficientDataError("No valid data remaining after removing NaN values")
            
            self.logger.info(f"Using {len(df_clean)} clean data points with columns: {binned_columns}")
            
            # Create transactions for association rule mining
            # Each row becomes a transaction with items like "temperature_low", "humidity_high", etc.
            transactions = []
            
            for _, row in df_clean.iterrows():
                transaction = []
                for col in binned_columns:
                    if pd.notna(row[col]):
                        # Create item name like "temperature_low"
                        item_name = f"{col.replace('_binned', '')}_{row[col]}"
                        transaction.append(item_name)
                
                if transaction:  # Only add non-empty transactions
                    transactions.append(transaction)
            
            if not transactions:
                raise InsufficientDataError("No valid transactions created for rule mining")
            
            self.logger.info(f"Created {len(transactions)} transactions for rule mining")
            
            # Encode transactions for mlxtend
            te = TransactionEncoder()
            te_ary = te.fit(transactions).transform(transactions)
            df_encoded = pd.DataFrame(te_ary, columns=te.columns_)
            
            # Apply Apriori algorithm to find frequent itemsets
            self.logger.info(f"Running Apriori algorithm with min_support={min_support}")
            
            frequent_itemsets = apriori(df_encoded, min_support=min_support, use_colnames=True)
            
            if frequent_itemsets.empty:
                self.logger.warning(f"No frequent itemsets found with min_support={min_support}")
                return pd.DataFrame()
            
            self.logger.info(f"Found {len(frequent_itemsets)} frequent itemsets")
            
            # Generate association rules
            self.logger.info(f"Generating association rules with min_confidence={min_confidence}")
            
            rules = association_rules(
                frequent_itemsets, 
                metric="confidence", 
                min_threshold=min_confidence,
                num_itemsets=len(frequent_itemsets)
            )
            
            if rules.empty:
                self.logger.warning(f"No association rules found with min_confidence={min_confidence}")
                return pd.DataFrame()
            
            # Filter by lift threshold
            rules_filtered = rules[rules['lift'] >= min_lift].copy()
            
            if rules_filtered.empty:
                self.logger.warning(f"No association rules found with min_lift={min_lift}")
                return pd.DataFrame()
            
            # Sort by lift (descending) and confidence (descending)
            rules_filtered = rules_filtered.sort_values(['lift', 'confidence'], ascending=False)
            
            # Format rules for better readability
            rules_filtered['antecedents_str'] = rules_filtered['antecedents'].apply(
                lambda x: ', '.join(list(x))
            )
            rules_filtered['consequents_str'] = rules_filtered['consequents'].apply(
                lambda x: ', '.join(list(x))
            )
            
            # Update performance metrics
            self.performance_monitor.record_metric("association_rules_found", len(rules_filtered))
            self.performance_monitor.record_metric("frequent_itemsets_found", len(frequent_itemsets))
            
            self.logger.info(f"Found {len(rules_filtered)} significant association rules")
            
            # Print significant rules to console
            self._print_significant_rules(rules_filtered)
            
            return rules_filtered
            
        except Exception as e:
            if isinstance(e, (DataAnalysisError, InsufficientDataError)):
                raise
            self.logger.error(f"Error in association rule mining: {e}")
            raise DataAnalysisError(f"Association rule mining failed: {e}")
    
    def _print_significant_rules(self, rules_df: pd.DataFrame, max_rules: int = 10):
        """
        Print significant association rules to console/log.
        
        Args:
            rules_df: DataFrame containing association rules
            max_rules: Maximum number of rules to print
        """
        if rules_df.empty:
            self.logger.info("No significant association rules found")
            return
        
        self.logger.info("=== SIGNIFICANT ASSOCIATION RULES ===")
        
        # Display top rules
        top_rules = rules_df.head(max_rules)
        
        for idx, rule in top_rules.iterrows():
            rule_str = (
                f"Rule {idx + 1}: {rule['antecedents_str']} → {rule['consequents_str']} "
                f"(Support: {rule['support']:.3f}, Confidence: {rule['confidence']:.3f}, "
                f"Lift: {rule['lift']:.3f})"
            )
            self.logger.info(rule_str)
        
        if len(rules_df) > max_rules:
            self.logger.info(f"... and {len(rules_df) - max_rules} more rules")
        
        # Summary statistics
        self.logger.info(f"\nRule Mining Summary:")
        self.logger.info(f"Total rules found: {len(rules_df)}")
        self.logger.info(f"Average confidence: {rules_df['confidence'].mean():.3f}")
        self.logger.info(f"Average lift: {rules_df['lift'].mean():.3f}")
        self.logger.info(f"Highest lift: {rules_df['lift'].max():.3f}")
    
    async def run_comprehensive_analysis(self, 
                                       days_back: int = 30,
                                       mac_address: Optional[str] = None,
                                       profile_report: bool = True,
                                       association_rules: bool = True,
                                       **rule_params) -> Dict[str, Any]:
        """
        Run comprehensive data analysis including profiling and rule mining.
        
        Args:
            days_back: Number of days of historical data to analyze
            mac_address: Optional MAC address filter
            profile_report: Whether to generate profile report
            association_rules: Whether to perform association rule mining
            **rule_params: Additional parameters for rule mining
            
        Returns:
            Dict[str, Any]: Analysis results summary
        """
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days_back)
            
            self.logger.info(f"Starting comprehensive analysis for {days_back} days of data")
            
            # Retrieve sensor data
            df_sensor = await self.get_sensor_data_for_analysis(
                start_time=start_time,
                end_time=end_time,
                mac_address=mac_address
            )
            
            results = {
                'data_points': len(df_sensor),
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'days': days_back
                },
                'columns': list(df_sensor.columns),
                'analysis_timestamp': datetime.utcnow().isoformat()
            }
            
            # Generate profile report
            if profile_report:
                try:
                    self.generate_sensor_data_profile_report(df_sensor)
                    results['profile_report'] = {
                        'generated': True,
                        'path': 'reports/sensor_data_profile_report.html'
                    }
                except Exception as e:
                    self.logger.error(f"Profile report generation failed: {e}")
                    results['profile_report'] = {
                        'generated': False,
                        'error': str(e)
                    }
            
            # Perform association rule mining
            if association_rules:
                try:
                    # Default rule mining parameters
                    rule_defaults = {
                        'columns_to_bin': ['temperature', 'humidity', 'pressure'],
                        'n_bins': 3,
                        'min_support': 0.05,
                        'min_confidence': 0.5,
                        'min_lift': 1.0
                    }
                    rule_defaults.update(rule_params)
                    
                    rules_df = self.discover_sensor_association_rules(df_sensor, **rule_defaults)
                    
                    results['association_rules'] = {
                        'generated': True,
                        'rules_found': len(rules_df),
                        'parameters': rule_defaults
                    }
                    
                    if not rules_df.empty:
                        # Add top rules summary
                        top_rules = rules_df.head(5)
                        results['association_rules']['top_rules'] = [
                            {
                                'antecedents': rule['antecedents_str'],
                                'consequents': rule['consequents_str'],
                                'support': float(rule['support']),
                                'confidence': float(rule['confidence']),
                                'lift': float(rule['lift'])
                            }
                            for _, rule in top_rules.iterrows()
                        ]
                    
                except Exception as e:
                    self.logger.error(f"Association rule mining failed: {e}")
                    results['association_rules'] = {
                        'generated': False,
                        'error': str(e)
                    }
            
            self.logger.info("Comprehensive analysis completed successfully")
            return results
            
        except Exception as e:
            self.logger.error(f"Comprehensive analysis failed: {e}")
            raise DataAnalysisError(f"Comprehensive analysis failed: {e}")


async def test_weather_data_analyzer(config: Config, logger: ProductionLogger,
                                   performance_monitor: PerformanceMonitor):
    """
    Test function for weather data analyzer.
    
    Args:
        config: Application configuration
        logger: Logger instance
        performance_monitor: Performance monitor instance
    """
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        # Connect
        await analyzer.connect()
        
        # Run comprehensive analysis
        results = await analyzer.run_comprehensive_analysis(
            days_back=7,  # Analyze last 7 days
            profile_report=True,
            association_rules=True,
            min_support=0.1,
            min_confidence=0.6
        )
        
        print("Analysis Results:")
        print(f"Data points analyzed: {results['data_points']}")
        print(f"Profile report: {results.get('profile_report', {}).get('generated', False)}")
        print(f"Association rules: {results.get('association_rules', {}).get('rules_found', 0)} rules found")
        
    finally:
        await analyzer.disconnect()


if __name__ == "__main__":
    # Simple test when run directly
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.utils.config import Config
    from src.utils.logging import ProductionLogger, PerformanceMonitor
    
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    asyncio.run(test_weather_data_analyzer(config, logger, performance_monitor))