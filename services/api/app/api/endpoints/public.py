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
    
    console.log("SkisPlace Widget: Config Found", { apiKey, projectId, modules });
    
    // Test Connection
    fetch('http://localhost:8000/api/v1/public/validate', {
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
