"""
TON Connect Manager - handles wallet connections via TON Connect 2.0
"""
import asyncio
import json
import logging
from typing import Optional, Dict
from io import BytesIO

from pytonconnect import TonConnect
from pytonconnect.storage import IStorage
import qrcode

from .config import TON_CONNECT_MANIFEST_URL, TON_CONNECT_TIMEOUT
from .database import save_ton_connect_session, get_ton_connect_session, delete_ton_connect_session
from .ton_utils import raw_to_user_friendly


class SQLiteStorage(IStorage):
    """SQLite storage adapter for TON Connect sessions"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self._cache = {}
    
    async def set_item(self, key: str, value: str):
        """Store item in cache and DB"""
        self._cache[key] = value
        # Save to DB on every update to ensure persistence
        session_data = json.dumps(self._cache)
        await save_ton_connect_session(self.user_id, None, session_data)
    
    async def get_item(self, key: str, default_value: str = None) -> Optional[str]:
        """Get item from cache"""
        return self._cache.get(key, default_value)
    
    async def remove_item(self, key: str):
        """Remove item from cache and DB"""
        self._cache.pop(key, None)
        session_data = json.dumps(self._cache)
        await save_ton_connect_session(self.user_id, None, session_data)


class TonConnectManager:
    """Manages TON Connect wallet connections"""
    
    def __init__(self):
        self.connectors: Dict[int, TonConnect] = {}
        self.logger = logging.getLogger(__name__)
    
    async def get_connector(self, user_id: int) -> TonConnect:
        """Get or create TON Connect instance for user"""
        if user_id not in self.connectors:
            storage = SQLiteStorage(user_id)
            
            # Try to restore session from database
            session = await get_ton_connect_session(user_id)
            if session and session.get("session_data"):
                try:
                    session_dict = json.loads(session["session_data"])
                    storage._cache = session_dict
                except Exception as e:
                    self.logger.error(f"Failed to load session data for user {user_id}: {e}")
            
            connector = TonConnect(
                manifest_url=TON_CONNECT_MANIFEST_URL,
                storage=storage
            )
            # Store storage instance on connector for easy access
            connector.storage_instance = storage
            
            # Only attempt restore if we have cache data
            if storage._cache:
                try:
                    # Set a timeout for restore_connection if the library supports it, 
                    # otherwise wrap in asyncio.wait_for
                    await asyncio.wait_for(connector.restore_connection(), timeout=2.0)
                except asyncio.TimeoutError:
                    self.logger.warning(f"Restore connection timed out for user {user_id}")
                except Exception as e:
                    self.logger.error(f"Failed to restore connection for user {user_id}: {e}")
            
            self.connectors[user_id] = connector
        
        return self.connectors[user_id]
    
    async def generate_connect_url(self, user_id: int) -> str:
        """Generate connection URL for wallet"""
        self.logger.info(f"[TON-CONNECT] ⚙️  Generating connect URL for user {user_id}")
        self.logger.info(f"[TON-CONNECT] 📄 Manifest URL: {TON_CONNECT_MANIFEST_URL}")

        # FORCE REBUILD: fresh connector every time
        if user_id in self.connectors:
            self.logger.info(f"[TON-CONNECT] 🗑️  Purging existing connector for user {user_id}")
            del self.connectors[user_id]
            
        connector = await self.get_connector(user_id)
        self.logger.info(f"[TON-CONNECT] ✅ Connector created for user {user_id}")
        
        # Clear any existing session in the library itself
        if connector.connected:
            self.logger.info(f"[TON-CONNECT] 🔌 Disconnecting stale session for user {user_id}")
            try:
                await connector.disconnect()
                self.logger.info(f"[TON-CONNECT] ✅ Stale session disconnected")
            except Exception as e:
                self.logger.warning(f"[TON-CONNECT] ⚠️  Disconnect failed (ignorable): {e}")

        # Get wallets list
        wallets = connector.get_wallets()
        self.logger.info(f"[TON-CONNECT] 💼 Available wallets: {[w['name'] for w in wallets]}")
        tonkeeper = next((w for w in wallets if 'tonkeeper' in w['name'].lower()), wallets[0] if wallets else None)
        
        if not tonkeeper:
            self.logger.error("[TON-CONNECT] ❌ No wallets available in connector!")
            raise Exception("No wallets available in connector")
        
        self.logger.info(f"[TON-CONNECT] 🔗 Connecting with wallet: {tonkeeper['name']}")
        connect_url = await connector.connect(tonkeeper)
        self.logger.info(f"[TON-CONNECT] 🌐 Connect URL generated: {connect_url[:60]}...")
        
        return connect_url
    
    async def wait_for_connection(self, user_id: int, timeout: int = 300) -> Optional[str]:
        """Wait for wallet connection and return wallet address (Default 5 min)"""
        connector = await self.get_connector(user_id)
        
        self.logger.info(f"[TON-CONNECT] ⏳ Polling for wallet connection: user={user_id}, timeout={timeout}s")
        
        try:
            for i in range(timeout):
                if connector.connected:
                    if connector.account and connector.account.address:
                        wallet_address = connector.account.address
                        friendly = raw_to_user_friendly(wallet_address)
                        self.logger.info(f"[TON-CONNECT] ✅ Wallet CONNECTED at second {i}: user={user_id}, addr={friendly}")
                        
                        storage = connector.storage_instance
                        session_data = json.dumps(storage._cache)
                        await save_ton_connect_session(user_id, wallet_address, session_data)
                        self.logger.info(f"[TON-CONNECT] 💾 Session saved to DB for user {user_id}")
                        
                        return wallet_address
                    else:
                        self.logger.warning(f"[TON-CONNECT] ⚠️  connected=True but account is None (second {i}) for user {user_id}")
                else:
                    if i % 10 == 0:  # Print every 10s to avoid spam
                        self.logger.info(f"[TON-CONNECT] ⌛ Still waiting... second {i}/{timeout} for user {user_id}")
                
                await asyncio.sleep(1)
            
            self.logger.warning(f"[TON-CONNECT] ⏱️  TIMEOUT after {timeout}s for user {user_id} — no connection detected")
            return None
        except Exception as e:
            self.logger.error(f"[TON-CONNECT] ❌ CRITICAL Error in wait_for_connection for user {user_id}: {e}", exc_info=True)
            return None
    
    async def get_connected_wallet(self, user_id: int) -> Optional[str]:
        """Get connected wallet address for user"""
        try:
            connector = await self.get_connector(user_id)
            
            if connector.connected:
                return connector.account.address
            
            # Try to restore from database
            session = await get_ton_connect_session(user_id)
            if session:
                # If wallet_address column is set, use it
                addr = session.get("wallet_address")
                if addr:
                    return addr
                
                # Fallback: try to extract from session_data JSON
                data_str = session.get("session_data")
                if data_str:
                    try:
                        data = json.loads(data_str)
                        # pytonconnect stores connection info in 'ton-connect-storage_bridge-connection'
                        conn_info = data.get('ton-connect-storage_bridge-connection')
                        if conn_info:
                            conn_dict = json.loads(conn_info)
                            # Extract address from the connect event if present
                            # This is a bit of a hack but ensures we find the real address
                            return conn_dict.get('connect_event', {}).get('payload', {}).get('items', [{}])[0].get('address')
                    except:
                        pass
            
            return None
        except Exception as e:
            self.logger.error(f"Error getting wallet for user {user_id}: {e}")
            return None
    
    async def disconnect_wallet(self, user_id: int):
        """Disconnect wallet for user"""
        try:
            connector = await self.get_connector(user_id)
            
            if connector.connected:
                try:
                    await asyncio.wait_for(connector.disconnect(), timeout=3.0)
                except Exception as e:
                    self.logger.warning(f"Library disconnect failed for user {user_id}: {e}")
            
            # ALWAYS remove from database and cache, even if disconnect() failed 
            # to ensure the user can start over.
            await delete_ton_connect_session(user_id)
            
            if user_id in self.connectors:
                del self.connectors[user_id]
        except Exception as e:
            self.logger.error(f"Error disconnecting wallet for user {user_id}: {e}")
            # Ensure at least DB/Cache removal is attempted again if something else failed
            try:
                await delete_ton_connect_session(user_id)
                self.connectors.pop(user_id, None)
            except: pass
    
    def generate_qr_code(self, url: str) -> BytesIO:
        """Generate QR code image from URL"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        
        return bio


# Global instance
ton_connect_manager = TonConnectManager()
