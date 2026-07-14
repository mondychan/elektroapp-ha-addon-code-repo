import json, re
with open('package-lock.json', encoding='utf-8') as f:
    lock = json.load(f)
pkgs = lock.get('packages', {})
for key in sorted(pkgs):
    k = key.lower()
    if '@testing-library/react' in k and '/node_modules/' in key:
        print('TESTING:', key, '→', pkgs[key].get('version'))
    if key == 'node_modules/react':
        print('REACT:', pkgs[key].get('version'))
    if key == 'node_modules/react-dom':
        print('REACT-DOM:', pkgs[key].get('version'))
