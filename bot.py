import os
import json
import logging
import asyncio
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import nextcord
from nextcord.ext import commands
from nextcord import Intents
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer, errors as kafka_errors
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
KAFKA_BROKER = os.getenv('KAFKA_BROKER')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
HUGGINGFACE_MODEL = os.getenv('HUGGINGFACE_MODEL')

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class SimpleDiscordKafkaService:
    def __init__(self, discord_token, channel_id, huggingface_model=HUGGINGFACE_MODEL):
        self.bot = commands.Bot(command_prefix='!', intents=Intents.all(), help_command=None)
        self.discord_token = discord_token
        self.channel_id = channel_id
        self.huggingface_model = huggingface_model

        # Kafka Producer and Consumer setup
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda m: json.dumps(m).encode('utf-8'),
            enable_idempotence=True,
            acks='all',
            retry_backoff_ms=500
        )
        self.consumer = AIOKafkaConsumer(
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='discord_history_consumer'
        )
        logger.info("Kafka producer and consumer configured")

        # Load model and tokenizer from Hugging Face Hub
        self.tokenizer = AutoTokenizer.from_pretrained(self.huggingface_model)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.huggingface_model)
        logger.info("Loaded model from Hugging Face Hub")

        self.setup_bot_events()

    def setup_bot_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f'Logged in as {self.bot.user}')
            channel = self.bot.get_channel(self.channel_id)
            if channel:
                logger.info(f"Sending greeting message to channel {self.channel_id}")
                await channel.send("Hello! I am scibot - I can fact check statements for you!")
            else:
                logger.warning(f"Channel with ID {self.channel_id} not found.")

        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return
            logger.info(f"Received message from {message.author}: {message.content}")
            if isinstance(message.channel, nextcord.DMChannel) or isinstance(message.channel, nextcord.abc.GuildChannel):
                await self.process_message(message)

    async def process_message(self, message):
        user_id = message.author.id
        message_content = message.content
        channel_id = message.channel.id
        timestamp = message.created_at.isoformat()

        logger.info(f"Processing message: {message_content} from user: {user_id}")

        # Sending message to Kafka
        await self.producer.send(f'discord_history_{user_id}', {
            'type': 'user_message',
            'content': message_content,
            'user_id': user_id,
            'channel_id': channel_id,
            'timestamp': timestamp
        })
        logger.info(f"Message sent to Kafka topic for user {user_id}")

        # Generate a response
        response = await self.generate_response(message_content)
        await message.channel.send(response)
        logger.info(f"Generated response: {response}")

        # Storing the response in Kafka
        await self.producer.send(f'discord_history_{user_id}', {
            'type': 'system_response',
            'content': response,
            'user_id': user_id,
            'channel_id': channel_id,
            'timestamp': timestamp
        })
        logger.info("Response stored in Kafka")

    async def generate_response(self, user_input):
        # Tokenize input text
        inputs = self.tokenizer(user_input, return_tensors="pt", padding=True, truncation=True)

        # Perform inference using the loaded model
        with torch.no_grad():
            outputs = self.model(**inputs)

        #Get the predicted class probabilities
        probabilities = torch.softmax(outputs.logits, dim=-1).tolist()[0]

        # Define the class labels
        class_labels = ["False", "True"]

        # Get the predicted class index
        predicted_class_index = probabilities.index(max(probabilities))

        # Check if the predicted class index is within the valid range
        if 0 <= predicted_class_index < len(class_labels):
            predicted_class = class_labels[predicted_class_index]
        else:
            predicted_class = "Unknown"

        # Format the response
        response = f"Your input: {user_input}\n" \
            f"True or False: {predicted_class}\n"

        return response

    async def start_producer(self, retries=5, delay=2):
        for attempt in range(retries):
            try:
                await self.producer.start()
                logger.info("Kafka producer started")
                return
            except kafka_errors.KafkaError as e:
                logger.warning(f"Producer connection attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise

    async def start_consumer(self, retries=5, delay=2):
        for attempt in range(retries):
            try:
                await self.consumer.start()
                logger.info("Kafka consumer started")
                return
            except kafka_errors.KafkaError as e:
                logger.warning(f"Consumer connection attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise

    async def start(self):
        try:
            await self.start_producer()
            await self.start_consumer()
            await self.bot.start(self.discord_token)
        except Exception as e:
            logger.error(f"Failed to start services due to: {e}")
        finally:
            await self.stop()

    async def stop(self):
        try:
            await self.producer.stop()
            logger.info("Kafka producer stopped")
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")
        except Exception as e:
            logger.error(f"Failed to stop services: {e}")
        try:
            await self.bot.close()
            logger.info("Discord bot stopped")
        except Exception as e:
            logger.error(f"Failed to close Discord bot: {e}")

async def main():
    service = SimpleDiscordKafkaService(DISCORD_TOKEN, CHANNEL_ID)
    await service.start()

if __name__ == "__main__":
    asyncio.run(main())
