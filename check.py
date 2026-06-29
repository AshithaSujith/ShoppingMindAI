import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("AIzaSyB8k3lwmI3HaHJ9r2FXTb6ge4sPnjC6Ga8"))

for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"Available Model: {m.name}")