from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

class IsAdminFilter(BaseFilter):
    """Filter that checks if the user is an admin or creator in a group, or just a regular user in a private chat."""
    async def __call__(self, obj: Message | CallbackQuery) -> bool:
        message = obj if isinstance(obj, Message) else obj.message
        user_id = obj.from_user.id
        
        # If it's a private chat, the user is always the "admin" of their own bot instance
        if message.chat.type == 'private':
            return True
            
        # For groups, check the user's status
        member = await message.chat.get_member(user_id)
        return member.status in ['creator', 'administrator']
