from datetime import datetime, timezone
from fastapi import APIRouter, Request
router=APIRouter(prefix='/v1')
@router.get('/healthz')
async def healthz(request: Request):
    return {'status':'ok','uptime_seconds':round(request.app.state.store.uptime(),3),'contexts_loaded':await request.app.state.store.counts()}
@router.get('/metadata')
async def metadata():
    return {'team_name': 'Sandeep Vera Challenge', 'team_members':['Sandeep Kumar'], 'model': 'deterministic-grounded-composer', 'approach':'deterministic trigger routing with optional LLM wording and strict validation', 'contact_email':'', 'version':'0.2.0', 'submitted_at':datetime.now(timezone.utc).isoformat()}
