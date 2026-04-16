#!/usr/bin/env python3
import yaml
import sys

def get_nested(data, path):
    parts = [p for p in path.strip('.').split('.') if p]
    cur = data
    for p in parts:
        if not isinstance(cur, dict):
            return None, False
        cur = cur.get(p)
        if cur is None:
            return None, False
    return cur, True

def main():
    mode = sys.argv[1]
    config_path = sys.argv[2]
    query = sys.argv[3] if len(sys.argv) > 3 else None
    
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    
    if mode == "get":
        value, found = get_nested(data, query)
        if not found:
            sys.exit(1)
        if isinstance(value, (dict, list)):
            sys.exit(1)
        print(value)
    
    elif mode == "list":
        value, found = get_nested(data, query)
        if not found or not isinstance(value, list):
            sys.exit(1)
        print(','.join(str(v) for v in value if v is not None))
    
    elif mode == "keys":
        value, found = get_nested(data, query)
        if not found or not isinstance(value, dict):
            sys.exit(1)
        for key in value.keys():
            print(key)

if __name__ == "__main__":
    main()
