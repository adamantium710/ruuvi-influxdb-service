"""
Weather API module for fetching forecast data from Open-Meteo.
Includes retry logic, rate limiting, and circuit breaker patterns.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

import requests
import pytz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..utils.config import Config


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class WeatherData:
    """Weather data point."""
    timestamp: datetime
    temperature: float
    humidity: float
    pressure: float
    wind_speed: float
    wind_direction: float
    precipitation: float
    cloud_cover: float
    visibility: Optional[float] = None
    uv_index: Optional[float] = None
    weather_code: Optional[int] = None
    is_forecast: bool = True


@dataclass
class ForecastData:
    """Complete forecast data response."""
    location_latitude: float
    location_longitude: float
    timezone: str
    current_weather: Optional[WeatherData] = None
    hourly_forecasts: List[WeatherData] = field(default_factory=list)
    daily_forecasts: List[WeatherData] = field(default_factory=list)
    retrieved_at: datetime = field(default_factory=datetime.utcnow)


class RateLimiter:
    """Simple rate limiter for API requests."""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds (default: 60)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """
        Acquire permission to make a request.
        
        Returns:
            bool: True if request is allowed
        """
        async with self._lock:
            now = time.time()
            
            # Remove old requests outside time window
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            # Check if we can make a new request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
    
    async def wait_for_slot(self) -> None:
        """Wait until a request slot becomes available."""
        while not await self.acquire():
            await asyncio.sleep(1)


class CircuitBreaker:
    """Circuit breaker for API fault tolerance."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if (time.time() - self.last_failure_time) > self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                
                # Success - reset failure count
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                
                return result
                
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitBreakerState.OPEN
                
                raise e


class WeatherAPIError(Exception):
    """Base exception for weather API operations."""
    pass


