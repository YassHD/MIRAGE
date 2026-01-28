"""
Module TCP pour Mirage - Communication peer-to-peer
"""

import asyncio
import logging
from typing import Callable, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TCPListener:
    """Écoute les messages TCP entrants"""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None
        self.callback: Optional[Callable] = None
    
    def set_callback(self, callback: Callable):
        """Définit la fonction appelée à la réception d'un message"""
        self.callback = callback
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Gère un client connecté"""
        addr = writer.get_extra_info('peername')
        logger.info(f"📩 Connexion de {addr}")
        
        try:
            # Lit le message (max 1 MB)
            data = await reader.read(1024 * 1024)
            
            if data and self.callback:
                await self.callback(data, addr)
            
            # Accusé de réception
            writer.write(b"OK")
            await writer.drain()
            
        except Exception as e:
            logger.error(f"❌ Erreur: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def start(self):
        """Démarre le serveur"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        logger.info(f"🎧 Écoute sur {self.host}:{self.port}")
        
        async with self.server:
            await self.server.serve_forever()
    
    async def stop(self):
        """Arrête le serveur"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("🛑 Serveur arrêté")


async def send_tcp_message(host: str, port: int, message: bytes) -> bool:
    """
    Envoie un message TCP
    
    Args:
        host: IP destination
        port: Port destination
        message: Message en bytes
    
    Returns:
        True si succès
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        
        writer.write(message)
        await writer.drain()
        
        # Attend l'ACK
        await asyncio.wait_for(reader.read(100), timeout=5)
        
        writer.close()
        await writer.wait_closed()
        
        logger.info(f"✅ Message envoyé à {host}:{port}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Échec envoi: {e}")
        return False


async def start_listener(host: str, port: int, on_message: Callable) -> TCPListener:
    """
    Démarre un listener (helper function)
    
    Args:
        host: IP d'écoute
        port: Port d'écoute
        on_message: Callback (message: bytes, addr: tuple)
    
    Returns:
        TCPListener instance
    """
    listener = TCPListener(host, port)
    listener.set_callback(on_message)
    asyncio.create_task(listener.start())
    return listener