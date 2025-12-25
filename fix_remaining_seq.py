#!/usr/bin/env python3
import sys
empty = ['c5cc1c7', '9d02312', '8f5febb', 'de714a2', '0d050a9', 'f4f9ccc', 'd7ac8d3', '41dfc65', 'a6ebcea', 'e4f4c9c', 'feb161a', '881eb83', 'f3a96cf', '68e06c7', '6109939']
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
