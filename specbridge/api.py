from ninja import NinjaAPI

from agents.api import router as agents_router
from alignment.api import router as alignment_router
from exports.api import router as exports_router
from projects.api import router as projects_router
from specs.api import router as specs_router

api = NinjaAPI(title="SpecBridge API", version="1.0", csrf=True)
api.add_router("/projects", projects_router)
api.add_router("/projects", alignment_router)
api.add_router("/projects", specs_router)
api.add_router("/projects", agents_router)
api.add_router("/projects", exports_router)
