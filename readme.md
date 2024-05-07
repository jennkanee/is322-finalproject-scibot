# Discord Kafka Chatbot

## Overview
This project implements a simple Discord chatbot integrated with Kafka for message exchange and a Hugging Face transformer model for text classification. The bot can fact-check statements provided by users on Discord channels.

## Features
- Responds to user messages with fact-checking results.
- Utilizes Kafka for message storage and retrieval.
- Uses a fine-tuned Hugging Face transformer model for text classification.

## Installation
1. Clone this repository.
2. Ensure you have Docker installed on your system.
3. Set up your environment variables by creating a `.env` file in the project root with the following variables:

    DISCORD_TOKEN=<your_discord_token>
    KAFKA_BROKER=<your_kafka_broker>
    CHANNEL_ID=<your_discord_channel_id>
    HUGGINGFACE_MODEL=<your_huggingface_model>

4. Run the project using Docker:

    docker compose up --build

## Usage
Once the bot is running, it will automatically join the specified Discord channel and respond to user messages with fact-checking results.



