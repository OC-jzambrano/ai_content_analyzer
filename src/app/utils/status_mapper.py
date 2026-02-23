"""
Status mapper utilities for campaign reporting.
"""

from typing import Dict, List
from app.schemas.moderation import CategoryAggregate


def map_categories_to_status(categories: List[CategoryAggregate]) -> Dict[str, str]:
    """
    Map category aggregates to their status values.
    
    Args:
        categories: List of CategoryAggregate objects
    
    Returns:
        Dict mapping category name to status string
    """
    return {cat.category: cat.status for cat in categories}


def get_critical_categories(categories: List[CategoryAggregate]) -> List[CategoryAggregate]:
    """
    Filter for Unsafe categories that require immediate action.
    
    Args:
        categories: List of CategoryAggregate objects
    
    Returns:
        List of unsafe categories
    """
    return [cat for cat in categories if cat.status == "Unsafe"]


def get_warning_categories(categories: List[CategoryAggregate]) -> List[CategoryAggregate]:
    """
    Filter for Warning categories that need review.
    
    Args:
        categories: List of CategoryAggregate objects
    
    Returns:
        List of warning categories
    """
    return [cat for cat in categories if cat.status == "Warning"]