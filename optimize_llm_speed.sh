#!/bin/bash
# Quick LLM Speed Optimization Script

echo "=========================================================================="
echo "LLM SPEED OPTIMIZATION"
echo "=========================================================================="
echo ""

# Check current setup
echo "📋 Current Configuration:"
echo "   Backend: $(grep LLM_BACKEND .env | cut -d'=' -f2)"
echo "   Model: $(grep LLM_MODEL .env | cut -d'=' -f2)"
echo ""

# Check if Ollama is being used
if grep -q "LLM_BACKEND=ollama" .env; then
    echo "🔍 Checking Ollama setup..."
    echo ""
    
    # Check if Ollama server is running
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama server is running (HTTP API available - FAST)"
    else
        echo "❌ Ollama server is NOT running (will use slow CLI)"
        echo ""
        echo "⚡ QUICK FIX: Start Ollama server"
        echo "   ollama serve &"
        echo ""
        read -p "Start Ollama server now? (y/n): " start_ollama
        if [ "$start_ollama" = "y" ]; then
            ollama serve > /dev/null 2>&1 &
            sleep 2
            echo "✅ Ollama server started"
        fi
    fi
    echo ""
    
    # Check current model
    current_model=$(grep LLM_MODEL .env | cut -d'=' -f2)
    echo "📦 Current model: $current_model"
    echo ""
    
    # Suggest faster models
    echo "💡 Faster model options:"
    echo "   1. phi           - Fastest, good quality (RECOMMENDED)"
    echo "   2. gemma:2b      - Fast, balanced"
    echo "   3. tinyllama     - Fastest, lower quality"
    echo "   4. mistral:7b-instruct-q4_0 - Quantized mistral (faster)"
    echo "   5. Keep current model"
    echo ""
    
    read -p "Choose option (1-5): " model_choice
    
    case $model_choice in
        1)
            new_model="phi"
            ;;
        2)
            new_model="gemma:2b"
            ;;
        3)
            new_model="tinyllama"
            ;;
        4)
            new_model="mistral:7b-instruct-q4_0"
            ;;
        *)
            new_model=""
            ;;
    esac
    
    if [ -n "$new_model" ]; then
        echo ""
        echo "📥 Installing $new_model..."
        ollama pull $new_model
        
        echo ""
        echo "✏️  Updating .env..."
        sed -i.bak "s/LLM_MODEL=.*/LLM_MODEL=$new_model/" .env
        
        echo "✅ Updated to $new_model"
    fi
    
    # Add optimization settings
    echo ""
    echo "⚙️  Adding optimization settings to .env..."
    
    if ! grep -q "LLM_MAX_TOKENS" .env; then
        echo "LLM_MAX_TOKENS=256" >> .env
        echo "✅ Added LLM_MAX_TOKENS=256"
    fi
    
    if ! grep -q "LLM_TEMPERATURE" .env; then
        echo "LLM_TEMPERATURE=0.1" >> .env
        echo "✅ Added LLM_TEMPERATURE=0.1"
    fi
    
    if ! grep -q "OLLAMA_KEEP_ALIVE" ~/.bashrc; then
        echo 'export OLLAMA_KEEP_ALIVE=3600' >> ~/.bashrc
        export OLLAMA_KEEP_ALIVE=3600
        echo "✅ Set OLLAMA_KEEP_ALIVE=3600 (keeps model in memory)"
    fi

else
    echo "ℹ️  Not using Ollama"
    echo ""
    echo "💡 For fastest speed, consider switching to Gemini:"
    echo "   1. Get free API key: https://makersuite.google.com/app/apikey"
    echo "   2. Update .env:"
    echo "      LLM_BACKEND=gemini"
    echo "      LLM_MODEL=gemini-2.0-flash-exp"
    echo "      LLM_API_KEY=your_api_key_here"
fi

echo ""
echo "=========================================================================="
echo "TESTING SPEED"
echo "=========================================================================="
echo ""

python3 test_llm_speed.py

echo ""
echo "=========================================================================="
echo "✅ OPTIMIZATION COMPLETE"
echo "=========================================================================="
echo ""
echo "📚 For more details, see: LLM_SPEED_OPTIMIZATION.md"
