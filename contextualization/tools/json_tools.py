# Recursively go through the JSON and round the fields provided
def round_percentages(data, fields=["percentage"]):
    if isinstance(data, dict):
        for key, value in data.items():
            if key in fields:
                data[key] = round(data[key])
            elif isinstance(value, dict) or isinstance(value, list):
                round_percentages(value, fields)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) or isinstance(item, list):
                round_percentages(item, fields)
