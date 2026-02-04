import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

UserName_DATEX = os.getenv("brukernavn")
Password_DATEX = os.getenv("passord")