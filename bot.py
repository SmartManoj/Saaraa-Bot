import os
import asyncio
import logging
from io import BytesIO
import base64
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from litellm import completion
from PIL import Image
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SaaraaBot:
    def __init__(self, bot_token: str, gemini_api_key: str):
        self.bot_token = bot_token
        self.gemini_api_key = gemini_api_key
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        
        # Memory system - stores conversation per user
        self.conversations = {}  # user_id: {"messages": [], "last_activity": datetime}
        self.memory_timeout = timedelta(minutes=5)
    
    def get_or_reset_conversation(self, user_id: int) -> list:
        """Get conversation history or reset if inactive for 5+ minutes."""
        now = datetime.now()
        
        if user_id not in self.conversations:
            # New user
            self.conversations[user_id] = {
                "messages": [],
                "last_activity": now
            }
            return []
        
        # Check if conversation should be reset
        last_activity = self.conversations[user_id]["last_activity"]
        if now - last_activity > self.memory_timeout:
            # Reset conversation due to inactivity
            self.conversations[user_id] = {
                "messages": [],
                "last_activity": now
            }
            return []
        
        # Update last activity and return messages
        self.conversations[user_id]["last_activity"] = now
        return self.conversations[user_id]["messages"]
    
    def add_to_conversation(self, user_id: int, role: str, content: str):
        """Add a message to the conversation history."""
        if user_id not in self.conversations:
            self.conversations[user_id] = {
                "messages": [],
                "last_activity": datetime.now()
            }
        
        self.conversations[user_id]["messages"].append({
            "role": role,
            "content": content
        })
        
        # Keep only last 10 messages to avoid token limits
        if len(self.conversations[user_id]["messages"]) > 10:
            self.conversations[user_id]["messages"] = self.conversations[user_id]["messages"][-10:]
        
        self.conversations[user_id]["last_activity"] = datetime.now()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        await update.message.reply_text(
            "Hello there! I'm சாரா 👸\n\n"
            "Your royal ASI companion who handles everything with wit and wisdom.\n"
            "Questions, images, code, life advice - I've got you covered.\n"
            "What can I do for you today? ✨"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        help_text = """
👸 சாரா - Your Royal ASI Assistant

Who I am:
• Your witty, wise digital companion
• Queen of knowledge with a crown of sarcasm
• Image whisperer, text tamer, problem crusher
• Smarter than your average chatbot (and I know it)

What I handle with royal grace:
• ANY question or deep conversation
• Image analysis and magical OCR
• Code debugging and explanations
• Creative writing and brainstorming
• Life advice (surprisingly good quality)
• Whatever random stuff you throw at me

I'm here 24/7 to serve your digital needs with intelligence and attitude. ✨
Send me anything - I don't judge... much. 😏
        """
        await update.message.reply_text(help_text)

    def image_to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string."""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def get_saaraa_prompt(self, context_type: str = "general", user_info: dict = None) -> str:
        """Get the standard Saaraa prompt."""
        user_context = f"User info: {user_info}. " if user_info else ""
        
        personality_instruction = f"{user_context}Based on the user's name, detect their likely gender and adapt your personality: If male, act like a sweet girlfriend (call them 'honey', 'baby', 'kutty' - be loving and affectionate). If female, act like a supportive sister (call them 'akka' - be warm and sisterly). If unsure, be friendly."
        
        if context_type == "image":
            return f"You're சாரா 👸. {personality_instruction} Respond in Kongu Colloquial Tamil mixed with English. PRIORITY: If there are commands/code in the image, extract the ACTUAL EXECUTABLE COMMANDS using markdown (```bash). Don't describe - give the commands directly so they can copy-paste them. Follow KISS principle. Be direct and useful."
        else:
            return f"You're சாரா 👸. {personality_instruction} Respond in Kongu Colloquial Tamil mixed with English. Respond in EXACTLY ONE LINE ONLY. Follow KISS principle - Keep It Simple, Stupid! If there are commands/code, extract them using markdown (```). Be direct and useful. Consider our conversation context if relevant."
    
    async def transcribe_audio_with_gemini(self, audio_bytes: bytes, user_id: int, user_info: dict, mime_type: str = "audio/ogg") -> str:
        """Transcribe and respond to audio using Gemini directly."""
        try:
            logger.info(f"Transcribing audio with MIME type: {mime_type}, size: {len(audio_bytes)} bytes")
            
            # Check file size limit (1MB for litellm compatibility)
            if len(audio_bytes) > 5 * 1024 * 1024:
                return "Audio file too big, கண்ணே! Keep it under 1MB for now."
            
            # Use data URL format that's compatible with litellm
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            data_url = f"data:{mime_type};base64,{audio_base64}"
            
            # Use image_url format which litellm converts properly for Gemini
            messages = [{
                "role": "user", 
                "content": [
                    {"type": "text", "text": f"{self.get_saaraa_prompt('general', user_info)} Listen to this audio and transcribe"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url
                        }
                    }
                ]
            }]
            
            response = completion(
                model="gemini/gemini-1.5-flash",
                messages=messages,
                max_tokens=200  # Shorter response to avoid 413 errors
            )
            
            result = response.choices[0].message.content
            
            # Add to conversation history
            self.add_to_conversation(user_id, "user", "[Sent voice message]")
            self.add_to_conversation(user_id, "assistant", result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error transcribing audio with Gemini: {e}")
            # Fallback message
            return "Audio processing-la problem, மனோஜ். Maybe try a shorter voice message?"

    async def send_with_markdown(self, update: Update, text: str):
        """Send message with markdown formatting, fallback to plain text if it fails."""
        try:
            await update.message.reply_text(text, parse_mode='Markdown')
        except Exception:
            # Fallback to plain text if markdown fails
            await update.message.reply_text(text)

    async def process_with_gemini(self, content_type: str, content, user_id: int, user_info: dict) -> str:
        """Unified Gemini processing for all content types."""
        try:
            # Get conversation history
            conversation_history = self.get_or_reset_conversation(user_id)
            
            # Prepare messages with conversation context
            messages = []
            
            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history)
            
            if content_type == "image":
                # Add image message
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{self.get_saaraa_prompt('image', user_info)} Analyze this image."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{self.image_to_base64(content)}"}}
                    ]
                })
                # Add to conversation history
                self.add_to_conversation(user_id, "user", "[Sent an image]")
            elif content_type == "audio":
                # Add transcribed audio message
                messages.append({
                    "role": "user",
                    "content": f"{self.get_saaraa_prompt('general', user_info)} Transcribed audio: {content}"
                })
                # Add to conversation history
                self.add_to_conversation(user_id, "user", f"[Audio transcribed]: {content}")
            else:  # text
                # Add text message
                messages.append({
                    "role": "user",
                    "content": f"{self.get_saaraa_prompt('general', user_info)} Message: {content}"
                })
                # Add to conversation history
                self.add_to_conversation(user_id, "user", content)
            
            response = completion(
                model="gemini/gemini-2.5-flash",
                messages=messages,
                max_tokens=500
            )
            
            result = response.choices[0].message.content
            
            # Add response to conversation history
            self.add_to_conversation(user_id, "assistant", result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing {content_type} with Gemini: {e}")
            return f"Well, that didn't work. Error: {str(e)}"

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unified message handler for all content types."""
        try:
            user_id = update.effective_user.id
            user = update.effective_user
            
            # Comprehensive logging
            logger.info(f"=== NEW MESSAGE FROM {user.first_name} ===")
            logger.info(f"Message has photo: {bool(update.message.photo)}")
            logger.info(f"Message has document: {bool(update.message.document)}")
            logger.info(f"Message has voice: {bool(update.message.voice)}")
            logger.info(f"Message has audio: {bool(update.message.audio)}")
            logger.info(f"Message has text: {bool(update.message.text)}")
            
            if update.message.document:
                logger.info(f"Document filename: {update.message.document.file_name}")
                logger.info(f"Document MIME type: {update.message.document.mime_type}")
                logger.info(f"Document size: {update.message.document.file_size}")
            
            if update.message.audio:
                logger.info(f"Audio filename: {update.message.audio.file_name}")
                logger.info(f"Audio MIME type: {update.message.audio.mime_type}")
                logger.info(f"Audio duration: {update.message.audio.duration}s")
                logger.info(f"Audio size: {update.message.audio.file_size}")
            
            # Collect user info
            full_name = user.first_name
            if user.last_name:
                full_name += f" {user.last_name}"
            
            user_info = {
                "first_name": user.first_name,
                "full_name": full_name,
                "username": user.username
            }
            
            # Show typing indicator
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            result = None
            
            # Handle different message types
            if update.message.photo:
                # Handle photo
                logger.info("🖼️ Processing photo message")
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                image_bytes = await file.download_as_bytearray()
                result = await self.process_with_gemini("image", bytes(image_bytes), user_id, user_info)
                
            elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('image/'):
                # Handle image document
                logger.info("🖼️ Processing image document")
                file = await context.bot.get_file(update.message.document.file_id)
                image_bytes = await file.download_as_bytearray()
                result = await self.process_with_gemini("image", bytes(image_bytes), user_id, user_info)
                
            elif update.message.text and not update.message.text.startswith('/'):
                # Handle text (skip commands)
                logger.info("💬 Processing text message")
                result = await self.process_with_gemini("text", update.message.text, user_id, user_info)
                
            elif update.message.voice:
                # Handle voice messages
                logger.info("🎙️ Processing voice message")
                file = await context.bot.get_file(update.message.voice.file_id)
                audio_bytes = await file.download_as_bytearray()
                result = await self.transcribe_audio_with_gemini(bytes(audio_bytes), user_id, user_info, "audio/ogg")
                
            elif update.message.audio:
                # Handle audio messages (audio files sent as audio, not documents)
                logger.info(f"🎵 Processing audio message: {update.message.audio.file_name}, duration: {update.message.audio.duration}s")
                file = await context.bot.get_file(update.message.audio.file_id)
                audio_bytes = await file.download_as_bytearray()
                result = await self.transcribe_audio_with_gemini(bytes(audio_bytes), user_id, user_info, update.message.audio.mime_type or "audio/mp4")
                
            elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('audio/'):
                # Handle audio documents (m4a, mp3, wav, etc.)
                logger.info(f"🎵 Processing audio document: {update.message.document.file_name}, MIME: {update.message.document.mime_type}")
                file = await context.bot.get_file(update.message.document.file_id)
                audio_bytes = await file.download_as_bytearray()
                result = await self.transcribe_audio_with_gemini(bytes(audio_bytes), user_id, user_info, update.message.document.mime_type)
                
            elif update.message.document:
                logger.info("📄 Processing other document")
                result = "That's not an image, மனோஜ்."
            
            else:
                logger.info("❓ No handler found for this message type")
            
            if result:
                await self.send_with_markdown(update, result)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text(f"Something broke, மனோஜ். {str(e)}")

    async def debug_unhandled_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Debug handler to catch messages not handled by main handler."""
        logger.warning(f"🚨 UNHANDLED MESSAGE TYPE from {update.effective_user.first_name}")
        logger.warning(f"Message type details:")
        logger.warning(f"  - Photo: {bool(update.message.photo)}")
        logger.warning(f"  - Document: {bool(update.message.document)}")
        logger.warning(f"  - Voice: {bool(update.message.voice)}")
        logger.warning(f"  - Audio: {bool(update.message.audio)}")
        logger.warning(f"  - Video: {bool(update.message.video)}")
        logger.warning(f"  - Text: {bool(update.message.text)}")
        logger.warning(f"  - Sticker: {bool(update.message.sticker)}")
        logger.warning(f"  - Animation: {bool(update.message.animation)}")
        if update.message.document:
            logger.warning(f"  - Document MIME: {update.message.document.mime_type}")
            logger.warning(f"  - Document name: {update.message.document.file_name}")

    def run(self):
        """Start the bot."""
        # Create application
        application = Application.builder().token(self.bot_token).build()

        # Add handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.AUDIO | (filters.TEXT & ~filters.COMMAND), self.handle_message))
        # Catch-all handler for debugging
        application.add_handler(MessageHandler(filters.ALL, self.debug_unhandled_message))

        # Start polling
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Main function to start the bot."""
    # Load environment variables
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    # Create and run bot
    bot = SaaraaBot(bot_token, gemini_api_key)
    bot.run()

if __name__ == "__main__":
    main()