class WeatherAPI:
    """
    Weather API client for Open-Meteo integration.
    
    Features:
    - Async HTTP requests with retry logic
    - Rate limiting to respect API limits
    - Circuit breaker for fault tolerance
    - Support for current, forecast, and historical data
    - Comprehensive error handling
    """
    
    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        """
        Initialize Weather API client.
        
        Args:
            config: Application configuration
            logger: Logger instance
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # API configuration
        self.base_url = config.weather_api_base_url
        self.timeout = config.weather_api_timeout
        self.latitude = config.weather_location_latitude
        self.longitude = config.weather_location_longitude
        self.timezone = config.weather_timezone
        
        # Rate limiting
        self.rate_limiter = RateLimiter(
            max_requests=config.weather_api_rate_limit_requests,
            time_window=60
        )
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.weather_circuit_breaker_failure_threshold,
            recovery_timeout=config.weather_circuit_breaker_recovery_timeout
        )
        
        # HTTP session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=config.weather_api_retry_attempts,
            backoff_factor=config.weather_api_retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.logger.info(f"WeatherAPI initialized for location ({self.latitude}, {self.longitude})")
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to weather API.
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Dict[str, Any]: API response data
            
        Raises:
            WeatherAPIError: If request fails
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            self.logger.debug(f"API request successful: {endpoint}")
            return data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise WeatherAPIError(f"API request failed: {e}")
        except ValueError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise WeatherAPIError(f"Invalid JSON response: {e}")
    
    async def _make_request_async(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make async HTTP request with rate limiting and circuit breaker.
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Dict[str, Any]: API response data
        """
        # Wait for rate limit slot
        await self.rate_limiter.wait_for_slot()
        
        # Execute with circuit breaker
        return await self.circuit_breaker.call(self._make_request, endpoint, params)
    
    def _parse_weather_data(self, data: Dict[str, Any], is_forecast: bool = True) -> List[WeatherData]:
        """
        Parse weather data from API response.
        
        Args:
            data: API response data
            is_forecast: Whether this is forecast data
            
        Returns:
            List[WeatherData]: Parsed weather data points
        """
        weather_points = []
        
        if 'hourly' not in data:
            return weather_points
        
        hourly = data['hourly']
        times = hourly.get('time', [])
        
        # Parse timezone
        tz = pytz.timezone(data.get('timezone', self.timezone))
        
        for i, time_str in enumerate(times):
            try:
                # Parse timestamp
                timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                timestamp = timestamp.astimezone(tz)
                
                # Extract weather parameters
                weather_point = WeatherData(
                    timestamp=timestamp,
                    temperature=self._safe_get_value(hourly, 'temperature_2m', i),
                    humidity=self._safe_get_value(hourly, 'relativehumidity_2m', i),
                    pressure=self._safe_get_value(hourly, 'surface_pressure', i),
                    wind_speed=self._safe_get_value(hourly, 'windspeed_10m', i),
                    wind_direction=self._safe_get_value(hourly, 'winddirection_10m', i),
                    precipitation=self._safe_get_value(hourly, 'precipitation', i),
                    cloud_cover=self._safe_get_value(hourly, 'cloudcover', i),
                    visibility=self._safe_get_value(hourly, 'visibility', i),
                    uv_index=self._safe_get_value(hourly, 'uv_index', i),
                    weather_code=self._safe_get_value(hourly, 'weathercode', i, int),
                    is_forecast=is_forecast
                )
                
                weather_points.append(weather_point)
                
            except (ValueError, KeyError) as e:
                self.logger.warning(f"Error parsing weather data point {i}: {e}")
                continue
        
        return weather_points
    
    def _safe_get_value(self, data: Dict[str, List], key: str, index: int, 
                       value_type: type = float) -> Optional[Union[float, int]]:
        """
        Safely extract value from API response data.
        
        Args:
            data: Data dictionary
            key: Key to extract
            index: List index
            value_type: Expected value type
            
        Returns:
            Optional[Union[float, int]]: Extracted value or None
        """
        try:
            values = data.get(key, [])
            if index < len(values) and values[index] is not None:
                return value_type(values[index])
        except (ValueError, TypeError, IndexError):
            pass
        return None
    
    async def fetch_current_weather(self) -> Optional[WeatherData]:
        """
        Fetch current weather data.
        
        Returns:
            Optional[WeatherData]: Current weather data or None if failed
        """
        params = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'current_weather': 'true',
            'timezone': self.timezone
        }
        
        try:
            data = await self._make_request_async('forecast', params)
            
            if 'current_weather' in data:
                current = data['current_weather']
                tz = pytz.timezone(data.get('timezone', self.timezone))
                
                timestamp = datetime.fromisoformat(current['time'].replace('Z', '+00:00'))
                timestamp = timestamp.astimezone(tz)
                
                return WeatherData(
                    timestamp=timestamp,
                    temperature=current.get('temperature', 0.0),
                    humidity=0.0,  # Not available in current weather
                    pressure=0.0,  # Not available in current weather
                    wind_speed=current.get('windspeed', 0.0),
                    wind_direction=current.get('winddirection', 0.0),
                    precipitation=0.0,  # Not available in current weather
                    cloud_cover=0.0,  # Not available in current weather
                    weather_code=current.get('weathercode'),
                    is_forecast=False
                )
            
            return None
            
        except WeatherAPIError as e:
            self.logger.error(f"Failed to fetch current weather: {e}")
            return None
    
    async def fetch_forecast_data(self, days: Optional[int] = None) -> Optional[ForecastData]:
        """
        Fetch weather forecast data.
        
        Args:
            days: Number of forecast days (defaults to config value)
            
        Returns:
            Optional[ForecastData]: Forecast data or None if failed
        """
        if days is None:
            days = self.config.weather_forecast_days
        
        params = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'hourly': [
                'temperature_2m',
                'relativehumidity_2m',
                'surface_pressure',
                'windspeed_10m',
                'winddirection_10m',
                'precipitation',
                'cloudcover',
                'visibility',
                'uv_index',
                'weathercode'
            ],
            'forecast_days': days,
            'timezone': self.timezone
        }
        
        try:
            data = await self._make_request_async('forecast', params)
            
            # Parse hourly forecasts
            hourly_forecasts = self._parse_weather_data(data, is_forecast=True)
            
            # Get current weather if available
            current_weather = await self.fetch_current_weather()
            
            forecast_data = ForecastData(
                location_latitude=data.get('latitude', self.latitude),
                location_longitude=data.get('longitude', self.longitude),
                timezone=data.get('timezone', self.timezone),
                current_weather=current_weather,
                hourly_forecasts=hourly_forecasts,
                retrieved_at=datetime.utcnow()
            )
            
            self.logger.info(f"Fetched forecast data: {len(hourly_forecasts)} hourly points")
            return forecast_data
            
        except WeatherAPIError as e:
            self.logger.error(f"Failed to fetch forecast data: {e}")
            return None
    
    async def fetch_historical_data(self, start_date: datetime, end_date: datetime) -> Optional[ForecastData]:
        """
        Fetch historical weather data.
        
        Args:
            start_date: Start date for historical data
            end_date: End date for historical data
            
        Returns:
            Optional[ForecastData]: Historical data or None if failed
        """
        params = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'hourly': [
                'temperature_2m',
                'relativehumidity_2m',
                'surface_pressure',
                'windspeed_10m',
                'winddirection_10m',
                'precipitation',
                'cloudcover',
                'visibility',
                'weathercode'
            ],
            'timezone': self.timezone
        }
        
        try:
            data = await self._make_request_async('historical-weather-api', params)
            
            # Parse historical data
            historical_data = self._parse_weather_data(data, is_forecast=False)
            
            forecast_data = ForecastData(
                location_latitude=data.get('latitude', self.latitude),
                location_longitude=data.get('longitude', self.longitude),
                timezone=data.get('timezone', self.timezone),
                hourly_forecasts=historical_data,
                retrieved_at=datetime.utcnow()
            )
            
            self.logger.info(f"Fetched historical data: {len(historical_data)} hourly points")
            return forecast_data
            
        except WeatherAPIError as e:
            self.logger.error(f"Failed to fetch historical data: {e}")
            return None
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """
        Get circuit breaker status information.
        
        Returns:
            Dict[str, Any]: Circuit breaker status
        """
        return {
            'state': self.circuit_breaker.state.value,
            'failure_count': self.circuit_breaker.failure_count,
            'last_failure_time': self.circuit_breaker.last_failure_time,
            'failure_threshold': self.circuit_breaker.failure_threshold,
            'recovery_timeout': self.circuit_breaker.recovery_timeout
        }
    
    def get_rate_limiter_status(self) -> Dict[str, Any]:
        """
        Get rate limiter status information.
        
        Returns:
            Dict[str, Any]: Rate limiter status
        """
        return {
            'max_requests': self.rate_limiter.max_requests,
            'time_window': self.rate_limiter.time_window,
            'current_requests': len(self.rate_limiter.requests),
            'requests_available': self.rate_limiter.max_requests - len(self.rate_limiter.requests)
        }
    
    async def health_check(self) -> bool:
        """
        Perform health check on weather API.
        
        Returns:
            bool: True if API is healthy
        """
        try:
            current_weather = await self.fetch_current_weather()
            return current_weather is not None
        except Exception as e:
            self.logger.error(f"Weather API health check failed: {e}")
            return False
    
    def close(self):
        """Close HTTP session and cleanup resources."""
        if self.session:
            self.session.close()
            self.logger.debug("Weather API session closed")


async def test_weather_api(config: Config):
    """
    Test function for Weather API.
    
    Args:
        config: Application configuration
    """
    import logging
    
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    api = WeatherAPI(config, logger)
    
    try:
        # Test current weather
        current = await api.fetch_current_weather()
        if current:
            print(f"Current weather: {current.temperature}°C")
        
        # Test forecast
        forecast = await api.fetch_forecast_data(days=3)
        if forecast:
            print(f"Forecast points: {len(forecast.hourly_forecasts)}")
        
        # Test historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=2)
        historical = await api.fetch_historical_data(start_date, end_date)
        if historical:
            print(f"Historical points: {len(historical.hourly_forecasts)}")
        
        # Status information
        print(f"Circuit breaker: {api.get_circuit_breaker_status()}")
        print(f"Rate limiter: {api.get_rate_limiter_status()}")
        
    finally:
        api.close()


if __name__ == "__main__":
    # Simple test when run directly
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.utils.config import Config
    
    config = Config()
    asyncio.run(test_weather_api(config))