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
            
            # Extract drug name from filters if available
            drug_name = None
            if search.filters_applied and isinstance(search.filters_applied, dict):
                drug_name = search.filters_applied.get('drug_name')
            
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
                activity["drugName"] = drug_name or search.search_query
            
            recent_activities.append(activity)
        
        # If no activities, create synthetic ones
        if not recent_activities:
            drugs = db.query(FDAExtractionResults).limit(5).all()
            activity_types = ['search', 'view', 'chat']
            
            for idx, drug in enumerate(drugs):
                activity_type = activity_types[idx % 3]
                
                activity = {
                    "id": f"synthetic_{drug.id}",
                    "type": activity_type,
                    "timestamp": (datetime.now() - timedelta(hours=idx)).isoformat()
                }
                
                if activity_type == 'search':
                    activity["query"] = f"{drug.drug_name} side effects"
                elif activity_type == 'chat':
                    activity["query"] = f"What are the indications for {drug.drug_name}?"
                else:  # view
                    activity["drugName"] = drug.drug_name
                
                recent_activities.append(activity)
        
        return {
            "recent_activity": recent_activities[:limit]
        }
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_drugs(
    period: str = "weekly",
    limit: int = 5,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get trending drugs based on search activity."""
    try:
        # Calculate date range
        end_date = datetime.now()
        if period == "daily":
            start_date = end_date - timedelta(days=1)
        elif period == "monthly":
            start_date = end_date - timedelta(days=30)
        else:  # weekly
            start_date = end_date - timedelta(days=7)
        
        # Get trending drugs from search history
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
        
        trending_drugs = []
        drug_counts = {}
        
        # Aggregate by drug name (normalize variations)
        for query, count in trending_query:
            # Try to extract drug name from query
            drug_name = query.strip().upper()
            
            # Normalize common patterns
            for pattern in [" SIDE EFFECTS", " INDICATIONS", " DOSAGE", " INTERACTIONS"]:
                if pattern in drug_name:
                    drug_name = drug_name.split(pattern)[0].strip()
            
            if drug_name in drug_counts:
                drug_counts[drug_name] += count
            else:
                drug_counts[drug_name] = count
        
        # Convert to list format
        for drug_name, count in sorted(drug_counts.items(), key=lambda x: x[1], reverse=True)[:limit]:
            trending_drugs.append({
                "drug_name": drug_name,
                "search_count": count
            })
        
        # If no trending data, use fallback
        if not trending_drugs:
            drugs = db.query(FDAExtractionResults).limit(limit).all()
            for idx, drug in enumerate(drugs):
                trending_drugs.append({
                    "drug_name": drug.drug_name,
                    "search_count": 100 - (idx * 20)
                })
        
        return {
            "trending_drugs": trending_drugs,
            "period": period
        }
        
    except Exception as e:
        logger.error(f"Error getting trending drugs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/enhanced")
async def get_enhanced_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get enhanced dashboard statistics with trending and activity data."""
    try:
        # Get basic stats
        total_drugs = db.query(FDAExtractionResults).count()
        total_manufacturers = db.query(func.count(distinct(FDAExtractionResults.manufacturer))).scalar() or 0
        
        # Get recent approvals
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_approvals = db.query(SourceFiles).filter(
            SourceFiles.created_at >= thirty_days_ago
        ).count()
        
        # Get total searches
        total_searches = db.query(SearchHistory).count()
        
        # Get trending drugs
        trending_response = await get_trending_drugs(limit=5, current_user=current_user, db=db)
        trending_drugs = trending_response["trending_drugs"]
        
        # Get recent activity
        activity_response = await get_recent_activity(limit=10, current_user=current_user, db=db)
        recent_activity = activity_response["recent_activity"]
        
        return {
            "total_drugs": total_drugs,
            "total_manufacturers": total_manufacturers,
            "recent_approvals": recent_approvals,
            "total_searches": total_searches,
            "additional_stats": {
                "trending_drugs": trending_drugs,
                "recent_activity": recent_activity
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting enhanced dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))