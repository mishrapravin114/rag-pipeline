"""Script to register dashboard analytics router."""

# This file would need to be integrated into main.py
# For now, we'll document how to add it

print("""
To register the dashboard analytics router, add these lines to main.py:

# Import dashboard analytics router
from api.routers.dashboard_analytics import router as dashboard_analytics_router
app.include_router(dashboard_analytics_router)

Add this after the other router registrations.
""")