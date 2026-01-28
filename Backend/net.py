"""
Module de communication TCP pour MIRAGE
Gère l'écoute (listen) et l'envoi (send) de messages via TCP
"""

import asyncio
import socket
from typing import Callable, Optional
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TCPListener:
    """Serveur TCP pour écouter les messages entrants"""

    def __init__(self, host: str = "0.0.0.0", port: int = 9999):
        """
        Initialise le listener TCP

        Args:
            host: Adresse IP d'écoute (0.0.0.0 = toutes les interfaces)
            port: Port d'écoute
        """
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None
        self.is_running = False
        self.on_message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """
        Définit la fonction à appeler quand un message est reçu

        Args:
            callback: Fonction qui prend (message: bytes, address: tuple)
        """
        self.on_message_callback = callback

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Gère une connexion client entrante

        Args:
            reader: Stream pour lire les données
            writer: Stream pour écrire les données
        """
        addr = writer.get_extra_info('peername')
        logger.info(f"Connexion entrante de {addr}")

        try:
            # Lire les données (max 64KB par message)
            data = await reader.read(65536)

            if data:
                logger.info(f"Message reçu de {addr}: {len(data)} bytes")

                # Appeler le callback si défini
                if self.on_message_callback:
                    await self.on_message_callback(data, addr)

                # Envoyer un accusé de réception
                writer.write(b"ACK")
                await writer.drain()

        except Exception as e:
            logger.error(f"Erreur lors de la réception: {e}")

        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Connexion fermée avec {addr}")

    async def start(self):
        """Démarre le serveur TCP"""
        if self.is_running:
            logger.warning("Le serveur est déjà en cours d'exécution")
            return

        try:
            self.server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port
            )
            self.is_running = True

            addr = self.server.sockets[0].getsockname()
            logger.info(f"Serveur TCP démarré sur {addr[0]}:{addr[1]}")

            async with self.server:
                await self.server.serve_forever()

        except Exception as e:
            logger.error(f"Erreur lors du démarrage du serveur: {e}")
            self.is_running = False

    async def stop(self):
        """Arrête le serveur TCP"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.is_running = False
            logger.info("Serveur TCP arrêté")


class TCPSender:
    """Client TCP pour envoyer des messages"""

    @staticmethod
    async def send_message(host: str, port: int, message: bytes, timeout: int = 5) -> bool:
        """
        Envoie un message à un destinataire via TCP

        Args:
            host: Adresse IP du destinataire
            port: Port du destinataire
            message: Message à envoyer (en bytes)
            timeout: Timeout en secondes

        Returns:
            True si l'envoi a réussi, False sinon
        """
        try:
            # Établir la connexion
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )

            logger.info(f"Connexion établie avec {host}:{port}")

            # Envoyer le message
            writer.write(message)
            await writer.drain()
            logger.info(f"Message envoyé: {len(message)} bytes")

            # Attendre l'accusé de réception
            ack = await asyncio.wait_for(reader.read(100), timeout=timeout)
            logger.info(f"ACK reçu: {ack}")

            # Fermer la connexion
            writer.close()
            await writer.wait_closed()

            return True

        except asyncio.TimeoutError:
            logger.error(f"Timeout lors de la connexion à {host}:{port}")
            return False

        except ConnectionRefusedError:
            logger.error(f"Connexion refusée par {host}:{port}")
            return False

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi: {e}")
            return False


# Fonctions utilitaires pour faciliter l'utilisation

async def start_listener(host: str, port: int, on_message: Callable) -> TCPListener:
    """
    Démarre un listener TCP (fonction helper)

    Args:
        host: Adresse IP d'écoute
        port: Port d'écoute
        on_message: Callback appelé à la réception d'un message

    Returns:
        Instance du TCPListener
    """
    listener = TCPListener(host, port)
    listener.set_message_callback(on_message)

    # Lancer le serveur dans une tâche séparée
    asyncio.create_task(listener.start())

    return listener


async def send_tcp_message(host: str, port: int, message: bytes) -> bool:
    """
    Envoie un message TCP (fonction helper)

    Args:
        host: Adresse IP du destinataire
        port: Port du destinataire
        message: Message en bytes

    Returns:
        True si l'envoi a réussi
    """
    return await TCPSender.send_message(host, port, message)


def get_local_ip() -> str:
    """
    Récupère l'adresse IP locale de la machine

    Returns:
        Adresse IP locale (ex: 192.168.1.x)
    """
    try:
        # Astuce: se connecter à une IP externe pour obtenir l'IP locale
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


# Exemple d'utilisation (à supprimer ou commenter en prod)
async def example_callback(message: bytes, address: tuple):
    """Exemple de callback pour traiter les messages reçus"""
    print(f"Message reçu de {address}: {message[:50]}...")  # Affiche les 50 premiers bytes


if __name__ == "__main__":
    # Test du module
    async def main():
        # Exemple: démarrer un listener
        listener = await start_listener("0.0.0.0", 9999, example_callback)
        print(f"Listener démarré sur {get_local_ip()}:9999")

        # Garder le programme en vie
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await listener.stop()

    asyncio.run(main())
