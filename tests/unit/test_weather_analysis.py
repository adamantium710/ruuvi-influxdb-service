"""
Unit tests for weather data analysis module.
Tests data profiling and association rule mining functionality.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile
import os

from src.weather.analysis import (
    WeatherDataAnalyzer, 
    DataAnalysisError, 
    InsufficientDataError
)
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = Mock(spec=Config)
    config.influxdb_host = "localhost"
    config.influxdb_port = 8086
    config.influxdb_token = "test-token"
    config.influxdb_org = "test-org"
    config.influxdb_bucket = "test-bucket"
    config.influxdb_timeout = 30
    config.influxdb_verify_ssl = False
    config.influxdb_enable_gzip = True
    config.influxdb_batch_size = 100
    config.influxdb_flush_interval = 10
    config.max_buffer_size = 1000
    config.influxdb_retry_attempts = 3
    config.influxdb_retry_delay = 1
    config.influxdb_retry_exponential_base = 2
    return config


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    return Mock(spec=ProductionLogger)


@pytest.fixture
def mock_performance_monitor():
    """Create mock performance monitor."""
    return Mock(spec=PerformanceMonitor)


@pytest.fixture
def mock_influxdb_client():
    """Create mock InfluxDB client."""
    client = Mock()
    client.is_connected.return_value = True
    client.bucket = "test-bucket"
    client.query = AsyncMock()
    return client


@pytest.fixture
def sample_sensor_data():
    """Create sample sensor data for testing."""
    np.random.seed(42)  # For reproducible tests
    
    # Generate 100 data points over 10 days
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=10),
        end=datetime.now(),
        periods=100
    )
    
    # Generate realistic sensor data with some correlation
    temperature = np.random.normal(20, 5, 100)  # 20°C ± 5°C
    humidity = np.random.normal(60, 15, 100)    # 60% ± 15%
    pressure = np.random.normal(1013, 20, 100)  # 1013 hPa ± 20 hPa
    
    # Add some correlation between temperature and humidity (inverse)
    humidity = humidity - 0.3 * (temperature - 20)
    humidity = np.clip(humidity, 0, 100)  # Keep humidity in valid range
    
    df = pd.DataFrame({
        'temperature': temperature,
        'humidity': humidity,
        'pressure': pressure
    }, index=dates)
    
    return df


@pytest.fixture
def small_sensor_data():
    """Create small sensor data for testing edge cases."""
    dates = pd.date_range(start=datetime.now() - timedelta(days=1), periods=5, freq='H')
    
    df = pd.DataFrame({
        'temperature': [20.0, 22.0, 24.0, 21.0, 19.0],
        'humidity': [60.0, 55.0, 50.0, 58.0, 65.0],
        'pressure': [1013.0, 1015.0, 1012.0, 1014.0, 1016.0]
    }, index=dates)
    
    return df


@pytest.fixture
def analyzer(mock_config, mock_logger, mock_performance_monitor, mock_influxdb_client):
    """Create WeatherDataAnalyzer instance for testing."""
    with patch('src.weather.analysis.RuuviInfluxDBClient', return_value=mock_influxdb_client):
        analyzer = WeatherDataAnalyzer(
            config=mock_config,
            logger=mock_logger,
            performance_monitor=mock_performance_monitor,
            influxdb_client=mock_influxdb_client
        )
        return analyzer


class TestWeatherDataAnalyzer:
    """Test cases for WeatherDataAnalyzer class."""
    
    def test_init_with_existing_client(self, mock_config, mock_logger, mock_performance_monitor, mock_influxdb_client):
        """Test initialization with existing InfluxDB client."""
        analyzer = WeatherDataAnalyzer(
            config=mock_config,
            logger=mock_logger,
            performance_monitor=mock_performance_monitor,
            influxdb_client=mock_influxdb_client
        )
        
        assert analyzer.influxdb_client == mock_influxdb_client
        assert not analyzer._owns_client
        assert analyzer.reports_dir.exists()
    
    def test_init_without_client(self, mock_config, mock_logger, mock_performance_monitor):
        """Test initialization without existing InfluxDB client."""
        with patch('src.weather.analysis.RuuviInfluxDBClient') as mock_client_class:
            analyzer = WeatherDataAnalyzer(
                config=mock_config,
                logger=mock_logger,
                performance_monitor=mock_performance_monitor
            )
            
            mock_client_class.assert_called_once_with(mock_config, mock_logger, mock_performance_monitor)
            assert analyzer._owns_client
    
    @pytest.mark.asyncio
    async def test_connect_with_owned_client(self, analyzer):
        """Test connection when analyzer owns the client."""
        analyzer._owns_client = True
        analyzer.influxdb_client.connect = AsyncMock(return_value=True)
        
        result = await analyzer.connect()
        
        assert result is True
        analyzer.influxdb_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_with_external_client(self, analyzer):
        """Test connection when using external client."""
        analyzer._owns_client = False
        analyzer.influxdb_client.is_connected.return_value = True
        
        result = await analyzer.connect()
        
        assert result is True
        analyzer.influxdb_client.is_connected.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_sensor_data_for_analysis_success(self, analyzer):
        """Test successful sensor data retrieval."""
        # Mock query results
        mock_results = [
            {
                '_time': '2023-01-01T12:00:00Z',
                'temperature': 20.5,
                'humidity': 65.0,
                'pressure': 1013.25,
                'sensor_mac': 'AA:BB:CC:DD:EE:FF'
            },
            {
                '_time': '2023-01-01T13:00:00Z',
                'temperature': 21.0,
                'humidity': 63.0,
                'pressure': 1014.0,
                'sensor_mac': 'AA:BB:CC:DD:EE:FF'
            }
        ]
        
        analyzer.influxdb_client.query.return_value = mock_results
        
        start_time = datetime(2023, 1, 1, 10, 0, 0)
        end_time = datetime(2023, 1, 1, 14, 0, 0)
        
        result = await analyzer.get_sensor_data_for_analysis(start_time, end_time)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ['temperature', 'humidity', 'pressure']
        assert result.index.name == '_time'
        
        # Verify query was called with correct parameters
        analyzer.influxdb_client.query.assert_called_once()
        query_call = analyzer.influxdb_client.query.call_args[0][0]
        assert 'ruuvi_environmental' in query_call
        assert start_time.isoformat() in query_call
        assert end_time.isoformat() in query_call
    
    @pytest.mark.asyncio
    async def test_get_sensor_data_no_results(self, analyzer):
        """Test sensor data retrieval with no results."""
        analyzer.influxdb_client.query.return_value = []
        
        start_time = datetime(2023, 1, 1, 10, 0, 0)
        
        with pytest.raises(InsufficientDataError, match="No sensor data found"):
            await analyzer.get_sensor_data_for_analysis(start_time)
    
    @pytest.mark.asyncio
    async def test_get_sensor_data_with_mac_filter(self, analyzer):
        """Test sensor data retrieval with MAC address filter."""
        analyzer.influxdb_client.query.return_value = [
            {
                '_time': '2023-01-01T12:00:00Z',
                'temperature': 20.5,
                'humidity': 65.0,
                'pressure': 1013.25
            }
        ]
        
        start_time = datetime(2023, 1, 1, 10, 0, 0)
        mac_address = "AA:BB:CC:DD:EE:FF"
        
        await analyzer.get_sensor_data_for_analysis(start_time, mac_address=mac_address)
        
        query_call = analyzer.influxdb_client.query.call_args[0][0]
        assert f'r["sensor_mac"] == "{mac_address}"' in query_call
    
    def test_generate_sensor_data_profile_report_success(self, analyzer, sample_sensor_data):
        """Test successful profile report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "test_report.html")
            
            # Mock ProfileReport
            with patch('src.weather.analysis.ProfileReport') as mock_profile:
                mock_profile_instance = Mock()
                mock_profile.return_value = mock_profile_instance
                
                analyzer.generate_sensor_data_profile_report(sample_sensor_data, output_path)
                
                # Verify ProfileReport was created and saved
                mock_profile.assert_called_once()
                mock_profile_instance.to_file.assert_called_once_with(Path(output_path))
                
                # Verify performance metrics were recorded
                analyzer.performance_monitor.record_metric.assert_any_call(
                    "profile_report_generation_time", pytest.approx(0, abs=10)
                )
                analyzer.performance_monitor.record_metric.assert_any_call(
                    "profile_report_data_points", len(sample_sensor_data)
                )
    
    def test_generate_sensor_data_profile_report_empty_data(self, analyzer):
        """Test profile report generation with empty DataFrame."""
        empty_df = pd.DataFrame()
        
        with pytest.raises(InsufficientDataError, match="DataFrame is empty"):
            analyzer.generate_sensor_data_profile_report(empty_df)
    
    def test_generate_sensor_data_profile_report_insufficient_data(self, analyzer):
        """Test profile report generation with insufficient data."""
        small_df = pd.DataFrame({
            'temperature': [20.0, 21.0],
            'humidity': [60.0, 65.0]
        })
        
        with pytest.raises(InsufficientDataError, match="Insufficient data for profiling"):
            analyzer.generate_sensor_data_profile_report(small_df)
    
    def test_discretize_continuous_data_success(self, analyzer, sample_sensor_data):
        """Test successful data discretization."""
        columns_to_bin = ['temperature', 'humidity', 'pressure']
        
        result = analyzer._discretize_continuous_data(sample_sensor_data, columns_to_bin, n_bins=3)
        
        # Check that binned columns were created
        expected_binned_columns = ['temperature_binned', 'humidity_binned', 'pressure_binned']
        for col in expected_binned_columns:
            assert col in result.columns
            assert result[col].dtype.name == 'category'
            assert set(result[col].dropna().unique()).issubset({'low', 'medium', 'high'})
    
    def test_discretize_continuous_data_missing_column(self, analyzer, sample_sensor_data):
        """Test discretization with missing column."""
        columns_to_bin = ['temperature', 'nonexistent_column']
        
        result = analyzer._discretize_continuous_data(sample_sensor_data, columns_to_bin, n_bins=3)
        
        # Should have temperature_binned but not nonexistent_column_binned
        assert 'temperature_binned' in result.columns
        assert 'nonexistent_column_binned' not in result.columns
    
    def test_discretize_continuous_data_insufficient_unique_values(self, analyzer):
        """Test discretization with insufficient unique values."""
        # Create data with only 2 unique values
        df = pd.DataFrame({
            'temperature': [20.0, 20.0, 21.0, 21.0, 20.0]
        })
        
        result = analyzer._discretize_continuous_data(df, ['temperature'], n_bins=3)
        
        # Should fallback to 2 bins or handle gracefully
        if 'temperature_binned' in result.columns:
            unique_bins = result['temperature_binned'].dropna().unique()
            assert len(unique_bins) <= 2
    
    def test_discover_sensor_association_rules_success(self, analyzer, sample_sensor_data):
        """Test successful association rule mining."""
        columns_to_bin = ['temperature', 'humidity', 'pressure']
        
        with patch.object(analyzer, '_print_significant_rules'):
            result = analyzer.discover_sensor_association_rules(
                sample_sensor_data,
                columns_to_bin,
                n_bins=3,
                min_support=0.1,
                min_confidence=0.5,
                min_lift=1.0
            )
        
        assert isinstance(result, pd.DataFrame)
        
        if not result.empty:
            # Check that required columns exist
            required_columns = ['antecedents', 'consequents', 'support', 'confidence', 'lift']
            for col in required_columns:
                assert col in result.columns
            
            # Check that rules meet minimum thresholds
            assert all(result['confidence'] >= 0.5)
            assert all(result['lift'] >= 1.0)
            assert all(result['support'] >= 0.1)
            
            # Check that string representations were added
            assert 'antecedents_str' in result.columns
            assert 'consequents_str' in result.columns
    
    def test_discover_sensor_association_rules_empty_data(self, analyzer):
        """Test association rule mining with empty DataFrame."""
        empty_df = pd.DataFrame()
        
        with pytest.raises(InsufficientDataError, match="DataFrame is empty"):
            analyzer.discover_sensor_association_rules(empty_df, ['temperature'])
    
    def test_discover_sensor_association_rules_insufficient_data(self, analyzer, small_sensor_data):
        """Test association rule mining with insufficient data."""
        with pytest.raises(InsufficientDataError, match="Insufficient data for association rule mining"):
            analyzer.discover_sensor_association_rules(small_sensor_data, ['temperature'])
    
    def test_discover_sensor_association_rules_no_frequent_itemsets(self, analyzer, sample_sensor_data):
        """Test association rule mining when no frequent itemsets are found."""
        # Use very high support threshold
        with patch.object(analyzer, '_print_significant_rules'):
            result = analyzer.discover_sensor_association_rules(
                sample_sensor_data,
                ['temperature', 'humidity'],
                min_support=0.9,  # Very high threshold
                min_confidence=0.5,
                min_lift=1.0
            )
        
        assert isinstance(result, pd.DataFrame)
        assert result.empty
    
    def test_print_significant_rules_empty(self, analyzer):
        """Test printing rules with empty DataFrame."""
        empty_rules = pd.DataFrame()
        
        analyzer._print_significant_rules(empty_rules)
        
        # Should log that no rules were found
        analyzer.logger.info.assert_any_call("No significant association rules found")
    
    def test_print_significant_rules_with_data(self, analyzer):
        """Test printing rules with actual data."""
        # Create mock rules DataFrame
        rules_data = {
            'antecedents_str': ['temperature_high', 'humidity_low'],
            'consequents_str': ['pressure_high', 'temperature_medium'],
            'support': [0.3, 0.2],
            'confidence': [0.8, 0.7],
            'lift': [1.5, 1.3]
        }
        rules_df = pd.DataFrame(rules_data)
        
        analyzer._print_significant_rules(rules_df, max_rules=5)
        
        # Should log rule information
        analyzer.logger.info.assert_any_call("=== SIGNIFICANT ASSOCIATION RULES ===")
        
        # Check that rule details were logged
        info_calls = [call.args[0] for call in analyzer.logger.info.call_args_list]
        rule_logs = [call for call in info_calls if 'Rule' in call and '→' in call]
        assert len(rule_logs) == 2  # Should log both rules
    
    @pytest.mark.asyncio
    async def test_run_comprehensive_analysis_success(self, analyzer, sample_sensor_data):
        """Test successful comprehensive analysis."""
        # Mock data retrieval
        analyzer.get_sensor_data_for_analysis = AsyncMock(return_value=sample_sensor_data)
        
        # Mock profile report generation
        with patch.object(analyzer, 'generate_sensor_data_profile_report') as mock_profile:
            # Mock association rule mining
            mock_rules = pd.DataFrame({
                'antecedents_str': ['temperature_high'],
                'consequents_str': ['humidity_low'],
                'support': [0.3],
                'confidence': [0.8],
                'lift': [1.5]
            })
            
            with patch.object(analyzer, 'discover_sensor_association_rules', return_value=mock_rules):
                result = await analyzer.run_comprehensive_analysis(
                    days_back=7,
                    profile_report=True,
                    association_rules=True
                )
        
        # Verify result structure
        assert 'data_points' in result
        assert 'time_range' in result
        assert 'columns' in result
        assert 'analysis_timestamp' in result
        assert 'profile_report' in result
        assert 'association_rules' in result
        
        # Verify profile report results
        assert result['profile_report']['generated'] is True
        assert 'path' in result['profile_report']
        
        # Verify association rules results
        assert result['association_rules']['generated'] is True
        assert result['association_rules']['rules_found'] == 1
        assert 'top_rules' in result['association_rules']
        assert len(result['association_rules']['top_rules']) == 1
        
        # Verify data retrieval was called correctly
        analyzer.get_sensor_data_for_analysis.assert_called_once()
        call_args = analyzer.get_sensor_data_for_analysis.call_args
        assert 'start_time' in call_args.kwargs
        assert 'end_time' in call_args.kwargs
    
    @pytest.mark.asyncio
    async def test_run_comprehensive_analysis_profile_error(self, analyzer, sample_sensor_data):
        """Test comprehensive analysis with profile report error."""
        analyzer.get_sensor_data_for_analysis = AsyncMock(return_value=sample_sensor_data)
        
        # Mock profile report to raise error
        with patch.object(analyzer, 'generate_sensor_data_profile_report', 
                         side_effect=Exception("Profile error")):
            with patch.object(analyzer, 'discover_sensor_association_rules', 
                             return_value=pd.DataFrame()):
                result = await analyzer.run_comprehensive_analysis(
                    days_back=7,
                    profile_report=True,
                    association_rules=True
                )
        
        # Profile report should show error
        assert result['profile_report']['generated'] is False
        assert 'error' in result['profile_report']
        assert result['profile_report']['error'] == "Profile error"
        
        # Association rules should still work
        assert result['association_rules']['generated'] is True
    
    @pytest.mark.asyncio
    async def test_run_comprehensive_analysis_rules_error(self, analyzer, sample_sensor_data):
        """Test comprehensive analysis with association rules error."""
        analyzer.get_sensor_data_for_analysis = AsyncMock(return_value=sample_sensor_data)
        
        with patch.object(analyzer, 'generate_sensor_data_profile_report'):
            # Mock association rules to raise error
            with patch.object(analyzer, 'discover_sensor_association_rules',
                             side_effect=Exception("Rules error")):
                result = await analyzer.run_comprehensive_analysis(
                    days_back=7,
                    profile_report=True,
                    association_rules=True
                )
        
        # Profile report should work
        assert result['profile_report']['generated'] is True
        
        # Association rules should show error
        assert result['association_rules']['generated'] is False
        assert 'error' in result['association_rules']
        assert result['association_rules']['error'] == "Rules error"


