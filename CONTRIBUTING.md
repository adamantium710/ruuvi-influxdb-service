# Contributing to Ruuvi Sensor Service

Thank you for your interest in contributing to the Ruuvi Sensor Service! This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## 🤝 Code of Conduct

This project adheres to a code of conduct that we expect all contributors to follow:

- **Be respectful**: Treat all community members with respect and kindness
- **Be inclusive**: Welcome newcomers and help them get started
- **Be collaborative**: Work together to improve the project
- **Be constructive**: Provide helpful feedback and suggestions
- **Be patient**: Remember that everyone has different skill levels and backgrounds

## 🚀 Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.8+** installed
- **Git** for version control
- **Linux environment** (Ubuntu, Debian, or similar)
- **Bluetooth adapter** for testing BLE functionality
- **InfluxDB** for database testing (can be containerized)

### Development Setup

1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/ruuvi-sensor-service.git
   cd ruuvi-sensor-service
   ```

2. **Create a Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If available
   ```

4. **Set Up Environment**:
   ```bash
   cp .env.sample .env
   # Edit .env with your development settings
   ```

5. **Run Tests**:
   ```bash
   pytest
   ```

## 🛠️ Contributing Guidelines

### Types of Contributions

We welcome various types of contributions:

- **Bug Reports**: Help us identify and fix issues
- **Feature Requests**: Suggest new functionality
- **Code Contributions**: Implement features or fix bugs
- **Documentation**: Improve or add documentation
- **Testing**: Add or improve test coverage
- **Examples**: Provide usage examples or tutorials

### Before You Start

1. **Check Existing Issues**: Look for existing issues or discussions
2. **Create an Issue**: For significant changes, create an issue first
3. **Discuss Your Approach**: Get feedback on your proposed solution
4. **Follow Standards**: Adhere to our coding and documentation standards

## 🔄 Pull Request Process

### 1. Prepare Your Changes

- Create a feature branch: `git checkout -b feature/your-feature-name`
- Make your changes following our coding standards
- Add or update tests as needed
- Update documentation if required
- Ensure all tests pass

### 2. Commit Your Changes

Use clear, descriptive commit messages:

```bash
git commit -m "feat: add sensor calibration functionality

- Implement calibration algorithm for temperature sensors
- Add CLI commands for calibration workflow
- Include validation for calibration parameters
- Update documentation with calibration examples

Fixes #123"
```

### 3. Submit Pull Request

- Push your branch: `git push origin feature/your-feature-name`
- Create a pull request with:
  - Clear title and description
  - Reference to related issues
  - List of changes made
  - Testing information

### 4. Review Process

- Maintainers will review your PR
- Address any feedback or requested changes
- Once approved, your PR will be merged

## 📝 Coding Standards

### Python Style Guide

We follow PEP 8 with some project-specific conventions:

- **Line Length**: Maximum 88 characters (Black formatter default)
- **Imports**: Use absolute imports, group by standard/third-party/local
- **Type Hints**: Use type hints for all public functions and methods
- **Docstrings**: Use Google-style docstrings

### Code Formatting

We use automated formatting tools:

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .

# Type checking
mypy src/
```

### Example Code Style

```python
"""Module for sensor data processing."""

from typing import Dict, List, Optional
import asyncio
from datetime import datetime

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SensorDataProcessor:
    """Processes sensor data with validation and transformation.
    
    This class handles the processing of raw sensor data from Ruuvi sensors,
    including validation, transformation, and preparation for storage.
    
    Attributes:
        config: Configuration object for processing parameters
        validators: List of validation functions to apply
    """
    
    def __init__(self, config: Dict[str, any]) -> None:
        """Initialize the sensor data processor.
        
        Args:
            config: Configuration dictionary containing processing parameters
            
        Raises:
            ValueError: If configuration is invalid
        """
        self.config = config
        self.validators = self._load_validators()
    
    async def process_data(
        self, 
        sensor_data: Dict[str, any], 
        sensor_id: str
    ) -> Optional[Dict[str, any]]:
        """Process raw sensor data.
        
        Args:
            sensor_data: Raw sensor data dictionary
            sensor_id: Unique identifier for the sensor
            
        Returns:
            Processed sensor data or None if validation fails
            
        Raises:
            ProcessingError: If data processing fails
        """
        try:
            # Validate data
            if not self._validate_data(sensor_data):
                logger.warning(f"Invalid data from sensor {sensor_id}")
                return None
            
            # Transform data
            processed_data = self._transform_data(sensor_data)
            
            logger.debug(f"Processed data for sensor {sensor_id}")
            return processed_data
            
        except Exception as e:
            logger.error(f"Processing failed for sensor {sensor_id}: {e}")
            raise ProcessingError(f"Failed to process data: {e}") from e
