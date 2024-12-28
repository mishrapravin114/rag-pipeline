"use client";

import React from 'react';

interface VirtualDrugListProps {
  collectionId: number;
  collectionName: string;
  onDrugClick?: (drugName: string) => void;
  className?: string;
  height?: number;
  itemHeight?: number;
}

export function VirtualDrugListTest({
  collectionId,
  collectionName,
  className
}: VirtualDrugListProps) {
  return (
    <div className={className}>
      <div className="p-4 border rounded">
        <h3>Test Component for Collection: {collectionName}</h3>
        <p>Collection ID: {collectionId}</p>
        <p>This is a minimal test component to check if the basic structure works.</p>
      </div>
    </div>
  );
}