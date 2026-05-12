document.addEventListener('DOMContentLoaded', () => {
    // State
    let currentTab = 'dashboard';
    let loadedAgent = null;
    let currentAgentConfig = null;
    let connections = {};
    let agents = [];
    let isAgentRunning = false;
    let tasks = [];
    let selectedTaskId = null;

    // Elements
    const tabItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const tabTitle = document.getElementById('tab-title');
    const terminal = document.getElementById('terminal');
    const startLoopBtn = document.getElementById('start-loop-btn');
    const stopLoopBtn = document.getElementById('stop-loop-btn');
    const loadAgentBtn = document.getElementById('load-agent-btn');
    const personaDropdown = document.getElementById('persona-dropdown');
    const connectionsList = document.getElementById('connections-list');
    const clearTerminalBtn = document.getElementById('clear-terminal');
    
    // Chat Elements
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendChatBtn = document.getElementById('send-chat-btn');
    
    // Inbox Elements
    const taskList = document.getElementById('task-list');
    const generateMocksBtn = document.getElementById('generate-mocks-btn');
    const taskDetailContent = document.getElementById('task-detail-content');
    const emptyDetailState = document.querySelector('.empty-detail-state');
    const platformBadge = document.getElementById('detail-platform-badge');
    const typeBadge = document.getElementById('detail-type-badge');
    const detailPersonaName = document.getElementById('detail-persona-name');
    const detailImageContainer = document.getElementById('detail-image-container');
    const detailImage = document.getElementById('detail-image');
    const taskContentEditor = document.getElementById('task-content-editor');
    const approveTaskBtn = document.getElementById('approve-task-btn');
    const rejectTaskBtn = document.getElementById('reject-task-btn');

    const configModal = document.getElementById('config-modal');
    const closeModalBtn = document.querySelector('.close-modal');
    const configForm = document.getElementById('config-form');
    const configFields = document.getElementById('config-fields');
    const personaForm = document.getElementById('persona-form');
    const personaName = document.getElementById('persona-name');
    const personaBio = document.getElementById('persona-bio');
    const personaTraits = document.getElementById('persona-traits');
    const personaVisual = document.getElementById('persona-visual');
    const personasList = document.getElementById('personas-list');
    const createPersonaBtn = document.getElementById('create-persona-btn');
    
    // New: Integrations Elements
    const enableTwitter = document.getElementById('enable-twitter');
    const twitterSettings = document.getElementById('twitter-settings');
    const twitterReadCount = document.getElementById('twitter-read-count');
    const twitterInterval = document.getElementById('twitter-interval');
    const enableInstagram = document.getElementById('enable-instagram');
    const enableFanvue = document.getElementById('enable-fanvue');
    const personaModelProvider = document.getElementById('persona-model-provider');
    const personaModelName = document.getElementById('persona-model-name');

    // Gallery Elements (Studio)
    const imageGenForm = document.getElementById('image-gen-form');
    const imagePromptInput = document.getElementById('image-prompt');
    const genStyle = document.getElementById('gen-style');
    const genSeed = document.getElementById('gen-seed');
    const randomizeSeedBtn = document.getElementById('randomize-seed');
    const galleryGrid = document.getElementById('gallery-grid');
    const galleryStatus = document.getElementById('gallery-status');
    const generateBtn = document.getElementById('generate-btn');
    const mainOutput = document.getElementById('main-output');

    // Tab Switching
    tabItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tab = item.getAttribute('data-tab');
            switchTab(tab);
        });
    });

    // Toggle logic for Twitter
    enableTwitter.addEventListener('change', () => {
        if (enableTwitter.checked) {
            twitterSettings.classList.remove('hidden');
        } else {
            twitterSettings.classList.add('hidden');
        }
    });

    function switchTab(tab) {
        tabItems.forEach(i => i.classList.remove('active'));
        tabPanes.forEach(p => p.classList.remove('active'));
        
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
        document.getElementById(tab).classList.add('active');
        
        tabTitle.textContent = tab.charAt(0).toUpperCase() + tab.slice(1);
        currentTab = tab;

        if (tab === 'connections') fetchConnections();
        if (tab === 'personas') fetchPersonas();
        if (tab === 'gallery') initGallery();
        if (tab === 'inbox') fetchTasks();
    }

    // Terminal Helper
    function logToTerminal(message, type = 'system') {
        const line = document.createElement('div');
        line.className = `terminal-line ${type}`;
        const time = new Date().toLocaleTimeString([], { hour12: false });
        line.textContent = `[${time}] ${message}`;
        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;
    }

    // API Calls
    async function apiRequest(endpoint, method = 'GET', body = null) {
        try {
            const options = {
                method,
                headers: { 'Content-Type': 'application/json' }
            };
            if (body) options.body = JSON.stringify(body);
            
            const response = await fetch(endpoint, options);
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.detail || 'API Error');
            return data;
        } catch (error) {
            logToTerminal(error.message, 'error');
            console.error(error);
            return null;
        }
    }

    async function fetchStatus() {
        const data = await apiRequest('/');
        if (data) {
            loadedAgent = data.agent;
            isAgentRunning = data.agent_running;
            updateControls();
            
            if (loadedAgent) {
                document.getElementById('stat-model').textContent = loadedAgent;
                document.getElementById('stat-status').textContent = isAgentRunning ? 'Running' : 'Loaded';
                fetchConnections();
            }
        }
    }

    async function fetchPersonas() {
        const data = await apiRequest('/agents');
        if (data) {
            agents = data.agents;
            renderPersonas();
            
            // Update dropdown
            const currentVal = personaDropdown.value;
            personaDropdown.innerHTML = '<option value="">Select Persona</option>';
            agents.forEach(agent => {
                const opt = document.createElement('option');
                opt.value = agent;
                opt.textContent = agent;
                personaDropdown.appendChild(opt);
            });
            
            if (currentVal && agents.includes(currentVal)) {
                personaDropdown.value = currentVal;
            } else if (!currentVal && agents.length > 0 && !loadedAgent) {
                personaDropdown.value = agents[0];
            }
        }
    }

    async function fetchConnections() {
        if (!loadedAgent) {
            connectionsList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-user-slash"></i>
                    <p>Please load a persona to view and manage connections.</p>
                </div>
            `;
            return;
        }
        const data = await apiRequest('/connections');
        if (data) {
            connections = data.connections;
            renderConnections();
            
            // Update stats
            const configuredCount = Object.values(connections).filter(c => c.configured).length;
            document.getElementById('stat-connections').textContent = configuredCount;

            // Populate Model Providers dropdown
            const currentProvider = personaModelProvider.value;
            personaModelProvider.innerHTML = '<option value="">Select Provider...</option>';
            
            Object.entries(connections).forEach(([name, info]) => {
                if (info.is_llm_provider) {
                    const opt = document.createElement('option');
                    opt.value = name;
                    opt.textContent = name.charAt(0).toUpperCase() + name.slice(1);
                    personaModelProvider.appendChild(opt);
                }
            });
            if (currentProvider && Array.from(personaModelProvider.options).some(o => o.value === currentProvider)) {
                personaModelProvider.value = currentProvider;
            }
        }
    }

    async function fetchTasks() {
        const data = await apiRequest('/agent/tasks');
        if (data) {
            tasks = data;
            renderTasks();
        }
    }

    function renderTasks() {
        taskList.innerHTML = '';
        if (tasks.length === 0) {
            taskList.innerHTML = '<div class="empty-list-message">No pending tasks.</div>';
            return;
        }

        tasks.forEach(task => {
            const item = document.createElement('div');
            item.className = `task-item ${selectedTaskId === task.id ? 'active' : ''}`;
            item.innerHTML = `
                <div class="task-item-header">
                    <span class="task-item-platform">${task.platform}</span>
                    <span class="task-item-type">${task.type}</span>
                </div>
                <div class="task-item-content">${task.content}</div>
            `;
            item.onclick = () => showTaskDetail(task.id);
            taskList.appendChild(item);
        });
    }

    function showTaskDetail(taskId) {
        selectedTaskId = taskId;
        const task = tasks.find(t => t.id === taskId);
        if (!task) return;

        // Update list active state
        renderTasks();

        // Populate detail view
        platformBadge.textContent = task.platform;
        typeBadge.textContent = task.type;
        detailPersonaName.textContent = task.persona;
        taskContentEditor.value = task.content;

        if (task.image_url) {
            detailImage.src = task.image_url;
            detailImageContainer.classList.remove('hidden');
        } else {
            detailImageContainer.classList.add('hidden');
        }

        emptyDetailState.classList.add('hidden');
        taskDetailContent.classList.remove('hidden');
    }

    async function loadAgentConfig(name) {
        const targetName = name || loadedAgent;
        if (!targetName) return;
        
        logToTerminal(`Fetching configuration for ${targetName}...`);
        const data = await apiRequest(`/agents/${targetName}/config`);
        if (data) {
            currentAgentConfig = data;
            personaName.value = data.name || targetName;
            personaBio.value = Array.isArray(data.bio) ? data.bio.join('\n') : (data.bio || '');
            personaTraits.value = Array.isArray(data.traits) ? data.traits.join(', ') : (data.traits || '');
            personaVisual.value = data.visual_prompt_base || '';
            
            // Populate Integrations
            const config = data.config || [];
            
            // Twitter
            const twitterCfg = config.find(c => c.name === 'twitter');
            if (twitterCfg) {
                enableTwitter.checked = true;
                twitterSettings.classList.remove('hidden');
                twitterReadCount.value = twitterCfg.timeline_read_count || 10;
                twitterInterval.value = twitterCfg.tweet_interval || 5400;
            } else {
                enableTwitter.checked = false;
                twitterSettings.classList.add('hidden');
            }
            
            // Mock ones
            enableInstagram.checked = config.some(c => c.name === 'instagram');
            enableFanvue.checked = config.some(c => c.name === 'fanvue');
            
            // AI Model
            const llmProviders = ['openai', 'anthropic', 'nvidia-nim', 'groq', 'xai', 'together', 'hyperbolic', 'galadriel', 'eternalai', 'ollama'];
            const activeLLM = config.find(c => llmProviders.includes(c.name));
            
            if (activeLLM) {
                personaModelProvider.value = activeLLM.name;
                personaModelName.value = activeLLM.model || '';
            }
            
            logToTerminal(`Configuration for ${targetName} loaded.`, "success");
        }
    }

    // Renderers
    function renderPersonas() {
        personasList.innerHTML = '';
        agents.forEach(agent => {
            const item = document.createElement('div');
            item.className = `persona-item ${loadedAgent === agent ? 'active-persona' : ''}`;
            item.innerHTML = `
                <div class="persona-item-header">
                    <i class="fas fa-user-astronaut"></i>
                    <span class="persona-item-name">${agent}</span>
                    ${loadedAgent === agent ? '<span class="badge badge-configured">Active</span>' : ''}
                </div>
                <div class="persona-item-actions">
                    <button class="btn btn-primary btn-sm activate-persona" data-persona="${agent}">
                        ${loadedAgent === agent ? 'Active' : 'Activate'}
                    </button>
                    <button class="btn btn-icon edit-persona" data-persona="${agent}">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            `;
            
            item.onclick = (e) => {
                if (e.target.closest('.activate-persona')) return;
                loadAgentConfig(agent);
            };
            
            personasList.appendChild(item);
        });

        document.querySelectorAll('.activate-persona').forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                const name = btn.getAttribute('data-persona');
                loadAgent(name);
            };
        });
    }

    function renderConnections() {
        connectionsList.innerHTML = '';
        
        const categories = {
            ai: { title: 'AI Brains & Image Generators', icon: 'fa-brain', connections: [] },
            social: { title: 'Social Platforms', icon: 'fa-share-nodes', connections: [] },
            crypto: { title: 'Web3 & Crypto (Advanced)', icon: 'fa-link', connections: [] }
        };

        const aiConns = ['openai', 'anthropic', 'ollama', 'groq', 'hyperbolic', 'galadriel', 'eternalai', 'xai', 'together', 'nvidia-nim', 'gemini_vision', 'comfy_api'];
        const socialConns = ['twitter', 'farcaster', 'discord', 'instagram', 'fanvue'];

        Object.entries(connections).forEach(([name, status]) => {
            if (aiConns.includes(name)) categories.ai.connections.push({ name, status });
            else if (socialConns.includes(name)) categories.social.connections.push({ name, status });
            else categories.crypto.connections.push({ name, status });
        });

        Object.entries(categories).forEach(([key, cat]) => {
            if (cat.connections.length === 0) return;

            const section = document.createElement('div');
            section.className = `conn-section ${key === 'crypto' ? 'conn-section-advanced' : ''}`;
            
            section.innerHTML = `
                <div class="section-header">
                    <i class="fas ${cat.icon}"></i>
                    <span>${cat.title}</span>
                </div>
                <div class="connections-grid"></div>
            `;
            
            const grid = section.querySelector('.connections-grid');
            
            cat.connections.forEach(({ name, status }) => {
                const card = document.createElement('div');
                card.className = 'conn-card';
                card.innerHTML = `
                    <div class="conn-header">
                        <span class="conn-name">${name}</span>
                        <span class="badge ${status.configured ? 'badge-configured' : 'badge-pending'}">
                            ${status.configured ? 'Configured' : 'Pending'}
                        </span>
                    </div>
                    <div class="conn-footer">
                        <button class="btn btn-icon btn-sm configure-btn" data-conn="${name}">
                            <i class="fas fa-cog"></i> Configure
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });
            
            connectionsList.appendChild(section);
        });

        document.querySelectorAll('.configure-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const connName = btn.getAttribute('data-conn');
                openConfigModal(connName);
            });
        });
    }

    // Actions
    async function loadAgent(name) {
        logToTerminal(`Loading agent: ${name}...`);
        const data = await apiRequest(`/agents/${name}/load`, 'POST');
        if (data) {
            logToTerminal(`Successfully loaded agent: ${name}`, 'success');
            fetchStatus();
            fetchConnections();
        }
    }

    async function startLoop() {
        const data = await apiRequest('/agent/start', 'POST');
        if (data) {
            logToTerminal('Agent loop started', 'success');
            isAgentRunning = true;
            updateControls();
        }
    }

    async function stopLoop() {
        const data = await apiRequest('/agent/stop', 'POST');
        if (data) {
            logToTerminal('Agent loop stopped', 'system');
            isAgentRunning = false;
            updateControls();
        }
    }

    function updateControls() {
        startLoopBtn.disabled = isAgentRunning || !loadedAgent;
        stopLoopBtn.disabled = !isAgentRunning;
        loadAgentBtn.disabled = isAgentRunning;
        
        if (loadedAgent) {
            personaDropdown.value = loadedAgent;
        }
    }

    // Chat
    async function sendMessage() {
        const msg = chatInput.value.trim();
        if (!msg || !loadedAgent) return;

        // Add user message
        addChatMessage(msg, 'user');
        chatInput.value = '';

        const data = await apiRequest('/agent/chat', 'POST', { message: msg });
        if (data) {
            addChatMessage(data.response, 'assistant');
        }
    }

    function addChatMessage(text, role) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        msgDiv.innerHTML = `<div class="message-bubble">${text}</div>`;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Modal logic
    function openConfigModal(connName) {
        const modalTitle = document.getElementById('modal-title');
        modalTitle.textContent = `Configure ${connName.charAt(0).toUpperCase() + connName.slice(1)}`;
        configModal.setAttribute('data-conn', connName);
        
        configFields.innerHTML = '';
        
        const createField = (label, id, type = 'text', placeholder = '') => {
            const group = document.createElement('div');
            group.className = 'form-group';
            group.innerHTML = `
                <label for="field-${id}">${label}</label>
                <input type="${type}" id="field-${id}" data-key="${id}" class="form-input" placeholder="${placeholder}">
            `;
            return group;
        };

        if (['openai', 'anthropic', 'groq', 'xai', 'together', 'nvidia-nim', 'hyperbolic', 'galadriel'].includes(connName)) {
            configFields.appendChild(createField('API Key', 'api_key', 'password', 'sk-...'));
        } else if (connName === 'twitter') {
            configFields.appendChild(createField('API Key', 'api_key'));
            configFields.appendChild(createField('API Secret', 'api_key_secret', 'password'));
            configFields.appendChild(createField('Access Token', 'access_token'));
            configFields.appendChild(createField('Access Token Secret', 'access_token_secret', 'password'));
        } else if (connName === 'discord') {
            configFields.appendChild(createField('Bot Token', 'bot_token', 'password'));
            configFields.appendChild(createField('Guild ID', 'guild_id'));
        } else if (connName === 'solana') {
            configFields.appendChild(createField('RPC URL', 'rpc_url', 'text', 'https://api.mainnet-beta.solana.com'));
            configFields.appendChild(createField('Private Key (Optional)', 'private_key', 'password'));
        } else if (connName === 'gemini_vision') {
            configFields.appendChild(createField('Gemini API Key', 'api_key', 'password', 'Enter API Key from Google AI Studio'));
        } else if (connName === 'comfy_api') {
            configFields.appendChild(createField('Server URL (Colab/Remote)', 'api_url', 'text', 'https://your-comfy-tunnel.cloudflare.com'));
        } else {
            // Default fallback: JSON textarea for unknown connections
            const fieldGroup = document.createElement('div');
            fieldGroup.className = 'form-group';
            fieldGroup.innerHTML = `
                <label>Configuration (JSON)</label>
                <textarea id="field-json" data-type="json" class="form-input" style="height:120px;" placeholder='{"key": "value"}'></textarea>
            `;
            configFields.appendChild(fieldGroup);
        }
        
        configModal.style.display = 'flex';
    }

    closeModalBtn.onclick = () => configModal.style.display = 'none';
    window.onclick = (e) => { if (e.target == configModal) configModal.style.display = 'none'; };

    configForm.onsubmit = async (e) => {
        e.preventDefault();
        const connName = configModal.getAttribute('data-conn');
        const params = {};
        
        const inputs = configFields.querySelectorAll('input, textarea');
        let hasError = false;

        inputs.forEach(input => {
            if (input.getAttribute('data-type') === 'json') {
                try {
                    Object.assign(params, JSON.parse(input.value));
                } catch (e) {
                    logToTerminal('Invalid JSON in configuration', 'error');
                    hasError = true;
                }
            } else {
                const key = input.getAttribute('data-key');
                params[key] = input.value;
            }
        });

        if (hasError) return;

        logToTerminal(`Configuring ${connName}...`);
        const data = await apiRequest(`/connections/${connName}/configure`, 'POST', {
            connection: connName,
            params: params
        });
        
        if (data) {
            logToTerminal(`${connName} configured successfully`, 'success');
            configModal.style.display = 'none';
            fetchConnections();
        }
    };

    // Event Listeners
    loadAgentBtn.onclick = () => {
        if (personaDropdown.value) {
            loadAgent(personaDropdown.value);
        } else {
            alert('Please select a persona first.');
            logToTerminal('Load failed: No persona selected', 'error');
        }
    };

    createPersonaBtn.onclick = () => {
        currentAgentConfig = {};
        personaForm.reset();
        personaName.value = "";
        personaBio.value = "";
        personaTraits.value = "";
        personaVisual.value = "";
        personaName.focus();
        logToTerminal("Started creating new persona.");
    };
    startLoopBtn.onclick = startLoop;
    stopLoopBtn.onclick = stopLoop;

    // Inbox Handlers
    generateMocksBtn.onclick = async () => {
        const data = await apiRequest('/agent/tasks/mock', 'POST');
        if (data) {
            logToTerminal(`Generated ${data.added} mock tasks.`, 'success');
            fetchTasks();
        }
    };

    approveTaskBtn.onclick = async () => {
        if (!selectedTaskId) return;
        const content = taskContentEditor.value;
        const data = await apiRequest(`/agent/tasks/${selectedTaskId}/approve`, 'POST', { content });
        if (data) {
            logToTerminal('Task approved and "published".', 'success');
            selectedTaskId = null;
            taskDetailContent.classList.add('hidden');
            emptyDetailState.classList.remove('hidden');
            fetchTasks();
        }
    };

    rejectTaskBtn.onclick = async () => {
        if (!selectedTaskId) return;
        const data = await apiRequest(`/agent/tasks/${selectedTaskId}/reject`, 'POST');
        if (data) {
            logToTerminal('Task rejected.', 'system');
            selectedTaskId = null;
            taskDetailContent.classList.add('hidden');
            emptyDetailState.classList.remove('hidden');
            fetchTasks();
        }
    };

    sendChatBtn.onclick = sendMessage;
    chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };

    document.getElementById('clear-terminal').onclick = () => terminal.innerHTML = '';

    personaForm.onsubmit = async (e) => {
        e.preventDefault();
        
        if (!loadedAgent) {
            logToTerminal("Cannot save: No agent loaded.", "error");
            return;
        }

        const payload = {
            ...currentAgentConfig,
            name: personaName.value,
            bio: personaBio.value.split('\n').filter(line => line.trim() !== ''),
            traits: personaTraits.value.split(',').map(t => t.trim()).filter(t => t !== ''),
            visual_prompt_base: personaVisual.value,
            config: [] // Reconstruct config
        };

        // Reconstruct Config Array
        // Add selected LLM Provider
        if (personaModelProvider.value) {
            const llmConfig = {
                "name": personaModelProvider.value,
                "model": personaModelName.value
            };
            
            // Add other specific fields if they existed
            if (currentAgentConfig && currentAgentConfig.config) {
                const existing = currentAgentConfig.config.find(c => c.name === personaModelProvider.value);
                if (existing) {
                    Object.assign(llmConfig, existing);
                    llmConfig.model = personaModelName.value; // ensure model is updated
                }
            }
            
            payload.config.push(llmConfig);
        }

        // Add Twitter if enabled
        if (enableTwitter.checked) {
            payload.config.push({
                "name": "twitter",
                "timeline_read_count": parseInt(twitterReadCount.value),
                "own_tweet_replies_count": 2, // default
                "tweet_interval": parseInt(twitterInterval.value)
            });
        }

        // Add mocks if enabled
        if (enableInstagram.checked) {
            payload.config.push({ "name": "instagram" });
        }
        if (enableFanvue.checked) {
            payload.config.push({ "name": "fanvue" });
        }

        // Keep other existing configs (e.g. solana, discord) that we're not managing yet
        if (currentAgentConfig && currentAgentConfig.config) {
            const managedNames = ['openai', 'anthropic', 'twitter', 'instagram', 'fanvue'];
            currentAgentConfig.config.forEach(c => {
                if (!managedNames.includes(c.name)) {
                    payload.config.push(c);
                }
            });
        }

        logToTerminal(`Saving persona for ${payload.name}...`);
        const data = await apiRequest('/agent/save', 'POST', payload);
        if (data) {
            logToTerminal(`Persona for ${payload.name} saved successfully!`, 'success');
            fetchPersonas();
            if (payload.name === loadedAgent) {
                fetchStatus();
            }
        } else {
            logToTerminal(`Failed to save persona for ${payload.name}`, 'error');
        }
    };

    // Gallery Logic
    async function initGallery() {
        // Load saved values
        const savedMethod = localStorage.getItem('gen_method') || 'gemini';
        genMethodSelect.value = savedMethod;

        // Fetch existing images
        const data = await apiRequest('/agent/gallery_images');
        if (data && data.images) {
            galleryGrid.innerHTML = '';
            data.images.forEach(img => {
                addGalleryItem(img.url, img.name);
            });
        }
    }

    // No longer needed, using radio buttons

    randomizeSeedBtn.onclick = () => {
        const newSeed = Math.floor(Math.random() * 1000000000);
        genSeed.value = newSeed;
    };
    
    // Call initGallery early
    initGallery();

    imageGenForm.onsubmit = async (e) => {
        e.preventDefault();
        
        if (!loadedAgent) {
            alert('Please load a persona first to provide visual context.');
            return;
        }

        const method = document.querySelector('input[name="method"]:checked').value;
        const prompt = imagePromptInput.value.trim();
        const aspectRatio = document.querySelector('input[name="aspect_ratio"]:checked').value;
        const style = genStyle.value;
        let seed = parseInt(genSeed.value);

        if (!prompt) {
            alert('Please provide a situational prompt.');
            return;
        }

        if (isNaN(seed) || seed === -1) {
            seed = null;
        }

        galleryStatus.classList.remove('hidden');
        mainOutput.classList.add('hidden');
        generateBtn.disabled = true;

        logToTerminal(`Generating via ${method}...`, 'info');

        const data = await apiRequest('/agent/generate_image', 'POST', {
            method: method,
            persona_name: loadedAgent,
            prompt: prompt,
            aspect_ratio: aspectRatio,
            seed: seed,
            style_preset: style,
            quality: 'Standard'
        });

        galleryStatus.classList.add('hidden');
        mainOutput.classList.remove('hidden');
        generateBtn.disabled = false;

        if (data && data.status === 'success') {
            logToTerminal(`Image generated successfully!`, 'success');
            renderMainOutput(data.image_url, data.prompt);
            addGalleryItem(data.image_url, data.prompt);
        } else {
            logToTerminal('Generation failed. Check Connections (API Key/URL).', 'error');
        }
    };

    function renderMainOutput(url, prompt) {
        mainOutput.innerHTML = `
            <div class="studio-main-preview">
                <img src="${url}" alt="Preview">
                <div class="studio-preview-actions">
                    <button class="btn btn-primary" onclick="sendToInbox('${url}', '${prompt.replace(/'/g, "\\'")}')">
                        <i class="fas fa-paper-plane"></i> Send to Inbox
                    </button>
                    <a href="${url}" target="_blank" class="btn btn-secondary">
                        <i class="fas fa-download"></i> Download
                    </a>
                </div>
            </div>
        `;
    }

    // Expose to window for onclick
    window.sendToInbox = async (url, prompt) => {
        logToTerminal('Sending creation to Inbox...');
        const data = await apiRequest('/agent/tasks/create', 'POST', {
            persona: loadedAgent || 'Daisy',
            content: `New studio creation: ${prompt}`,
            image_url: url
        });
        if (data) {
            logToTerminal('Studio creation sent to Inbox tasks!', 'success');
        }
    };

    function addGalleryItem(url, prompt) {
        const item = document.createElement('div');
        item.className = 'studio-item';
        item.innerHTML = `
            <img src="${url}" alt="History Item" loading="lazy">
            <div class="studio-item-actions">
                <button class="btn btn-icon btn-sm" onclick="renderMainOutput('${url}', '${prompt.replace(/'/g, "\\'")}')">
                    <i class="fas fa-eye"></i>
                </button>
            </div>
        `;
        
        if (galleryGrid.firstChild) {
            galleryGrid.insertBefore(item, galleryGrid.firstChild);
        } else {
            galleryGrid.appendChild(item);
        }
    }

    // Init
    fetchStatus();
    fetchPersonas();
    fetchConnections();
    
    // Polling for status
    setInterval(fetchStatus, 5000);
});
