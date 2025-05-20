"""Module for handling API call metrics and logging."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging
import uuid

logger = logging.getLogger(__name__)

@dataclass
class APICallMetrics:
    """Data class to store API call metrics."""
    timestamp: str
    api_type: str
    prompt_length: int
    response_length: int
    total_duration: float
    load_duration: Optional[float] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[float] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    run_id: Optional[str] = None  # Link to the run this call belongs to
    # New fields requested by user
    prompt_identifier: Optional[str] = None
    model_name: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

@dataclass
class RunMetrics:
    """Data class to store metrics for a complete run."""
    run_id: str
    start_time: str
    end_time: str
    total_urls: int
    successful_urls: int
    failed_urls: int
    total_api_calls: int
    successful_api_calls: int
    failed_api_calls: int
    total_duration: float
    avg_duration_per_url: float
    avg_duration_per_call: float
    calls_by_api: Dict[str, int]
    errors: List[str]
    urls_processed: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the RunMetrics instance."""
        return asdict(self)

class MetricsLogger:
    """Class to handle logging of API call metrics."""
    
    def __init__(self, metrics_dir: Optional[Path] = None):
        """
        Initialize the metrics logger.
        
        Args:
            metrics_dir: Directory to store metrics files. If None, uses 'metrics' in current directory.
        """
        self.metrics_dir = metrics_dir or Path("metrics")
        self.metrics_dir.mkdir(exist_ok=True)
        self.current_run_id = None
        self.current_run_start = None
        self.current_run_urls = []
        self.current_run_errors = []
        
    def start_run(self) -> str:
        """
        Start a new run and return its ID.
        
        Returns:
            str: The run ID
        """
        self.current_run_id = str(uuid.uuid4())
        self.current_run_start = time.time()
        self.current_run_urls = []
        self.current_run_errors = []
        return self.current_run_id
        
    def log_api_call(self, metrics: APICallMetrics, url: Optional[str] = None) -> None:
        """
        Log API call metrics to a JSON file.
        
        Args:
            metrics: APICallMetrics object containing the metrics to log
            url: Optional URL being processed
        """
        # Add run ID to metrics if we're in a run
        if self.current_run_id:
            metrics.run_id = self.current_run_id
            if url:
                self.current_run_urls.append(url)
            if not metrics.success:
                self.current_run_errors.append(metrics.error_message)
        
        # Create filename based on date
        date_str = datetime.now().strftime("%Y-%m-%d")
        metrics_file = self.metrics_dir / f"api_calls_{date_str}.jsonl"
        
        # Convert metrics to dict and add to file
        metrics_dict = asdict(metrics)
        with open(metrics_file, "a") as f:
            f.write(json.dumps(metrics_dict) + "\n")
            
        # Log to console
        logger.info(f"API Call Metrics: {json.dumps(metrics_dict, indent=2)}")
        
    def end_run(self) -> RunMetrics:
        """
        End the current run and save its metrics.
        
        Returns:
            RunMetrics: The metrics for the completed run
        """
        if not self.current_run_id:
            raise ValueError("No run in progress")
            
        end_time = time.time()
        run_duration = end_time - self.current_run_start
        
        # Get all API calls for this run
        run_calls = []
        date_str = datetime.now().strftime("%Y-%m-%d")
        metrics_file = self.metrics_dir / f"api_calls_{date_str}.jsonl"
        
        if metrics_file.exists():
            with open(metrics_file) as f:
                for line in f:
                    call = json.loads(line)
                    if call.get("run_id") == self.current_run_id:
                        run_calls.append(call)
        
        # Calculate run metrics
        total_calls = len(run_calls)
        successful_calls = sum(1 for call in run_calls if call["success"])
        failed_calls = total_calls - successful_calls
        total_duration = sum(call["total_duration"] for call in run_calls)
        
        # Count calls by API type
        calls_by_api = {}
        for call in run_calls:
            api_type = call["api_type"]
            calls_by_api[api_type] = calls_by_api.get(api_type, 0) + 1
        
        # Create run metrics
        run_metrics = RunMetrics(
            run_id=self.current_run_id,
            start_time=datetime.fromtimestamp(self.current_run_start).isoformat(),
            end_time=datetime.fromtimestamp(end_time).isoformat(),
            total_urls=len(set(self.current_run_urls)),
            successful_urls=len(set(self.current_run_urls)) - len(self.current_run_errors),
            failed_urls=len(self.current_run_errors),
            total_api_calls=total_calls,
            successful_api_calls=successful_calls,
            failed_api_calls=failed_calls,
            total_duration=run_duration,
            avg_duration_per_url=run_duration / len(set(self.current_run_urls)) if self.current_run_urls else 0,
            avg_duration_per_call=total_duration / total_calls if total_calls else 0,
            calls_by_api=calls_by_api,
            errors=self.current_run_errors,
            urls_processed=sorted(set(self.current_run_urls))
        )
        
        # Save run metrics
        run_metrics_file = self.metrics_dir / f"run_metrics_{date_str}.jsonl"
        with open(run_metrics_file, "a") as f:
            f.write(json.dumps(asdict(run_metrics)) + "\n")
            
        # Log run summary
        logger.info(f"Run Summary: {json.dumps(asdict(run_metrics), indent=2)}")
        
        # Reset run state
        self.current_run_id = None
        self.current_run_start = None
        self.current_run_urls = []
        self.current_run_errors = []
        
        return run_metrics
        
    def get_metrics_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get summary statistics for API calls over the specified number of days.
        
        Args:
            days: Number of days to include in summary
            
        Returns:
            Dictionary containing summary statistics
        """
        summary = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "avg_duration": 0,
            "total_duration": 0,
            "calls_by_api": {},
            "errors": []
        }
        
        # Get all metrics files for the specified period
        end_date = datetime.now()
        start_date = end_date - datetime.timedelta(days=days)
        
        for date in (start_date + datetime.timedelta(n) for n in range(days)):
            metrics_file = self.metrics_dir / f"api_calls_{date.strftime('%Y-%m-%d')}.jsonl"
            if not metrics_file.exists():
                continue
                
            with open(metrics_file) as f:
                for line in f:
                    metrics = json.loads(line)
                    summary["total_calls"] += 1
                    summary["total_duration"] += metrics["total_duration"]
                    
                    if metrics["success"]:
                        summary["successful_calls"] += 1
                    else:
                        summary["failed_calls"] += 1
                        summary["errors"].append(metrics["error_message"])
                        
                    # Track calls by API type
                    api_type = metrics["api_type"]
                    if api_type not in summary["calls_by_api"]:
                        summary["calls_by_api"][api_type] = 0
                    summary["calls_by_api"][api_type] += 1
        
        # Calculate averages
        if summary["total_calls"] > 0:
            summary["avg_duration"] = summary["total_duration"] / summary["total_calls"]
            
        return summary 