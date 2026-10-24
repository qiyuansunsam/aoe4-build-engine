import json, sys
from pathlib import Path

def convert(value):
    if not isinstance(value, list):
        return value
    grouped = {}
    for entry in value:
        grouped.setdefault(entry['key'], []).append(convert(entry['value']))
    return {key: values[0] if len(values) == 1 else values for key, values in grouped.items()}

def load(path):
    return convert(json.loads(Path(path).read_text(encoding='utf-8-sig'))['data'])['default']

if __name__ == '__main__':
    data = load(sys.argv[1])
    print(json.dumps({key: data[key] for key in sys.argv[2:]} if len(sys.argv)>2 else data, indent=2))
