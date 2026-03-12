# LLM Speed Optimization Guide

## Current Setup

- **Backend**: Ollama
- **Model**: Mistral
- **Speed Issues**: Using CLI fallback instead of HTTP API

## Quick Fixes for Faster LLM

### 1. ✅ Use Ollama HTTP API (FASTEST)

Make sure Ollama server is running:

```bash
# Check if Ollama server is running
curl http://localhost:11434/api/tags

# If not running, start it:
ollama serve &

# Or add to systemd to auto-start
```

**Why**: HTTP API keeps model in memory = 10x faster than CLI

### 2. ✅ Use Faster Model

Switch from `mistral` to a faster model in `.env`:

```bash
# Option A: Phi-2 (Much faster, good quality)
LLM_MODEL=phi

# Option B: TinyLlama (Fastest, lower quality)
LLM_MODEL=tinyllama

# Option C: Gemma 2B (Fast and good balance)
LLM_MODEL=gemma:2b

# Option D: Keep Mistral but use smaller variant
LLM_MODEL=mistral:7b-instruct-q4_0
```

Download the model:

```bash
ollama pull phi
# or
ollama pull gemma:2b
```

### 3. ✅ Reduce Token Limits

Your current code uses 512 max tokens. For simple intents, reduce it:

Add to `.env`:

```bash
LLM_MAX_TOKENS=256
LLM_TEMPERATURE=0.1
```

### 4. ✅ Enable Model Caching

Ollama keeps the model loaded for 5 minutes by default. Increase it:

```bash
# Keep model loaded for 1 hour
export OLLAMA_KEEP_ALIVE=3600

# Or add to ~/.bashrc
echo 'export OLLAMA_KEEP_ALIVE=3600' >> ~/.bashrc
```

### 5. ✅ Use GPU (If Available)

```bash
# Check if GPU is detected
ollama ps

# If NVIDIA GPU available
# Ollama should auto-detect and use CUDA

# Verify GPU usage
nvidia-smi  # Should show ollama process
```

### 6. ⚡ Switch to Gemini (RECOMMENDED FOR SPEED)

Gemini Flash is MUCH faster than local Ollama:

```bash
# In .env, switch to Gemini
LLM_BACKEND=gemini
LLM_MODEL=gemini-2.0-flash-exp
LLM_API_KEY=your_api_key_here
```

Get free API key: https://makersuite.google.com/app/apikey

**Speed comparison**:

- Ollama Mistral (CLI): ~5-10 seconds
- Ollama Mistral (HTTP): ~2-4 seconds
- Ollama Phi (HTTP): ~1-2 seconds
- Gemini Flash: ~0.5-1 second ✅

### 7. ✅ Add Response Streaming (Advanced)

For real-time responses, enable streaming in Ollama provider.

### 8. ✅ Optimize Prompts

Shorter prompts = faster responses:

**Current**:

```
[Long system prompt]
User message: [user input]
Respond with valid JSON only.
```

**Optimized**:

```json
{ "intent": "classify", "msg": "check my day" }
```

## Quick Setup Commands

### Option A: Optimize Ollama (Current Setup)

```bash
# 1. Start Ollama server
ollama serve &

# 2. Pull faster model
ollama pull phi

# 3. Update .env
cat >> .env << 'EOF'
LLM_BACKEND=ollama
LLM_MODEL=phi
LLM_MAX_TOKENS=256
EOF

# 4. Test speed
time python3 -c "from src.integrations.llm import build_llm_provider_from_env; llm = build_llm_provider_from_env(); print(llm.generate_json('Classify', 'check my day'))"
```

### Option B: Switch to Gemini (Fastest)

```bash
# 1. Get API key from https://makersuite.google.com/app/apikey

# 2. Update .env
cat >> .env << 'EOF'
LLM_BACKEND=gemini
LLM_MODEL=gemini-2.0-flash-exp
LLM_API_KEY=your_api_key_here
EOF

# 3. Test
python3 -c "from src.integrations.llm import build_llm_provider_from_env; llm = build_llm_provider_from_env(); print(llm.generate_json('Classify', 'check my day'))"
```

## Performance Benchmarks

| Setup                 | Response Time | Quality      |
| --------------------- | ------------- | ------------ |
| Ollama Mistral CLI    | 5-10s         | Excellent    |
| Ollama Mistral HTTP   | 2-4s          | Excellent    |
| Ollama Phi HTTP       | 1-2s          | Good         |
| Ollama TinyLlama HTTP | 0.5-1s        | Fair         |
| Gemini Flash API      | 0.5-1s        | Excellent ✅ |

## Recommended Setup

**For Best Speed + Quality**: Switch to Gemini Flash
**For Local/Privacy**: Use Ollama with Phi model and HTTP API

## Apply Changes Now

```bash
cd /home/misgun/LightClaw

# Ensure Ollama server is running
ollama serve > /dev/null 2>&1 &

# Pull faster model
ollama pull phi

# Backup current .env
cp .env .env.backup

# Update to use Phi model
sed -i 's/LLM_MODEL=mistral/LLM_MODEL=phi/' .env

# Test the speed
echo "Testing LLM speed..."
time python3 -c "
import sys
sys.path.insert(0, '.')
from src.integrations.llm import build_llm_provider_from_env
llm = build_llm_provider_from_env()
result = llm.generate_json('Classify this intent', 'check my calendar today')
print(result)
"
```

## Monitor Performance

```bash
# Check Ollama server status
curl http://localhost:11434/api/tags

# Check running models
ollama ps

# Check response time
time curl -X POST http://localhost:11434/api/generate -d '{
  "model": "phi",
  "prompt": "test",
  "stream": false
}'
```

## Troubleshooting

**Issue**: Ollama still slow

- **Fix**: Make sure `ollama serve` is running (not using CLI)

**Issue**: Model not found

- **Fix**: `ollama pull <model-name>`

**Issue**: Out of memory

- **Fix**: Use smaller model (tinyllama, phi) or reduce context

**Issue**: Want fastest possible

- **Fix**: Switch to Gemini Flash API
