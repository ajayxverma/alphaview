from contextlib import asynccontextmanager

from alphaview_common.db import init_schema
from alphaview_common.web import create_app
from alphaview_integrations.api import router
from alphaview_integrations.models import SCHEMA, Base, engine


@asynccontextmanager
async def lifespan(_app):
    await init_schema(engine, Base, SCHEMA)
    yield


app = create_app("integrations", lifespan)
app.include_router(router)
