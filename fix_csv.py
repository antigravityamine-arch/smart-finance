import os
with open('raw_data.csv', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('raw_data_fixed.csv', 'w', encoding='utf-8') as out:
    for line in lines:
        line = line.rstrip('\n')
        if line.endswith('"'):
            line = line[:-1]
        if line.startswith('"'):
            line = line[1:]
        out.write(line + '\n')

os.replace('raw_data_fixed.csv', 'raw_data.csv')
print("Fixed trailing and leading quotes in raw_data.csv")
