import os
import json
from scraper import HOME


path_not_founds = []
suggestion_not_found = []
data_path = os.path.join(HOME, 'data')
for path in os.listdir(data_path):
    pharmacy_path = os.path.join(data_path, path, 'overview', path + ".json")
    if os.path.exists(pharmacy_path):
        with open(pharmacy_path, 'r', encoding='utf-8') as fn:
            data_json = json.load(fn)
        if not data_json.get('suggestions'):
            suggestion_not_found.append(path)
    else:
        path_not_founds.append(path)

print('path_not_founds', path_not_founds)
print('suggestion_not_found', suggestion_not_found)
