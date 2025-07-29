def groom_json_string(json_string):
    json_string = json_string.replace("```json", "")
    json_string = json_string.replace("```", "")
    json_string = json_string.strip()
    return json_string
