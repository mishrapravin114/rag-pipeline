// Minor update
import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('q') || '';
    const therapeuticArea = searchParams.get('therapeutic_area');

    // Mock search results - in production this would connect to the backend
    const allResults = [
      {
        id: '1',
        entity_name: 'OCREVUS',
        manufacturer: 'Genentech, Inc.',
        approval_date: '2017-03-28',
        indication: 'Treatment of relapsing forms of multiple sclerosis',
        regulatory_classification: 'BLA',
      },
      {
        id: '2',
        entity_name: 'ANKTIVA',
        manufacturer: 'ImmunityBio, Inc.',
        approval_date: '2024-04-22',
        indication: 'Treatment of BCG-unresponsive non-muscle invasive bladder cancer',
        regulatory_classification: 'BLA',
      },
      {
        id: '3',
        entity_name: 'ALECENSA',
        manufacturer: 'Genentech, Inc.',
        approval_date: '2015-12-11',
        indication: 'Treatment of ALK-positive metastatic non-small cell lung cancer',
        regulatory_classification: 'NDA',
      },
      {
        id: '4',
        entity_name: 'AUGTYRO',
        manufacturer: 'Roche Products Limited',
        approval_date: '2023-11-15',
        indication: 'Treatment of RET fusion-positive solid tumors',
        regulatory_classification: 'NDA',
      },
    ];

    // Simple filtering based on query
    let results = allResults;
    if (query) {
      results = allResults.filter(
        (entity) =>
          entity.entity_name.toLowerCase().includes(query.toLowerCase()) ||
          entity.manufacturer.toLowerCase().includes(query.toLowerCase()) ||
          entity.indication.toLowerCase().includes(query.toLowerCase())
      );
    }

    // Filter by therapeutic area if provided
    if (therapeuticArea && therapeuticArea !== '') {
      // This is a simple mock - in reality you'd have proper therapeutic area mapping
      results = results.filter((entity) =>
        entity.indication.toLowerCase().includes(therapeuticArea.toLowerCase())
      );
    }

    return NextResponse.json({
      results,
      total: results.length,
      query,
      therapeuticArea,
    });
  } catch (error) {
    console.error('Error performing search:', error);
    return NextResponse.json(
      { error: 'Failed to perform search' },
      { status: 500 }
    );
  }
} 