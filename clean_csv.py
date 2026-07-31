import os
import sys

def clean_csv():
    file_path = 'c:/Users/Administrator/Desktop/Nouveau dossier/raw_data.csv'
    temp_path = 'c:/Users/Administrator/Desktop/Nouveau dossier/raw_data_temp.csv'
    
    if not os.path.exists(file_path):
        print("raw_data.csv not found!")
        return

    print("Cleaning raw_data.csv...")
    fixed_count = 0
    with open(file_path, 'r', encoding='utf-8') as f_in, open(temp_path, 'w', encoding='utf-8') as f_out:
        for line in f_in:
            if line.startswith('"') and len(line) > 1 and line[1].isdigit():
                f_out.write(line[1:])
                fixed_count += 1
            else:
                f_out.write(line)
    
    os.replace(temp_path, file_path)
    print(f"Done! Fixed {fixed_count} malformed rows.")

if __name__ == "__main__":
    clean_csv()
