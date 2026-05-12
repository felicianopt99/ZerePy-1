import asyncio
import sys
import os

# Adicionar o diretório raiz ao path para importar src
sys.path.append(os.getcwd())

from src.memory import MemoryManager

async def test_memory():
    print("🚀 Iniciando teste de memória...")
    memory = MemoryManager(db_path="data/chroma_db_test")
    
    persona = "Daisy"
    user_id = "user_123"
    
    # 1. Adicionar memória
    print(f"📝 Adicionando facto para {persona}...")
    fact = "O utilizador gosta de café gelado com caramelo."
    mem_id = await memory.add_memory(persona, user_id, fact)
    print(f"✅ Memória adicionada com ID: {mem_id}")
    
    # 2. Recuperar memória
    print(f"🔍 Recuperando memórias para {user_id}...")
    memories = await memory.get_user_memories(persona, user_id)
    print(f"✅ Factos encontrados: {memories}")
    
    assert fact in memories, "Erro: Facto não encontrado nas memórias!"
    
    # 3. Testar isolamento (Outra persona)
    print(f"🧪 Testando isolamento entre personas...")
    persona_2 = "Astra"
    memories_astra = await memory.get_user_memories(persona_2, user_id)
    assert len(memories_astra) == 0, "Erro: Isolação de persona falhou!"
    print("✅ Isolação de persona confirmada.")
    
    # 4. Eliminar memória
    print(f"🗑️ Eliminando memória {mem_id}...")
    await memory.delete_memory(persona, mem_id)
    memories_after = await memory.get_user_memories(persona, user_id)
    assert mem_id not in memories_after, "Erro: Memória não foi eliminada!"
    print("✅ Eliminação confirmada.")
    
    print("\n🎉 Todos os testes passaram com sucesso!")

if __name__ == "__main__":
    asyncio.run(test_memory())
