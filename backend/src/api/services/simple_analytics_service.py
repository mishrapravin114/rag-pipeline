"""Simple analytics service for search history and trending analysis."""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from datetime import datetime, timedelta
import logging

# Import database models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

logger = logging.getLogger(__name__)

class SimpleAnalyticsService:
    
    @staticmethod
    def get_user_search_history(username: str, limit: int = 10, db: Session = None) -> List[Dict]:
        """Get recent search history for user."""
        try:
            from database.database import SearchHistory
            
            searches = db.query(SearchHistory).filter(
                SearchHistory.username == username
            ).order_by(SearchHistory.search_timestamp.desc()).limit(limit).all()
            
            return [
                {
                    "id": search.id,
                    "query": search.search_query,
                    "search_type": search.search_type,
                    "results_count": search.results_count,
                    "timestamp": search.search_timestamp.isoformat(),
                    "execution_time_ms": search.execution_time_ms
                }
                for search in searches
            ]
        except Exception as e:
            logger.error(f"Error getting user search history: {e}")
            return []
    
    @staticmethod
    def get_trending_searches(period: str = "weekly", limit: int = 10, db: Session = None) -> List[Dict]:
        """Get trending searches (simplified)."""
        try:
            from database.database import SearchHistory
            
            # Calculate period dates
            end_date = datetime.utcnow()
            if period == "daily":
                start_date = end_date - timedelta(days=1)
            elif period == "weekly":
                start_date = end_date - timedelta(weeks=1)
            else:  # monthly
                start_date = end_date - timedelta(days=30)
            
            # Query trending searches (simple aggregation)
            trending = db.query(
                SearchHistory.search_query,
                func.count(SearchHistory.id).label('frequency')
            ).filter(
                SearchHistory.search_timestamp >= start_date
            ).group_by(SearchHistory.search_query).order_by(
                func.count(SearchHistory.id).desc()
            ).limit(limit).all()
            
            return [
                {
                    "search_term": item.search_query,
                    "frequency": item.frequency,
                    "period": period
                }
                for item in trending
            ]
        except Exception as e:
            logger.error(f"Error getting trending searches: {e}")
            return []
    
    @staticmethod
    def get_search_statistics(username: str = None, db: Session = None) -> Dict[str, Any]:
        """Get search statistics for dashboard."""
        try:
            from database.database import SearchHistory
            
            # Base query
            query = db.query(SearchHistory)
            if username:
                query = query.filter(SearchHistory.username == username)
            
            # Get basic stats
            total_searches = query.count()
            
            # Get searches by type
            search_types = query.with_entities(
                SearchHistory.search_type,
                func.count(SearchHistory.id).label('count')
            ).group_by(SearchHistory.search_type).all()
            
            # Get recent activity (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_searches = query.filter(
                SearchHistory.search_timestamp >= week_ago
            ).count()
            
            return {
                "total_searches": total_searches,
                "recent_searches_7days": recent_searches,
                "search_types": [
                    {"type": st.search_type, "count": st.count}
                    for st in search_types
                ],
                "period": "all_time" if not username else f"user_{username}"
            }
        except Exception as e:
            logger.error(f"Error getting search statistics: {e}")
            return {
                "total_searches": 0,
                "recent_searches_7days": 0,
                "search_types": [],
                "period": "error"
            }
    
    @staticmethod
    def update_trending_data(db: Session = None):
        """Background task to update trending search data."""
        try:
            from database.database import TrendingSearches
            
            # Calculate trending for different periods
            periods = ["daily", "weekly", "monthly"]
            
            for period in periods:
                trending_data = SimpleAnalyticsService.get_trending_searches(
                    period=period, limit=50, db=db
                )
                
                # Save to TrendingSearches table
                for item in trending_data:
                    existing = db.query(TrendingSearches).filter(
                        TrendingSearches.search_term == item["search_term"],
                        TrendingSearches.time_period == period
                    ).first()
                    
                    if existing:
                        existing.frequency = item["frequency"]
                        existing.last_updated = datetime.utcnow()
                    else:
                        trending_record = TrendingSearches(
                            search_term=item["search_term"],
                            frequency=item["frequency"],
                            time_period=period,
                            last_updated=datetime.utcnow()
                        )
                        db.add(trending_record)
                
                db.commit()
                logger.info(f"Updated trending data for {period}")
                
        except Exception as e:
            logger.error(f"Error updating trending data: {e}")
            db.rollback()
    
    @staticmethod
    def get_dashboard_data(username: str, db: Session = None) -> Dict[str, Any]:
        """Get comprehensive dashboard data for user."""
        try:
            return {
                "user_stats": SimpleAnalyticsService.get_search_statistics(username, db),
                "recent_searches": SimpleAnalyticsService.get_user_search_history(username, 5, db),
                "trending_weekly": SimpleAnalyticsService.get_trending_searches("weekly", 5, db),
                "trending_daily": SimpleAnalyticsService.get_trending_searches("daily", 3, db)
            }
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {
                "user_stats": {"total_searches": 0},
                "recent_searches": [],
                "trending_weekly": [],
                "trending_daily": []
            } 