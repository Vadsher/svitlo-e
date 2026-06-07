from aiogram import Router

from src.handlers.common import router as common_router
from src.handlers.host_add import router as host_add_router
from src.handlers.host_list import router as host_list_router
from src.handlers.settings import router as settings_router

# Create a master router
router = Router()

# Include sub-routers. Order can matter if there are global message handlers,
# but since we use explicit FSM states and commands, this order is fine.
router.include_router(common_router)
router.include_router(host_add_router)
router.include_router(host_list_router)
router.include_router(settings_router)
