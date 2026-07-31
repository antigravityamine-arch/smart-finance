import os
with open('raw_data.csv', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('""', '"')

with open('raw_data_fixed.csv', 'w', encoding='utf-8') as out:
    out.write(content)

os.replace('raw_data_fixed.csv', 'raw_data.csv')
print("Fixed double quotes in raw_data.csv")
