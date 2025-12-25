#!/usr/bin/env python3
import sys
with open(sys.argv[1], 'r') as f:
    lines = f.readlines()
with open(sys.argv[1], 'w') as f:
    for line in lines:
        if '3308f17' in line and line.strip().startswith('pick'):
            f.write('edit ' + ' '.join(line.split()[1:]) + '\n')
        else:
            f.write(line)
