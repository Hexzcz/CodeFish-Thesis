import json

with open("project8_roads.geojson") as f:
    data = json.load(f)


graph = {}

for feature in data["features"]:
    u = feature["properties"]["u"]
    v = feature["properties"]["v"]
    length = feature["properties"]["length"]
    oneway = feature["properties"]["oneway"]

    if u not in graph:
        graph[u] = []
    graph[u].append((v, length))
    
    