```

## 🧪 Testing

### Test Structure

```
tests/
├── unit/                 # Unit tests
├── integration/          # Integration tests
├── fixtures/            # Test data and fixtures
├── mocks/              # Mock objects
└── utils/              # Test utilities
```

### Writing Tests

- Write tests for all new functionality
- Use descriptive test names
- Include both positive and negative test cases
- Mock external dependencies
- Test error conditions

### Example Test

```python
"""Tests for sensor data processing."""

import pytest
from unittest.mock import Mock, patch

from src.processing.sensor_data import SensorDataProcessor
from tests.fixtures.sensor_data import VALID_SENSOR_DATA, INVALID_SENSOR_DATA


class TestSensorDataProcessor:
    """Test cases for SensorDataProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create a processor instance for testing."""
        config = {"validation_enabled": True, "timeout": 30}
        return SensorDataProcessor(config)
    
    @pytest.mark.asyncio
    async def test_process_valid_data(self, processor):
        """Test processing of valid sensor data."""
        result = await processor.process_data(VALID_SENSOR_DATA, "test-sensor")
        
        assert result is not None
        assert "temperature" in result
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_process_invalid_data(self, processor):
        """Test processing of invalid sensor data."""
        result = await processor.process_data(INVALID_SENSOR_DATA, "test-sensor")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_processing_error_handling(self, processor):
        """Test error handling during processing."""
        with patch.object(processor, '_transform_data', side_effect=Exception("Test error")):
            with pytest.raises(ProcessingError):
                await processor.process_data(VALID_SENSOR_DATA, "test-sensor")
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_sensor_data.py

# Run tests with specific marker
pytest -m integration
```

## 📚 Documentation

### Documentation Standards

- Use clear, concise language
- Include code examples where appropriate
- Keep documentation up-to-date with code changes
- Use proper Markdown formatting

### Types of Documentation

1. **Code Documentation**: Docstrings and inline comments
2. **API Documentation**: Function and class documentation
3. **User Documentation**: README, guides, tutorials
4. **Developer Documentation**: Contributing guides, architecture docs

### Documentation Structure

```
docs/
├── API_REFERENCE.md          # Complete API documentation
├── DEPLOYMENT.md             # Deployment guide
├── TROUBLESHOOTING.md        # Troubleshooting guide
├── BLUETOOTH_TROUBLESHOOTING.md  # Bluetooth-specific issues
├── SECURE_INSTALLATION.md   # Security guidelines
└── SECURITY_REMEDIATION.md  # Security best practices
```

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Environment Information**:
   - Operating system and version
   - Python version
   - Package versions
   - Hardware information (Bluetooth adapter, etc.)

2. **Steps to Reproduce**:
   - Clear, step-by-step instructions
   - Minimal code example if applicable
   - Configuration details (sanitized)

3. **Expected vs Actual Behavior**:
   - What you expected to happen
   - What actually happened
   - Error messages or logs

4. **Additional Context**:
   - Screenshots if relevant
   - Related issues or discussions
   - Potential solutions you've tried

## 💡 Feature Requests

When requesting features:

1. **Describe the Problem**: What problem does this solve?
2. **Proposed Solution**: How should it work?
3. **Alternatives**: What alternatives have you considered?
4. **Use Cases**: Provide specific use cases
5. **Implementation Ideas**: Any thoughts on implementation?

## 🏷️ Issue Labels

We use labels to categorize issues:

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Improvements or additions to documentation
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed
- `question`: Further information is requested
- `wontfix`: This will not be worked on

## 🎯 Development Priorities

Current development priorities:

1. **Stability**: Bug fixes and reliability improvements
2. **Performance**: Optimization and resource usage
3. **Documentation**: Comprehensive guides and examples
4. **Testing**: Improved test coverage and quality
5. **Features**: New functionality based on user feedback

## 📞 Getting Help

If you need help:

1. **Check Documentation**: Review existing documentation
2. **Search Issues**: Look for similar questions or problems
3. **Ask Questions**: Create an issue with the `question` label
4. **Join Discussions**: Participate in project discussions

## 🙏 Recognition

Contributors will be recognized in:

- Project README
- Release notes
- Contributor list
- Special mentions for significant contributions

Thank you for contributing to the Ruuvi Sensor Service! Your contributions help make this project better for everyone.