@pytest.mark.asyncio
async def test_analyzer_integration():
    """Integration test for the analyzer with mocked dependencies."""
    # Create realistic test data
    dates = pd.date_range(start=datetime.now() - timedelta(days=5), periods=50, freq='H')
    np.random.seed(42)
    
    df = pd.DataFrame({
        'temperature': np.random.normal(20, 3, 50),
        'humidity': np.random.normal(60, 10, 50),
        'pressure': np.random.normal(1013, 15, 50)
    }, index=dates)
    
    # Mock all dependencies
    with patch('src.weather.analysis.RuuviInfluxDBClient') as mock_client_class:
        mock_client = Mock()
        mock_client.is_connected.return_value = True
        mock_client_class.return_value = mock_client
        
        config = Mock()
        logger = Mock()
        performance_monitor = Mock()
        
        analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
        
        # Mock data retrieval
        analyzer.get_sensor_data_for_analysis = AsyncMock(return_value=df)
        
        # Run analysis
        with patch('src.weather.analysis.ProfileReport') as mock_profile:
            mock_profile_instance = Mock()
            mock_profile.return_value = mock_profile_instance
            
            result = await analyzer.run_comprehensive_analysis(days_back=5)
        
        # Verify basic structure
        assert result['data_points'] == 50
        assert result['profile_report']['generated'] is True
        assert result['association_rules']['generated'] is True


if __name__ == "__main__":
    pytest.main([__file__])