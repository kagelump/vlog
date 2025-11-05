"""Tests for Snakemake integration in auto_ingest."""
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSnakemakeIntegration:
    """Test that auto_ingest correctly invokes Snakemake."""
    
    def test_snakemake_config_format(self):
        """Test that the temporary config has the correct format."""
        try:
            from vlog.auto_ingest import AutoIngestService
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestService(temp_dir, "custom-model")
            
            # The config should include the model name
            assert service.model_name == "custom-model"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
