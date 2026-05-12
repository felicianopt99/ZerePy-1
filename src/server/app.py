from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import asyncio
import json
import signal
import threading
import asyncio
import base64
import httpx
import time
import os
import random
from pathlib import Path
from src.cli import ZerePyCLI
from src.memory import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server/app")

class ActionRequest(BaseModel):
    """Request model for agent actions"""
    connection: str
    action: str
    params: Optional[List[str]] = []

class ConfigureRequest(BaseModel):
    """Request model for configuring connections"""
    connection: str
    params: Optional[Dict[str, Any]] = {}

class ChatRequest(BaseModel):
    """Request model for chat messages"""
    message: str

class UniversalImageRequest(BaseModel):
    """Request model for universal image generation"""
    method: str = "gemini" # gemini or comfy
    persona_name: str
    prompt: str
    aspect_ratio: str = "1:1"
    seed: Optional[int] = None
    style_preset: Optional[str] = "Realism"
    quality: Optional[str] = "Standard"

class MemoryAddRequest(BaseModel):
    """Request model for adding a memory"""
    persona_name: str
    user_id: str
    fact: str

class AgentSaveRequest(BaseModel):
    """Request model for saving agent configuration"""
    name: str
    bio: List[str]
    traits: List[str]
    visual_prompt_base: Optional[str] = ""
    examples: Optional[List[str]] = []
    example_accounts: Optional[List[str]] = []
    loop_delay: Optional[int] = 900
    config: Optional[List[Dict[str, Any]]] = []
    tasks: Optional[List[Dict[str, Any]]] = []
    use_time_based_weights: Optional[bool] = False
    time_based_multipliers: Optional[Dict[str, float]] = {}

    class Config:
        extra = "allow"

class Task(BaseModel):
    """Model for a pending HITL task"""
    id: str
    persona: str
    type: str  # post|dm
    platform: str  # instagram|fanvue|twitter
    content: str
    image_url: Optional[str] = None
    status: str = "pending"
    user_id: Optional[str] = None
    user_name: Optional[str] = None

class ApproveTaskRequest(BaseModel):
    """Request model for approving a task with optional edits"""
    content: str

class ServerState:
    """Simple state management for the server"""
    def __init__(self):
        self.cli = ZerePyCLI()
        try:
            self.cli._load_default_agent()
        except Exception:
            pass
        self.agent_running = False
        self.agent_task = None
        self._stop_event = threading.Event()

    def _run_agent_loop(self):
        """Run agent loop in a separate thread"""
        try:
            log_once = False
            while not self._stop_event.is_set():
                if self.cli.agent:
                    try:
                        if not log_once:
                            logger.info("Loop logic not implemented")
                            log_once = True

                    except Exception as e:
                        logger.error(f"Error in agent action: {e}")
                        if self._stop_event.wait(timeout=30):
                            break
        except Exception as e:
            logger.error(f"Error in agent loop thread: {e}")
        finally:
            self.agent_running = False
            logger.info("Agent loop stopped")

    async def start_agent_loop(self):
        """Start the agent loop in background thread"""
        if not self.cli.agent:
            raise ValueError("No agent loaded")
        
        if self.agent_running:
            raise ValueError("Agent already running")

        self.agent_running = True
        self._stop_event.clear()
        self.agent_task = threading.Thread(target=self._run_agent_loop)
        self.agent_task.start()

    async def stop_agent_loop(self):
        """Stop the agent loop"""
        if self.agent_running:
            self._stop_event.set()
            if self.agent_task:
                self.agent_task.join(timeout=5)
            self.agent_running = False

