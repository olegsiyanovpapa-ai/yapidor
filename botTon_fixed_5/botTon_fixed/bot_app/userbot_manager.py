import logging
from pyrogram import Client
from pyrogram.errors import RPCError
from pyrogram.raw.functions.users import GetFullUser
from bot_app.config import USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSION_NAME
import os

logger = logging.getLogger(__name__)

class UserBotManager:
    def __init__(self):
        self.api_id = USERBOT_API_ID
        self.api_hash = USERBOT_API_HASH
        self.session_name = USERBOT_SESSION_NAME
        self.client = None

    async def get_client(self):
        if self.client is None:
            # Check if session file exists
            if not os.path.exists(f"{self.session_name}.session"):
                logger.error(f"UserBot session file {self.session_name}.session not found!")
                return None
            
            self.client = Client(
                self.session_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                no_updates=True # We don't need to process updates for gift sending
            )
        return self.client

    async def send_gift(self, user_id: int, gift_id: str, message: str = None, is_anonymous: bool = False):
        """
        Sends a gift using the UserBot account.
        """
        client = await self.get_client()
        if not client:
            return False, "UserBot session not initialized"

        try:
            if not client.is_connected:
                await client.start()
            
            from pyrogram.raw.functions.payments import SendGift
            from pyrogram.raw.types import TextWithEntities
            
            peer = await client.resolve_peer(user_id)
            
            # Prepare message as TextWithEntities
            msg_obj = TextWithEntities(text=message, entities=[]) if message else None
            
            result = await client.invoke(
                SendGift(
                    user_id=peer,
                    gift_id=int(gift_id),
                    message=msg_obj,
                    is_anonymous=is_anonymous
                )
            )
            logger.info(f"UserBot successfully sent gift {gift_id} to user {user_id} (Anon: {is_anonymous})")
            return True, "Success"
        except RPCError as e:
            logger.error(f"UserBot failed to send gift: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error in UserBot send_gift: {e}")
            return False, str(e)

    async def get_account_stars_balance(self):
        """
        Fetches the Stars balance of the UserBot account.
        """
        client = await self.get_client()
        if not client:
            return 0

        try:
            if not client.is_connected:
                await client.start()
            
            # Using GetFullUser for self to get stars balance
            me = await client.get_me()
            peer = await client.resolve_peer(me.id)
            full_user_resp = await client.invoke(GetFullUser(id=peer))
            
            # The result of GetFullUser is a UserFull object which contains a 'full_user' field
            full_user = getattr(full_user_resp, 'full_user', None)
            if full_user:
                return getattr(full_user, 'stars', 0)
            return 0
        except Exception as e:
            logger.error(f"Error fetching UserBot stars balance: {e}")
            return 0
        finally:
            # We keep the client running or stop it depending on load. 
            # For rarity of gifts, stopping is fine, but starting takes time.
            # Let's keep it connected but for now we'll stop to avoid issues.
            pass

userbot_manager = UserBotManager()
