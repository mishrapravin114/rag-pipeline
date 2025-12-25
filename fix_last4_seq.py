#!/usr/bin/env python3
import sys
empty = ['8d2d597', 'fa969fe', '86eaa3d', 'e148e81']
with open(sys.argv[1], 'r') as f:
    lines = f.readlines()
with open(sys.argv[1], 'w') as f:
    for line in lines:
        if line.strip().startswith('pick'):
            parts = line.split()
            if len(parts) > 1 and parts[1] in empty:
                f.write('edit ' + ' '.join(parts[1:]) + '\n')
            else:
                f.write(line)
        else:
            f.write(line)
