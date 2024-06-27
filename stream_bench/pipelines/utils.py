def merge_dicts(dicts: list[dict]) -> dict:
    d = dict()
    for dd in dicts:
        for k, v in dd.items():
            if (k in d) and (d[k] != v):
                print(k, d[k], v)
                raise ValueError("Found duplicated and inconsistent key-value pair.")
            d[k] = v
    return d
