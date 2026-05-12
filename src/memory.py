import chromadb
import uuid
import asyncio
import logging
from typing import List
from pathlib import Path

logger = logging.getLogger("memory")

class MemoryManager:
    def __init__(self, db_path: str = "data/chroma_db"):
        """
        Inicializa o cliente persistente do ChromaDB.
        """
        # Garantir que o diretório base existe
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)

    async def get_or_create_collection(self, persona_name: str):
        """
        Cria ou obtém uma coleção para isolar as memórias por modelo virtual.
        """
        # Sanitizar nome da persona para ser compatível com ChromaDB (3-63 chars, alnum, underscores, hyphens)
        safe_name = "".join(c for c in persona_name if c.isalnum() or c in ("_", "-")).lower()
        if len(safe_name) < 3:
            safe_name = f"persona_{safe_name}"
            
        return await asyncio.to_thread(self.client.get_or_create_collection, name=safe_name)

    async def add_memory(self, persona_name: str, user_id: str, fact: str) -> str:
        """
        Gera um ID único, adiciona o facto e guarda o user_id nos metadados.
        """
        collection = await self.get_or_create_collection(persona_name)
        memory_id = str(uuid.uuid4())
        
        await asyncio.to_thread(
            collection.add,
            ids=[memory_id],
            documents=[fact],
            metadatas=[{"user_id": str(user_id)}]
        )
        logger.info(f"Memória adicionada para {persona_name} (User: {user_id}): {memory_id}")
        return memory_id

    async def get_user_memories(self, persona_name: str, user_id: str) -> List[str]:
        """
        Faz query à coleção filtrando pelos metadados {"user_id": user_id} e retorna os factos.
        """
        collection = await self.get_or_create_collection(persona_name)
        
        # Utilizamos o método .get() para filtrar por metadados de forma exata
        results = await asyncio.to_thread(
            collection.get,
            where={"user_id": str(user_id)}
        )
        
        return results.get("documents", [])

    async def delete_memory(self, persona_name: str, memory_id: str):
        """
        Permite a gestão manual, removendo uma memória específica por ID.
        """
        collection = await self.get_or_create_collection(persona_name)
        
        await asyncio.to_thread(
            collection.delete,
            ids=[memory_id]
        )
        logger.info(f"Memória {memory_id} removida da coleção {persona_name}")
