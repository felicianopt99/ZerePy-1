from fastapi.testclient import TestClient
import sys
import os

# Adicionar o diretório raiz ao path
sys.path.append(os.getcwd())

from src.server.app import create_app

app = create_app()
client = TestClient(app)

def test_memory_api():
    print("🚀 Iniciando teste da API de Memória...")
    
    persona = "Daisy"
    user_id = "fan_123"
    fact = "Adora a cor azul e flores."
    
    # 1. Adicionar Memória via API
    print("📝 Testando POST /agent/memory/add...")
    response = client.post("/agent/memory/add", json={
        "persona_name": persona,
        "user_id": user_id,
        "fact": fact
    })
    assert response.status_code == 200
    print(f"✅ Sucesso: {response.json()}")
    
    # 2. Recuperar Memória via API
    print(f"🔍 Testando GET /agent/memory/{persona}/{user_id}...")
    response = client.get(f"/agent/memory/{persona}/{user_id}")
    assert response.status_code == 200
    memories = response.json().get("memories", [])
    print(f"✅ Memórias encontradas: {memories}")
    assert fact in memories
    
    # 3. Testar Mock Tasks com CRM
    print("📋 Testando POST /agent/tasks/mock...")
    response = client.post("/agent/tasks/mock")
    assert response.status_code == 200
    
    # Verificar se as tarefas no ficheiro têm os campos user_id e user_name
    tasks_response = client.get("/agent/tasks")
    tasks = tasks_response.json()
    dm_task = next((t for t in tasks if t["type"] == "dm"), None)
    
    if dm_task:
        print(f"✅ Tarefa DM encontrada com User: {dm_task.get('user_name')} ({dm_task.get('user_id')})")
        assert dm_task.get("user_id") == "fan_123"
        assert dm_task.get("user_name") == "João VIP"
    else:
        print("⚠️ Nenhuma tarefa DM encontrada nos mocks.")

    print("\n🎉 Todos os testes de API passaram!")

if __name__ == "__main__":
    test_memory_api()
