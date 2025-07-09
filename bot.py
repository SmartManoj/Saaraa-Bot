import os
import asyncio
import logging
from io import BytesIO
import base64
import time
import subprocess
import re
from datetime import datetime, timedelta
from pymsgbox import prompt
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from litellm import completion
from PIL import Image
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())
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
                model="gemini/gemini-2.5-flash",
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
            return "Audio processing-la problem. Maybe try a shorter voice message?"

    async def send_with_markdown(self, update: Update, text: str):
        """Send message with markdown formatting, fallback to plain text if it fails."""
        try:
            logger.info(f"📤 Attempting to send message with markdown")
            await update.message.reply_text(text, parse_mode='Markdown')
            logger.info(f"✅ Message sent successfully")
        except Exception as e:
            logger.warning(f"⚠️ Markdown failed, sending plain text: {e}")
            # Fallback to plain text if markdown fails
            await update.message.reply_text(text)
            logger.info(f"✅ Plain text message sent successfully")

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
            
            result = response.choices[0].message.content or "No words to message."
            
            # Add response to conversation history
            self.add_to_conversation(user_id, "assistant", result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing {content_type} with Gemini: {e}")
            logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
            return f"Well, that didn't work. Error: {str(e)}"

    def extract_code_blocks(self, text: str) -> list:
        """Extract code blocks from markdown text."""
        # Pattern to match code blocks with optional language specifier
        # Updated to handle both newline and non-newline cases after language
        pattern = r'```(?:(\w+)\s*)?(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        code_blocks = []
        for language, code in matches:
            code = code.strip()
            if code:
                code_blocks.append({
                    'language': language.lower() if language else 'bash',
                    'code': code
                })
        
        return code_blocks

    async def execute_code_block(self, code_block: dict) -> str:
        """Execute a code block safely and return the result."""
        try:
            language = code_block['language']
            code = code_block['code']
            
            # Security check - only allow certain languages/commands
            if language not in ['bash', 'sh', 'python', 'py', 'javascript', 'js', 'node']:
                return f"❌ Language '{language}' not supported for execution"
            
            # Additional security - block dangerous commands
            dangerous_patterns = [
                r'rm\s+-rf',
                r'sudo',
                r'chmod\s+777',
                r'>/dev/null',
                r'&\s*$',
                r'shutdown',
                r'reboot',
                r'format',
                r'mkfs',
                r'dd\s+if=',
                r'curl.*\|.*bash',
                r'wget.*\|.*bash'
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    return f"❌ Potentially dangerous command detected: {pattern}"
            
            # Execute based on language
            if language in ['bash', 'sh']:
                # Execute bash commands
                process = await asyncio.create_subprocess_shell(
                    code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=os.getcwd()
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
                
                output = stdout.decode('utf-8', errors='replace')
                error = stderr.decode('utf-8', errors='replace')
                
                if process.returncode == 0:
                    return f"✅ *Executed successfully:*\n```shell\n{output}\n```" if output else "✅ *Executed successfully* (no output)"
                else:
                    return f"❌ *Execution failed:*\n```shell\n{error}\n```"
                    
            elif language in ['python', 'py']:
                # Execute Python code
                process = await asyncio.create_subprocess_exec(
                    'python', '-c', code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
                
                output = stdout.decode('utf-8', errors='replace')
                error = stderr.decode('utf-8', errors='replace')
                
                if process.returncode == 0:
                    return f"✅ *Python executed successfully:*\n```shell\n{output}\n```" if output else "✅ *Python executed successfully* (no output)"
                else:
                    return f"❌ *Python execution failed:*\n```shell\n{error}\n```"
                    
            elif language in ['javascript', 'js', 'node']:
                # Execute JavaScript/Node.js code
                process = await asyncio.create_subprocess_exec(
                    'node', '-e', code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
                
                output = stdout.decode('utf-8', errors='replace')
                error = stderr.decode('utf-8', errors='replace')
                
                if process.returncode == 0:
                    return f"✅ *Node.js executed successfully:*\n```shell\n{output}\n```" if output else "✅ *Node.js executed successfully* (no output)"
                else:
                    return f"❌ *Node.js execution failed:*\n```shell\n{error}\n```"
                    
        except asyncio.TimeoutError:
            return "❌ *Execution timed out* (30 second limit)"
        except Exception as e:
            return f"❌ *Execution error:* {str(e)}"

    async def handle_run_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle @SaraTheQueenBot run command in group chats."""
        try:
            message_text = update.message.text or update.message.caption or ""
            lower_message_text = message_text.lower()
            has_run_command = "run" in lower_message_text or 'test' in lower_message_text
            
            # Check if this is a mention with "run" command
            bot_username = context.bot.username
            if f"@{bot_username}" in message_text:
                if not has_run_command:
                    return await self.handle_message(update, context)
            else:
                return
            
            user = update.effective_user
            logger.info(f"🏃 Run command from {user.first_name} in chat {update.effective_chat.id}")
            
            # Show typing indicator
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            # Extract code blocks from reply message if available, otherwise from current message
            if update.message.reply_to_message:
                reply_text = update.message.reply_to_message.text_markdown_v2  or update.message.reply_to_message.caption or ""
                logger.info(f"🔍 Extracting code blocks from reply message: {reply_text}")
                code_blocks = self.extract_code_blocks(reply_text)
            else:
                logger.info(f"🔍 Extracting code blocks from current message: {message_text}")
                code_blocks = self.extract_code_blocks(message_text)
            
            if not code_blocks:
                await update.message.reply_text("No code blocks found to execute! Use ```bash or ```python format.")
                return
            
            confirmation = prompt("Are you sure you want to execute these code blocks? (y/n)")
            if confirmation.lower() != "y":
                await update.message.reply_text("Code execution cancelled!")
                return
            
            # Execute each code block
            results = []
            for i, code_block in enumerate(code_blocks):
                result = await self.execute_code_block(code_block)
                results.append(f"*Block {i+1} ({code_block['language']}):*\n{result}")
            
            # Send results
            final_result = "\n\n".join(results)
            
            # Split long messages
            if len(final_result) > 4000:
                parts = [final_result[i:i+4000] for i in range(0, len(final_result), 4000)]
                for part in parts:
                    await self.send_with_markdown(update, part)
            else:
                await self.send_with_markdown(update, final_result)
                
        except Exception as e:
            logger.error(f"Error handling run command: {e}")
            await update.message.reply_text(f"Error executing code: {str(e)}")

    def should_respond_in_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if bot should respond in group chat (only if mentioned or replying to bot)."""
        # Always respond in private chats
        if update.effective_chat.type == "private":
            return True
        
        # In group chats, only respond if:
        # 1. Bot is mentioned
        # 2. Message is a reply to bot's message
        
        bot_username = context.bot.username
        message_text = update.message.text or update.message.caption or ""
        
        # Check if bot is mentioned
        if f"@{bot_username}" in message_text:
            return True
        
        # Check if message is a reply to bot's message
        if update.message.reply_to_message:
            if update.message.reply_to_message.from_user.id == context.bot.id:
                # skip if the msg is intended for others users
                if not any( "mention" in entity.type and entity.offset == 0 for entity in (update.message.entities or [])):
                    return True
        
        return False
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unified message handler for all content types."""
        try:
            logger.info(f"🎯 HANDLE_MESSAGE CALLED!")
            
            user_id = update.effective_user.id
            user = update.effective_user
            
            # Check if we should respond in group chats
            if not self.should_respond_in_group(update, context):
                logger.info(f"🚫 Ignoring group message (not mentioned or reply)")
                return
            
            # Comprehensive logging
            logger.info(f"=== NEW MESSAGE FROM {user.first_name} ===")
            logger.info(f"Message has photo: {bool(update.message.photo)}")
            logger.info(f"Message has document: {bool(update.message.document)}")
            logger.info(f"Message has voice: {bool(update.message.voice)}")
            logger.info(f"Message has audio: {bool(update.message.audio)}")
            logger.info(f"Message has text: {bool(update.message.text)}")
            
            if update.message.text:
                logger.info(f"Text content: {update.message.text}")
            
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
                result = "That's not an image."
            
            else:
                logger.info("❓ No handler found for this message type")
            
            if result:
                logger.info(f"✅ Sending response: {result[:100]}...")
                await self.send_with_markdown(update, result)
            else:
                logger.warning("❌ No result generated for message")
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
            await update.message.reply_text(f"Something broke. {str(e)}")

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
        
        # Add run command handler for group chats (mentions with "run")
        application.add_handler(MessageHandler(filters.TEXT & filters.Entity("mention"), self.handle_run_command))
        
        # Main message handler - simplified to catch all messages
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_message))
        
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
