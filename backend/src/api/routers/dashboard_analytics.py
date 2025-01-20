"""Dashboard analytics endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging

from database.database import get_db, SearchHistory, SourceFiles, FDAExtractionResults
from api.routers.simple_auth import get_current_user
from api.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/activity/recent")
async def get_recent_activity(
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent user activity including searches, views, and chats."""
    try:
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_activities = []
        
        # Get recent activities from SearchHistory
        recent_searches = db.query(SearchHistory).filter(
            SearchHistory.search_timestamp >= seven_days_ago
        ).order_by(
            SearchHistory.search_timestamp.desc()
        ).limit(limit * 2).all()  # Get more to ensure we have enough
        
        for search in recent_searches:
            activity_type = 'search'
            
            # Determine activity type based on search_type
            if search.search_type:
                if 'chat' in search.search_type.lower():
                    activity_type = 'chat'
                elif 'view' in search.search_type.lower():
                    activity_type = 'view'
            
            # Extract entity name from filters if available
            entity_name = None
            if search.filters_applied and isinstance(search.filters_applied, dict):
                entity_name = search.filters_applied.get('entity_name')
            
            activity = {
                "id": str(search.id),
                "type": activity_type,
                "timestamp": search.search_timestamp.isoformat() if search.search_timestamp else datetime.now().isoformat()
            }
            
            if activity_type == 'search':
                activity["query"] = search.search_query
            elif activity_type == 'chat':
                activity["query"] = search.search_query
            else:  # view
                activity["entityName"] = entity_name or search.search_query
            
            recent_activities.append(activity)
        
        # If no activities, create synthetic ones
        if not recent_activities:
            entities = db.query(FDAExtractionResults).limit(5).all()
            activity_types = ['search', 'view', 'chat']
            
            for idx, entity in enumerate(entities):
                activity_type = activity_types[idx % 3]
                
                activity = {
                    "id": f"synthetic_{entity.id}",
                    "type": activity_type,
                    "timestamp": (datetime.now() - timedelta(hours=idx)).isoformat()
                }
                
                if activity_type == 'search':
                    activity["query"] = f"{entity.entity_name} side effects"
                elif activity_type == 'chat':
                    activity["query"] = f"What are the indications for {entity.entity_name}?"
                else:  # view
                    activity["entityName"] = entity.entity_name
                
                recent_activities.append(activity)
        
        return {
            "recent_activity": recent_activities[:limit]
        }
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_entities(
    period: str = "weekly",
    limit: int = 5,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get trending entities based on search activity."""
    try:
        # Calculate date range
        end_date = datetime.now()
        if period == "daily":
            start_date = end_date - timedelta(days=1)
        elif period == "monthly":
            start_date = end_date - timedelta(days=30)
        else:  # weekly
            start_date = end_date - timedelta(days=7)
        
        # Get trending entities from search history
        trending_query = db.query(
            SearchHistory.search_query,
            func.count(SearchHistory.id).label('search_count')
        ).filter(
            SearchHistory.search_timestamp >= start_date,
            SearchHistory.search_query.isnot(None),
            SearchHistory.search_query != ''
        ).group_by(
            SearchHistory.search_query
        ).order_by(
            func.count(SearchHistory.id).desc()
        ).limit(limit * 2).all()  # Get more to filter
        
        trending_entities = []
        entitie_counts = {}
        
        # Aggregate by entity name (normalize variations)
        for query, count in trending_query:
            # Try to extract entity name from query
            entity_name = query.strip().upper()
            
            # Normalize common patterns
            for pattern in [" SIDE EFFECTS", " INDICATIONS", " DOSAGE", " INTERACTIONS"]:
                if pattern in entity_name:
                    entity_name = entity_name.split(pattern)[0].strip()
            
            if entity_name in entitie_counts:
                entitie_counts[entity_name] += count
            else:
                entitie_counts[entity_name] = count
        
        # Convert to list format
        for entity_name, count in sorted(entitie_counts.items(), key=lambda x: x[1], reverse=True)[:limit]:
            trending_entities.append({
                "entity_name": entity_name,
                "search_count": count
            })
        
        # If no trending data, use fallback
        if not trending_entities:
            entities = db.query(FDAExtractionResults).limit(limit).all()
            for idx, entity in enumerate(entities):
                trending_entities.append({
                    "entity_name": entity.entity_name,
                    "search_count": 100 - (idx * 20)
                })
        
        return {
            "trending_entities": trending_entities,
            "period": period
        }
        
    except Exception as e:
        logger.error(f"Error getting trending entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/enhanced")
async def get_enhanced_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get enhanced dashboard statistics with trending and activity data."""
    try:
        # Get basic stats
        total_entities = db.query(FDAExtractionResults).count()
        total_manufacturers = db.query(func.count(distinct(FDAExtractionResults.manufacturer))).scalar() or 0
        
        # Get recent approvals
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_approvals = db.query(SourceFiles).filter(
            SourceFiles.created_at >= thirty_days_ago
        ).count()
        
        # Get total searches
        total_searches = db.query(SearchHistory).count()
        
        # Get trending entities
        trending_response = await get_trending_entities(limit=5, current_user=current_user, db=db)
        trending_entities = trending_response["trending_entities"]
        
        # Get recent activity
        activity_response = await get_recent_activity(limit=10, current_user=current_user, db=db)
        recent_activity = activity_response["recent_activity"]
        
        return {
            "total_entities": total_entities,
            "total_manufacturers": total_manufacturers,
            "recent_approvals": recent_approvals,
            "total_searches": total_searches,
            "additional_stats": {
                "trending_entities": trending_entities,
                "recent_activity": recent_activity
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting enhanced dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))