class ZerePyServer:
    def __init__(self):
        self.app = FastAPI(title="ZerePy Server")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.state = ServerState()
        self.memory = MemoryManager()
        self.setup_routes()
        
        # Mount static files
        static_path = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=str(static_path), html=True), name="static")
        
        # Initialize tasks storage
        self.tasks_path = Path("data") / "pending_tasks.json"
        self._ensure_tasks_file()

    def _ensure_tasks_file(self):
        """Ensure the tasks file exists and is a valid JSON array"""
        if not self.tasks_path.parent.exists():
            self.tasks_path.parent.mkdir(parents=True)
        if not self.tasks_path.exists():
            with open(self.tasks_path, "w") as f:
                json.dump([], f)

    def _read_tasks(self) -> List[Dict[str, Any]]:
        """Read tasks from the JSON file"""
        try:
            with open(self.tasks_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_tasks(self, tasks: List[Dict[str, Any]]):
        """Write tasks to the JSON file"""
        with open(self.tasks_path, "w") as f:
            json.dump(tasks, f, indent=2)

    def setup_routes(self):
        @self.app.get("/")
        async def root():
            """Server status endpoint"""
            return {
                "status": "running",
                "agent": self.state.cli.agent.name if self.state.cli.agent else None,
                "agent_running": self.state.agent_running
            }

        @self.app.get("/agents")
        async def list_agents():
            """List available agents"""
            try:
                agents = []
                agents_dir = Path("agents")
                if agents_dir.exists():
                    for agent_file in agents_dir.glob("*.json"):
                        if agent_file.stem != "general":
                            agents.append(agent_file.stem)
                return {"agents": agents}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agents/{name}/load")
        async def load_agent(name: str):
            """Load a specific agent"""
            try:
                self.state.cli._load_agent_from_file(name)
                return {
                    "status": "success",
                    "agent": name
                }
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/agents/{name}/config")
        async def get_agent_config(name: str):
            """Get configuration of a specific agent"""
            try:
                agent_path = Path("agents") / f"{name}.json"
                if not agent_path.exists():
                    raise HTTPException(status_code=404, detail="Agent not found")
                
                with open(agent_path, "r") as f:
                    config = json.load(f)
                return config
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agent/save")
        async def save_agent(agent_data: AgentSaveRequest):
            """Save or overwrite an agent's configuration"""
            try:
                agents_dir = Path("agents")
                agents_dir.mkdir(exist_ok=True)
                
                # Sanitize filename
                safe_name = "".join(c for c in agent_data.name if c.isalnum() or c in ("-", "_")).strip()
                if not safe_name:
                    raise HTTPException(status_code=400, detail="Invalid agent name")
                
                file_path = agents_dir / f"{safe_name}.json"
                
                # Convert Pydantic model to dict
                data = agent_data.dict()
                
                with open(file_path, "w") as f:
                    json.dump(data, f, indent=2)
                
                return {"status": "success", "message": f"Agent {safe_name} saved successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/connections")
        async def list_connections():
            """List all available connections"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                connections = {}
                for name, conn in self.state.cli.agent.connection_manager.connections.items():
                    connections[name] = {
                        "configured": conn.is_configured(),
                        "is_llm_provider": conn.is_llm_provider
                    }
                return {"connections": connections}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agent/action")
        async def agent_action(action_request: ActionRequest):
            """Execute a single agent action"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                result = await asyncio.to_thread(
                    self.state.cli.agent.perform_action,
                    connection=action_request.connection,
                    action=action_request.action,
                    params=action_request.params
                )
                return {"status": "success", "result": result}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/agent/start")
        async def start_agent():
            """Start the agent loop"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                await self.state.start_agent_loop()
                return {"status": "success", "message": "Agent loop started"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/agent/stop")
        async def stop_agent():
            """Stop the agent loop"""
            try:
                await self.state.stop_agent_loop()
                return {"status": "success", "message": "Agent loop stopped"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/agent/chat")
        async def chat(chat_request: ChatRequest):
            """Send a message to the agent and get a response"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                # Use the prompt LLM to get a response
                response = self.state.cli.agent.prompt_llm(chat_request.message)
                return {"status": "success", "response": response}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/agent/generate_image")
        async def generate_image(request: UniversalImageRequest):
            """Generate an image using selected method"""
            try:
                # 1. Load agent config for visual context
                agent_path = Path("agents") / f"{request.persona_name}.json"
                if not agent_path.exists():
                    raise HTTPException(status_code=404, detail=f"Agent {request.persona_name} not found")
                
                with open(agent_path, "r") as f:
                    agent_config = json.load(f)
                
                visual_prompt_base = agent_config.get("visual_prompt_base", "")
                
                # --- PROMPT COMPOSER ---
                style_keywords = {
                    "Polaroid": "vintage polaroid, 1990s aesthetic, film grain, slight motion blur, instant camera photo, washed colors",
                    "Cinematic": "highly detailed, masterpiece, 8k, dramatic cinematic lighting, rim lighting, depth of field, f/1.8, movie still",
                    "Realist": "raw photo, photorealistic, 8k, ultra-high resolution, sharp focus, professional street photography, natural lighting",
                    "Anime": "high quality anime style, vibrant colors, clean lines, cel shaded",
                    "Digital Art": "vibrant digital illustration, trending on artstation, sharp details"
                }
                style_bonus = style_keywords.get(request.style_preset, "")
                
                full_prompt = f"{visual_prompt_base}, {request.prompt}" if visual_prompt_base else request.prompt
                if style_bonus:
                    full_prompt = f"{full_prompt}, {style_bonus}"
                
                gallery_dir = Path(__file__).parent / "static" / "gallery"
                gallery_dir.mkdir(parents=True, exist_ok=True)
                timestamp = int(time.time())

                if request.method == "gemini":
                    # --- GEMINI MODE ---
                    gemini_conn = self.state.cli.agent.connection_manager.connections.get("gemini_vision")
                    api_key = os.getenv("GEMINI_API_KEY")
                    
                    if not api_key:
                        raise HTTPException(status_code=400, detail="Gemini Vision connection is not configured (API Key missing)")
                    
                    logger.info(f"Generating Gemini image: {full_prompt} | Ratio: {request.aspect_ratio}")
                    
                    # Mapping aspect ratios for Imagen 3
                    # Values: "1:1", "9:16", "16:9", "4:3", "3:4"
                    ratio_map = {
                        "Square 1:1": "1:1",
                        "Portrait 4:5": "3:4",
                        "Story 9:16": "9:16"
                    }
                    target_ratio = ratio_map.get(request.aspect_ratio, "1:1")

                    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={api_key}"
                    
                    # Professional payload for Imagen 3
                    payload = {
                        "instances": [{"prompt": full_prompt}],
                        "parameters": {
                            "sampleCount": 1,
                            "aspectRatio": target_ratio,
                            "safetySetting": "block_none" if request.quality == "High-Res" else "block_medium_and_above"
                        }
                    }
                    
                    if request.seed is not None:
                        payload["parameters"]["seed"] = request.seed

                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.post(api_url, json=payload)
                        if resp.status_code != 200:
                            raise HTTPException(status_code=resp.status_code, detail=f"Gemini Error: {resp.text}")
                        
                        data = resp.json()
                        img_b64 = data.get("predictions", [{}])[0].get("bytesBase64Encoded")
                        if not img_b64:
                            raise HTTPException(status_code=500, detail="Gemini API prediction missing image data")

                        local_filename = f"gemini_{timestamp}.png"
                        local_path = gallery_dir / local_filename
                        with open(local_path, "wb") as f:
                            f.write(base64.b64decode(img_b64))

                else:
                    # --- COMFYUI MODE ---
                    logger.info(f"Generating ComfyUI image: {full_prompt}")
                    workflow_path = Path("comfy_workflows") / "default_workflow.json"
                    with open(workflow_path, "r") as f:
                        workflow = json.load(f)
                    
                    # Inject prompt into Node 6
                    if "6" in workflow: workflow["6"]["inputs"]["text"] = f"{full_prompt}, style of {request.style_preset}"
                    
                    # Inject Seed into Node 3 (KSampler)
                    if "3" in workflow:
                        seed = request.seed if request.seed is not None else random.randint(1, 1125899906842624)
                        workflow["3"]["inputs"]["seed"] = seed
                    
                    # Inject Aspect Ratio into Node 5 (EmptyLatentImage)
                    if "5" in workflow:
                        # Standard 512 base
                        if request.aspect_ratio == "Square 1:1":
                            width, height = 512, 512
                        elif request.aspect_ratio == "Portrait 4:5":
                            width, height = 512, 640
                        elif request.aspect_ratio == "Story 9:16":
                            width, height = 512, 910
                        else:
                            width, height = 512, 512
                            
                        # High-Res scale
                        if request.quality == "High-Res":
                            width = int(width * 1.5)
                            height = int(height * 1.5)
                            
                        workflow["5"]["inputs"]["width"] = width
                        workflow["5"]["inputs"]["height"] = height

                    # Get URL from environment
                    api_url = os.getenv("COMFYUI_API_URL")
                    if not api_url:
                        raise HTTPException(status_code=400, detail="ComfyUI connection is not configured (URL missing)")
                    
                    api_url = api_url.rstrip("/")
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        p_resp = await client.post(f"{api_url}/prompt", json={"prompt": workflow})
                        prompt_id = p_resp.json().get("prompt_id")
                        
                        # Polling
                        filename = None
                        for _ in range(45):
                            await asyncio.sleep(2)
                            h_resp = await client.get(f"{api_url}/history/{prompt_id}")
                            if h_resp.status_code == 200 and prompt_id in h_resp.json():
                                outputs = h_resp.json()[prompt_id].get("outputs", {})
                                for n in outputs:
                                    if "images" in outputs[n]:
                                        filename = outputs[n]["images"][0]["filename"]
                                        break
                                if filename: break
                        
                        if not filename: raise HTTPException(status_code=504, detail="ComfyUI Timeout")
                        
                        v_resp = await client.get(f"{api_url}/view", params={"filename": filename})
                        local_filename = f"comfy_{timestamp}_{filename}"
                        local_path = gallery_dir / local_filename
                        with open(local_path, "wb") as f:
                            f.write(v_resp.content)

                return {
                    "status": "success",
                    "image_url": f"/static/gallery/{local_filename}",
                    "prompt": full_prompt
                }

            except Exception as e:
                logger.error(f"Image generation failed: {e}")
                if isinstance(e, HTTPException): raise e
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agent/tasks/create")
        async def create_task(request: Dict[str, Any]):
            """Create a new task manually (e.g. from gallery)"""
            import uuid
            tasks = self._read_tasks()
            new_task = {
                "id": str(uuid.uuid4()),
                "persona": request.get("persona", "Daisy"),
                "type": "post",
                "platform": "instagram",
                "content": request.get("content", ""),
                "image_url": request.get("image_url"),
                "status": "pending"
            }
            tasks.insert(0, new_task)
            self._write_tasks(tasks)
            return {"status": "success", "task": new_task}


        @self.app.get("/agent/gallery_images")
        async def get_gallery_images():
            """List all images in the gallery directory"""
            try:
                gallery_dir = Path(__file__).parent / "static" / "gallery"
                if not gallery_dir.exists():
                    return {"images": []}
                
                images = []
                for file in gallery_dir.iterdir():
                    if file.is_file() and file.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                        mtime = file.stat().st_mtime
                        images.append({
                            "url": f"/static/gallery/{file.name}",
                            "name": file.name,
                            "time": mtime
                        })
                
                images.sort(key=lambda x: x["time"], reverse=True)
                return {"images": images}
            except Exception as e:
                logger.error(f"Gallery list error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/connections/{name}/configure")
        async def configure_connection(name: str, config: ConfigureRequest):
            """Configure a specific connection"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                connection = self.state.cli.agent.connection_manager.connections.get(name)
                if not connection:
                    raise HTTPException(status_code=404, detail=f"Connection {name} not found")
                
                success = connection.configure(**config.params)
                if success:
                    return {"status": "success", "message": f"Connection {name} configured successfully"}
                else:
                    raise HTTPException(status_code=400, detail=f"Failed to configure {name}")
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/connections/{name}/status")
        async def connection_status(name: str):
            """Get configuration status of a connection"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
                
            try:
                connection = self.state.cli.agent.connection_manager.connections.get(name)
                if not connection:
                    raise HTTPException(status_code=404, detail=f"Connection {name} not found")
                    
                return {
                    "name": name,
                    "configured": connection.is_configured(verbose=True),
                    "is_llm_provider": connection.is_llm_provider
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/agent/tasks")
        async def get_tasks():
            """Get all pending tasks"""
            return self._read_tasks()

        @self.app.post("/agent/tasks/{task_id}/approve")
        async def approve_task(task_id: str, request: ApproveTaskRequest):
            """Approve and 'publish' a task"""
            tasks = self._read_tasks()
            task_index = next((i for i, t in enumerate(tasks) if t["id"] == task_id), None)
            
            if task_index is None:
                raise HTTPException(status_code=404, detail="Task not found")
            
            task = tasks.pop(task_index)
            task["content"] = request.content
            task["status"] = "approved"
            
            # Simulate publication
            logger.info(f"--- PUBLISHING TASK ---")
            logger.info(f"Platform: {task.get('platform')}")
            logger.info(f"Content: {task['content']}")
            if task.get("image_url"):
                logger.info(f"Image: {task['image_url']}")
            logger.info(f"-----------------------")
            
            
            self._write_tasks(tasks)
            
            # (Opcional) Log para demonstrar injeção de memória
            if task.get("user_id"):
                memories = await self.memory.get_user_memories(task["persona"], task["user_id"])
                logger.info(f"Contexto injetado na IA para {task['user_id']}: {memories}")

            return {"status": "success", "message": "Task approved and published"}

        @self.app.post("/agent/tasks/{task_id}/reject")
        async def reject_task(task_id: str):
            """Reject and remove a task"""
            tasks = self._read_tasks()
            tasks = [t for t in tasks if t["id"] != task_id]
            self._write_tasks(tasks)
            return {"status": "success", "message": "Task rejected"}

        @self.app.post("/agent/tasks/mock")
        async def mock_tasks():
            """Generate dummy tasks for testing"""
            import uuid
            
            # Find a local image if possible
            gallery_dir = Path(__file__).parent / "static" / "gallery"
            mock_image = None
            if gallery_dir.exists():
                images = list(gallery_dir.glob("*.png")) + list(gallery_dir.glob("*.jpg"))
                if images:
                    mock_image = f"/static/gallery/{images[0].name}"

            mocks = [
                {
                    "id": str(uuid.uuid4()),
                    "persona": self.state.cli.agent.name if self.state.cli.agent else "Daisy",
                    "type": "post",
                    "platform": "instagram",
                    "content": "Just had the most amazing morning! The sun is shining and everything feels perfect. ✨ #blessed #morningvibes",
                    "image_url": mock_image,
                    "status": "pending"
                },
                {
                    "id": str(uuid.uuid4()),
                    "persona": self.state.cli.agent.name if self.state.cli.agent else "Daisy",
                    "type": "dm",
                    "platform": "fanvue",
                    "content": "Hey babe! I just posted something special for you. Go check your inbox and let me know what you think! 😉",
                    "image_url": None,
                    "status": "pending",
                    "user_id": "fan_123",
                    "user_name": "João VIP"
                }
            ]
            
            tasks = self._read_tasks()
            tasks.extend(mocks)
            self._write_tasks(tasks)
            return {"status": "success", "added": len(mocks)}

        @self.app.get("/agent/memory/{persona_name}/{user_id}")
        async def get_memories(persona_name: str, user_id: str):
            """Get long-term memories for a specific user"""
            try:
                memories = await self.memory.get_user_memories(persona_name, user_id)
                return {"status": "success", "memories": memories}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agent/memory/add")
        async def add_memory(request: MemoryAddRequest):
            """Add a new fact to long-term memory"""
            try:
                memory_id = await self.memory.add_memory(
                    request.persona_name, 
                    request.user_id, 
                    request.fact
                )
                return {"status": "success", "memory_id": memory_id}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

def create_app():
    server = ZerePyServer()
    return server.app