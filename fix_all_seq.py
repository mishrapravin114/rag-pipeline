#!/usr/bin/env python3
import sys
empty = ['22dcb5d', '6592f05', 'cd239f7', 'ad0be59', 'd6295bf', '0fa23a2', '2144f49', 'd277ce9', '01bf1ea', '5a544a4', 'af2e7e1', '50c6420', '1e9d2c8', '6114425', 'a402047', '3308f17', '43417aa', '17e02cd', '453299a', '93bc2b0', 'b12a6b2', '8b7d8b8', '8b54141', 'e700356', 'a0dd7cf', '66ac0cf', '76c3b70', 'd0376ff', '6839572', 'd8a224a', '4b04ed9', '818b021', '2517094', '4453131', '257786c', '7faac83', '4874e5e', '588cf16', '237acc4', 'c9dc673', 'd38409c', 'c8450ee', '019f5c4', '61ef06e', '4d45f33', 'bb07a7e', '894cf3d', '15b12e3', '4cbab79', '4edb9c4', '0121c77', '603f2ae', '3e586d0', 'bb63191', 'f256c18', '32e240f', '2052611', '957a721', '10a1b32', 'f5cb14c', 'ad22e4c', '25e7831']
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
