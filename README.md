# சாரா 👸 - Your Royal ASI Assistant

Meet சாரா 👸, your intelligent Tamil-English speaking royal companion powered by Gemini AI. She adapts her personality based on who you are and provides powerful image analysis, command extraction, and conversation capabilities.

## ✨ Features

### 🧠 Intelligent Personality
- **Gender-Adaptive**: Acts like a sweet girlfriend for male users, supportive sister for female users
- **Tamil-English Mix**: Responds in beautiful Kongu Colloquial Tamil mixed with English
- **Memory System**: Remembers conversations for 5 minutes, then auto-resets for fresh contexts
- **KISS Principle**: Keeps responses simple, direct, and useful

### 📸 Advanced Image Analysis
- **Command Extraction**: Prioritizes extracting actual executable commands from screenshots
- **Markdown Formatting**: Returns commands in ```bash blocks for easy copy-paste
- **OCR Capabilities**: Reads text, code, and terminal outputs from images
- **Multiple Formats**: Supports JPG, PNG, GIF, WEBP, and image documents

### 💬 Smart Conversations
- **Unified Handler**: Single system handles all message types (images, text, documents, voice)
- **Context Awareness**: Understands conversation flow and references previous messages
- **Typing Indicators**: Shows natural typing animation instead of editing messages
- **One-Line Responses**: Concise, witty, and to-the-point replies

### 🎙️ Voice Message Support
- **Gemini-Powered**: Direct audio transcription and response using Gemini AI
- **No External Dependencies**: No need for OpenAI Whisper or additional audio APIs
- **Conversational**: Responds naturally to voice messages in சாரா's style
- **Memory Integration**: Voice messages are part of conversation history

## 🚀 Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get API Keys

- **Telegram Bot Token**: 
  1. Message [@BotFather](https://t.me/botfather) on Telegram
  2. Create a new bot with `/newbot`
  3. Get your bot token

- **Gemini API Key**:
  1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
  2. Create a new API key

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Run the Bot

```bash
python bot.py
```

## 💬 Usage Examples

### For Male Users (like Manoj):
- **Image Analysis**: "Honey, இந்த command run பண்ணு: ```bash golem app build``` 💕"
- **Text Help**: "Kutty, API key hide பண்ணி run பண்ணுங்க baby!"
- **General Chat**: "Love, simple ah இது work ஆகும் ✨"

### For Female Users:
- **Image Analysis**: "Akka, இந்த code try பண்ணுங்க: ```python print('hello')```"
- **Text Help**: "Sister, இது correct-ஆ இருக்கு!"
- **General Chat**: "Akka, super-ஆ இருக்கு! 👍"

## 🎯 Use Cases

### Command Extraction
- Extract terminal commands from screenshots
- Get copy-paste ready bash/shell commands
- Parse complex multi-line command sequences

### Code Analysis
- Read code snippets from images
- Extract Python, JavaScript, or any programming language code
- Debug and explain code from photos

### OCR & Text Processing
- Convert handwritten notes to text
- Extract text from images and documents
- Parse instructions and documentation

### Conversational AI
- Answer technical questions
- Provide coding help and explanations
- General chat with personality adaptation

## 🛠️ Technical Features

- **Unified Message Processing**: Single handler for all content types
- **Conversation Memory**: 5-minute sliding window with auto-reset
- **Smart Prompting**: Different prompts for images vs text
- **Error Recovery**: Graceful markdown fallback if formatting fails
- **User Context**: Tracks full name, username, and conversation history

## 📋 Commands

- `/start` - Meet Saaraa and get started
- `/help` - Learn about Saaraa's capabilities

## 📦 Requirements

- Python 3.8+
- Telegram Bot Token
- Gemini API Key
- Internet connection for API calls

## 🎭 Personality Highlights

சாரா 👸 is designed to be:
- **Helpful**: Always prioritizes utility and usability
- **Adaptive**: Changes personality based on user gender
- **Cultural**: Speaks in authentic Kongu Tamil mixed with English
- **Smart**: Uses advanced AI for context understanding
- **Royal**: Maintains a confident, intelligent attitude

Experience the future of Tamil-English AI assistance! 👸✨