from fastapi import APIRouter, HTTPException, Depends, Request

router = APIRouter()

def get_app_state(request: Request):
    return request.app.state.data

@router.get("/evacuation-centers")
async def get_evacuation_centers(state: dict = Depends(get_app_state)):
    evac_geojson = state.get('evac_geojson')
    if evac_geojson is None:
        raise HTTPException(404, "Evacuation centers not loaded")
    return evac_geojson

@router.get("/health")
async def health_check(state: dict = Depends(get_app_state)):
    graph = state['graph']
    models = state['models']
    centers = state['centers']
    return {
        "status": "ok",
        "graph_nodes": graph.node_count(),
        "graph_edges": graph.edge_count(),
        "evac_centers": len(centers),
        "models_loaded": list(models.keys()),
    }
