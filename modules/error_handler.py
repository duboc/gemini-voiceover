import logging
import json
import re
from typing import Optional, Any

logger = logging.getLogger(__name__)

class GeminiErrorHandler:
    """Helper class to parse and handle Gemini API errors"""

    @staticmethod
    def extract_quota_info(error_str: str) -> Optional[str]:
        """Extract quota metric from error string"""
        try:
            # Look for "Quota exceeded for metric: X"
            # Example: "Quota exceeded for metric: generativelanguage.googleapis.com/generate_requests_per_model_per_day"
            match = re.search(r"Quota exceeded for metric: ([\w\./_]+)", error_str)
            if match:
                return match.group(1)
            
            # Look in parsed JSON if the error string contains it
            # The error string might contain a JSON-like structure: "{'error': ...}"
            # We try to find the inner JSON structure
            json_match = re.search(r"(\{.*'error':.*\})", error_str, re.DOTALL)
            if json_match:
                try:
                    # Replace single quotes with double quotes for valid JSON if needed (simple heuristic)
                    # This is risky but the error repr often uses single quotes
                    json_str = json_match.group(1).replace("'", '"').replace("None", "null").replace("True", "true").replace("False", "false")
                    error_data = json.loads(json_str)
                    
                    if 'error' in error_data:
                        details = error_data['error'].get('details', [])
                        for detail in details:
                            if 'violations' in detail:
                                for violation in detail['violations']:
                                    if 'quotaMetric' in violation:
                                        return violation['quotaMetric']
                except Exception:
                    pass

            return None
        except Exception as e:
            logger.warning(f"Failed to parse quota info from error: {e}")
            return None

    @staticmethod
    def handle_gemini_error(e: Exception, context: str) -> None:
        """
        Parse Gemini API error and raise a more informative exception
        
        Args:
            e: The original exception
            context: Description of what was happening (e.g., "Transcription", "Translation")
            
        Raises:
            Exception: A more informative exception
        """
        error_str = str(e)
        
        # Check for Quota Exceeded / Resource Exhausted
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            metric = GeminiErrorHandler.extract_quota_info(error_str)
            
            metric_msg = f" for metric '{metric}'" if metric else ""
            
            # User-friendly message
            friendly_msg = (
                f"Gemini API Quota Exceeded during {context}{metric_msg}. "
                "You have reached the daily limit for this model. "
                "Please try again later or verify your billing details."
            )
            
            logger.error(f"Gemini Quota Error: {friendly_msg}")
            raise Exception(friendly_msg) from e
            
        # Check for other common errors (like 500s, 400s)
        if "500" in error_str or "INTERNAL" in error_str:
            raise Exception(f"Gemini Internal Server Error during {context}. Please try again later.") from e
            
        if "400" in error_str or "INVALID_ARGUMENT" in error_str:
            raise Exception(f"Invalid Request to Gemini API during {context}. Please check input data.") from e

        # Re-raise with context if it's not a specific handled error
        raise Exception(f"{context} failed: {error_str}") from e
