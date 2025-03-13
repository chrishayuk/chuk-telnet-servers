#!/usr/bin/env python3
# src/servers/guess_who_server.py
"""
Guess Who Telnet Server
A telnet server that hosts a text-based version of the Guess Who game
"""
import asyncio
import logging
import os
import sys
import random
from typing import List, Dict, Any

# imports
from telnet_server import TelnetServer, TelnetProtocolHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# setup the loggers
logger = logging.getLogger('guess-who-telnet-server')

# Define character database
CHARACTERS = [
    {"name": "Alex", "gender": "male", "hair_color": "black", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Alfred", "gender": "male", "hair_color": "red", "hair_type": "bald", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Anita", "gender": "female", "hair_color": "blonde", "hair_type": "long", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Anne", "gender": "female", "hair_color": "black", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Bernard", "gender": "male", "hair_color": "brown", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": True},
    {"name": "Bill", "gender": "male", "hair_color": "red", "hair_type": "bald", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Charles", "gender": "male", "hair_color": "blonde", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Claire", "gender": "female", "hair_color": "red", "hair_type": "short", "glasses": True, "facial_hair": False, "hat": False},
    {"name": "David", "gender": "male", "hair_color": "blonde", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Eric", "gender": "male", "hair_color": "blonde", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": True},
    {"name": "Frans", "gender": "male", "hair_color": "red", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "George", "gender": "male", "hair_color": "white", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": True},
    {"name": "Herman", "gender": "male", "hair_color": "red", "hair_type": "bald", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Joe", "gender": "male", "hair_color": "blonde", "hair_type": "short", "glasses": True, "facial_hair": False, "hat": False},
    {"name": "Maria", "gender": "female", "hair_color": "brown", "hair_type": "long", "glasses": False, "facial_hair": False, "hat": True},
    {"name": "Max", "gender": "male", "hair_color": "black", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Paul", "gender": "male", "hair_color": "white", "hair_type": "short", "glasses": True, "facial_hair": False, "hat": False},
    {"name": "Peter", "gender": "male", "hair_color": "white", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Philip", "gender": "male", "hair_color": "black", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Richard", "gender": "male", "hair_color": "brown", "hair_type": "bald", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Robert", "gender": "male", "hair_color": "brown", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Sam", "gender": "male", "hair_color": "white", "hair_type": "bald", "glasses": True, "facial_hair": False, "hat": False},
    {"name": "Susan", "gender": "female", "hair_color": "white", "hair_type": "long", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Tom", "gender": "male", "hair_color": "black", "hair_type": "bald", "glasses": True, "facial_hair": False, "hat": False}
]

VALID_QUESTIONS = [
    "is it a man?",
    "is it a woman?",
    "do they have glasses?",
    "do they have a hat?",
    "do they have facial hair?",
    "do they have black hair?",
    "do they have blonde hair?",
    "do they have brown hair?",
    "do they have red hair?",
    "do they have white hair?",
    "are they bald?",
    "do they have short hair?",
    "do they have long hair?",
]

class GuessWhoTelnetHandler(TelnetProtocolHandler):
    """Handler for Guess Who telnet sessions"""

    async def initialize(self) -> None:
        """Initialize the game state"""
        self.game_started = False
        self.remaining_characters = CHARACTERS.copy()
        self.secret_character = None
        self.questions_asked = 0
        self.max_questions = 10

    async def show_help(self) -> None:
        """Display help information"""
        await self.send_line("\nGUESS WHO - HELP")
        await self.send_line("----------------")
        await self.send_line("COMMANDS (type exactly as shown):")
        await self.send_line("  start         - Start a new game")
        await self.send_line("  list          - Show remaining possible characters")
        await self.send_line("  guess [name]  - Make a final guess (e.g., 'guess alex')")
        await self.send_line("  help          - Show this help")
        await self.send_line("  quit          - Exit the game")
        await self.send_line("\nQUESTIONS (type exactly as shown):")
        for question in VALID_QUESTIONS:
            await self.send_line(f"  {question}")
        await self.send_line("\nYou have 10 questions before you must guess!")
        await self.send_line("----------------\n")

    async def display_characters(self) -> None:
        """Display the list of remaining characters"""
        if not self.remaining_characters:
            await self.send_line("No characters remain! Something went wrong.")
            return
            
        await self.send_line("\nREMAINING CHARACTERS:")
        await self.send_line("---------------------")
        
        # Calculate the maximum name length for alignment
        max_name_length = max(len(character["name"]) for character in self.remaining_characters)
        
        for character in sorted(self.remaining_characters, key=lambda x: x["name"]):
            name = character["name"].ljust(max_name_length)
            gender = character["gender"]
            hair = f"{character['hair_color']} {character['hair_type']} hair"
            if character["hair_type"] == "bald":
                hair = "bald"
                
            features = []
            if character["glasses"]:
                features.append("glasses")
            if character["facial_hair"]:
                features.append("facial hair")
            if character["hat"]:
                features.append("hat")
                
            features_str = ", ".join(features) if features else "no accessories"
            
            await self.send_line(f"{name} - {gender}, {hair}, {features_str}")
        
        await self.send_line(f"\nRemaining characters: {len(self.remaining_characters)}")
        await self.send_line(f"Questions asked: {self.questions_asked}/{self.max_questions}")
        await self.send_line("---------------------\n")

    async def start_game(self) -> None:
        """Start a new game"""
        # Reset the game state
        self.remaining_characters = CHARACTERS.copy()
        self.secret_character = random.choice(CHARACTERS)
        self.questions_asked = 0
        self.game_started = True
        
        logger.info(f"Started new game for {self.addr}. Secret character: {self.secret_character['name']}")
        
        await self.send_line("\n" + "=" * 50)
        await self.send_line("WELCOME TO GUESS WHO!")
        await self.send_line("=" * 50)
        await self.send_line("I've selected a secret character. Can you guess who it is?")
        await self.send_line(f"You can ask up to {self.max_questions} yes/no questions.")
        await self.send_line("\nAVAILABLE COMMANDS:")
        await self.send_line("  list          - Show all possible characters")
        await self.send_line("  help          - Show all commands & questions")
        await self.send_line("  guess [name]  - Make your final guess (e.g., 'guess alex')")
        await self.send_line("\nEXAMPLE QUESTIONS:")
        await self.send_line("  is it a man?")
        await self.send_line("  do they have glasses?")
        await self.send_line("  do they have red hair?")
        await self.send_line("  (type 'help' to see all available questions)")
        await self.send_line("=" * 50 + "\n")
        
        await self.display_characters()

    async def handle_question(self, question: str) -> None:
        """Handle a yes/no question from the player"""
        # Clean up the question for processing
        question = question.lower().strip()
        
        # Only process if this is a valid question
        if question not in VALID_QUESTIONS:
            await self.send_line("That doesn't seem to be a valid question. Type 'help' to see example questions.")
            return
            
        # Increment question counter
        self.questions_asked += 1
        logger.info(f"Client {self.addr} asked: {question}")
        
        # Process different types of questions
        answer = False  # Default answer
        elimination_key = None  # Which key to use for elimination
        elimination_value = None  # What value to eliminate on
        
        # Gender questions
        if question == "is it a man?":
            answer = self.secret_character["gender"] == "male"
            elimination_key = "gender"
            elimination_value = "male" if not answer else "female"
        elif question == "is it a woman?":
            answer = self.secret_character["gender"] == "female"
            elimination_key = "gender"
            elimination_value = "female" if not answer else "male"
        
        # Accessories questions
        elif question == "do they have glasses?":
            answer = self.secret_character["glasses"]
            elimination_key = "glasses"
            elimination_value = True if not answer else False
        elif question == "do they have a hat?":
            answer = self.secret_character["hat"]
            elimination_key = "hat"
            elimination_value = True if not answer else False
        elif question == "do they have facial hair?":
            answer = self.secret_character["facial_hair"]
            elimination_key = "facial_hair"
            elimination_value = True if not answer else False
        
        # Hair color questions
        elif "hair" in question:
            # Hair type questions
            if "bald" in question:
                answer = self.secret_character["hair_type"] == "bald"
                elimination_key = "hair_type"
                elimination_value = "bald" if not answer else None
            elif "short hair" in question:
                answer = self.secret_character["hair_type"] == "short"
                elimination_key = "hair_type"
                elimination_value = "short" if not answer else None
            elif "long hair" in question:
                answer = self.secret_character["hair_type"] == "long"
                elimination_key = "hair_type"
                elimination_value = "long" if not answer else None
            # Hair color questions
            elif "black hair" in question:
                answer = self.secret_character["hair_color"] == "black"
                elimination_key = "hair_color"
                elimination_value = "black" if not answer else None
            elif "blonde hair" in question:
                answer = self.secret_character["hair_color"] == "blonde"
                elimination_key = "hair_color"
                elimination_value = "blonde" if not answer else None
            elif "brown hair" in question:
                answer = self.secret_character["hair_color"] == "brown"
                elimination_key = "hair_color"
                elimination_value = "brown" if not answer else None
            elif "red hair" in question:
                answer = self.secret_character["hair_color"] == "red"
                elimination_key = "hair_color"
                elimination_value = "red" if not answer else None
            elif "white hair" in question:
                answer = self.secret_character["hair_color"] == "white"
                elimination_key = "hair_color"
                elimination_value = "white" if not answer else None
        
        # Send the answer to the player
        await self.send_line(f"Answer: {'Yes' if answer else 'No'}")
        
        # Eliminate characters based on the answer
        if elimination_key and elimination_value is not None:
            # If answer is True, then we keep characters that match the attribute
            # If answer is False, then we eliminate characters that match the attribute
            if elimination_key in ["hair_type", "hair_color"] and elimination_value is None:
                # Special handling for hair questions where we need to eliminate multiple possibilities
                if answer:
                    # Keep only characters with matching attribute
                    self.remaining_characters = [c for c in self.remaining_characters 
                                                if c[elimination_key] == self.secret_character[elimination_key]]
                else:
                    # Remove characters with matching attribute
                    self.remaining_characters = [c for c in self.remaining_characters 
                                                if c[elimination_key] != self.secret_character[elimination_key]]
            else:
                # Standard elimination
                self.remaining_characters = [c for c in self.remaining_characters 
                                            if (c[elimination_key] == elimination_value) == answer]
        
        # Check if only one character remains
        if len(self.remaining_characters) == 1:
            await self.send_line("\nI think you know who it is now! Type 'guess [name]' to make your final guess.")
        
        # Check if max questions reached
        if self.questions_asked >= self.max_questions:
            await self.send_line("\nYou've used all your questions! Make your final guess with 'guess [name]'.")
        
        await self.display_characters()

    async def make_guess(self, guess: str) -> None:
        """Process the player's final guess"""
        # Extract the name from the guess command
        name = guess.strip().lower()
        
        # Check if the guess is correct
        correct = name == self.secret_character["name"].lower()
        
        if correct:
            await self.send_line("\n🎉 CONGRATULATIONS! 🎉")
            await self.send_line(f"You correctly guessed that the character was {self.secret_character['name']}!")
            await self.send_line(f"It took you {self.questions_asked} questions.")
        else:
            await self.send_line("\n❌ Sorry, that's incorrect! ❌")
            await self.send_line(f"The character was {self.secret_character['name']}.")
        
        await self.send_line("\nType 'start' to play again or 'quit' to exit.")
        self.game_started = False

    async def handle_client(self) -> None:
        """Handle a client connection"""
        logger.info(f"New connection from {self.addr}")
        
        # Initialize game state
        await self.initialize()
        
        # Send welcome message
        await self.send_line("=============================================")
        await self.send_line("      WELCOME TO THE GUESS WHO SERVER!      ")
        await self.send_line("=============================================")
        await self.send_line("COMMANDS (type exactly as shown):")
        await self.send_line("  start         - Begin a new game")
        await self.send_line("  help          - View all commands & questions")
        await self.send_line("  quit          - Disconnect")
        await self.send_line("=============================================")
        
        await self.send_line("\n> ")
        
        # Main loop
        while self.running:
            try:
                # Read a line from the client
                message = await self.read_line(timeout=300)
                
                # Handle disconnection
                if message is None:
                    logger.info(f"Client {self.addr} closed connection")
                    break
                
                # Log the message
                logger.info(f"Received from {self.addr}: {message}")
                message = message.strip().lower()
                
                # Process commands
                if message == 'quit':
                    await self.send_line("Thanks for playing Guess Who! Goodbye!")
                    break
                    
                elif message == 'help':
                    await self.show_help()
                    
                elif message == 'start':
                    await self.start_game()
                    
                elif message == 'list' and self.game_started:
                    await self.display_characters()
                    
                elif message.startswith('guess ') and self.game_started:
                    await self.make_guess(message[6:])
                    
                elif self.game_started and message in VALID_QUESTIONS:
                    await self.handle_question(message)
                    
                else:
                    if not self.game_started:
                        await self.send_line("Game not started. Type 'start' to begin or 'help' for instructions.")
                    else:
                        await self.send_line("I don't understand that command or question. Type 'help' for instructions.")
                
                # Prompt for the next message
                await self.send_line("\n> ")
                
            except asyncio.TimeoutError:
                # Check if we're still running
                if not self.running:
                    break
            
            except Exception as e:
                logger.error(f"Error in game loop for {self.addr}: {e}")
                if "Connection reset" in str(e) or "Broken pipe" in str(e):
                    break
                else:
                    await asyncio.sleep(1)


class GuessWhoTelnetServer(TelnetServer):
    """Guess Who telnet server"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023):
        """Initialize the server"""
        super().__init__(host, port, GuessWhoTelnetHandler)


def main():
    """Main function"""
    try:
        # Create and start the server
        server = GuessWhoTelnetServer()
        logger.info(f"Starting Guess Who Telnet Server on port {server.port}")
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    finally:
        logger.info("Server process exiting.")


if __name__ == "__main__":
    # call main
    main()