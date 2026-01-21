from fastapi import APIRouter, Depends
from app.api import deps
from app.models.project import Project

router = APIRouter()

@router.get("/validate")
def validate_access(
    project: Project = Depends(deps.verify_public_origin),
):
    """
    Test endpoint to verify API Key + Origin validation.
    """
    return {
        "status": "allowed",
        "project": project.name,
        "domains": [d.domain for d in project.domains]
    }

@router.get("/ping")
def ping_connection(
    project: Project = Depends(deps.verify_public_origin),
):
    """
    Simple connectivity check for widgets.
    """
    return {"status": "connected", "project": project.name}

@router.get("/widget.js")
def get_widget_js():
    """
    Returns the JavaScript loader script.
    In a real app, this would be dynamically generated or served from a CDN.
    For now, it returns a script that logs to console and verifies connection.
    """
    js_content = """
(function() {
    console.log("SkisPlace Widget: Loading...");
    
    // Find my own script tag to read config
    var scripts = document.getElementsByTagName('script');
    var myScript = null;
    for (var i = 0; i < scripts.length; i++) {
        if (scripts[i].src.includes('widget.js')) {
            myScript = scripts[i];
            break;
        }
    }
    
    if (!myScript) {
        console.error("SkisPlace Widget: Could not find script tag.");
        return;
    }
    
    var apiKey = myScript.getAttribute('data-api-key');
    var projectId = myScript.getAttribute('data-project-id');
    var modules = myScript.getAttribute('data-modules');
    
    // Derive API Base URL from script src
    // Expecting src like ".../api/v1/public/widget.js"
    // We want ".../api/v1/public/validate"
    var src = myScript.src;
    var baseUrl = src.substring(0, src.lastIndexOf('/')); // removes 'widget.js'
    
    console.log("SkisPlace Widget: Config Found", { apiKey, projectId, modules, baseUrl });
    
    // Test Connection
    fetch(baseUrl + '/validate', {
        headers: {
            'X-API-KEY': apiKey
        }
    })
    .then(response => {
        if (response.ok) {
            console.log("SkisPlace Widget: ✅ Connection Verified!");
            return response.json();
        } else {
            console.error("SkisPlace Widget: ❌ Connection Failed (" + response.status + ")");
        }
    })
    .then(data => {
        if(data) console.log("SkisPlace Widget: Data", data);
    })
    .catch(err => console.error("SkisPlace Widget: Network Error", err));

})();
    """
    from fastapi.responses import Response
    return Response(content=js_content, media_type="application/javascript")

@router.post("/render")
def render_preview(
    project: Project = Depends(deps.verify_public_origin),
    # body: dict = Body(...) # In real app we'd declare a schema
):
    """
    Stub endpoint for rendering.
    """
    # Simulate processing delay if we wanted, but immediate is fine for MVP.
    return {
        "status": "success",
        "result_url": "https://images.unsplash.com/photo-1516455590571-18256e5bb9ff?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80" # Placeholder epoxy floor image
    }
