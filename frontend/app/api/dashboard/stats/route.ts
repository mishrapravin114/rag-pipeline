import { NextResponse } from 'next/server';

export async function GET() {
  try {
    // Mock data for now - in production this would connect to the backend
    const stats = {
      totalDrugs: 4,
      totalManufacturers: 3,
      recentApprovals: 1,
      totalSections: 24,
    };

    return NextResponse.json(stats);
  } catch (error) {
    console.error('Error fetching dashboard stats:', error);
    return NextResponse.json(
      { error: 'Failed to fetch dashboard stats' },
      { status: 500 }
    );
  }
} 