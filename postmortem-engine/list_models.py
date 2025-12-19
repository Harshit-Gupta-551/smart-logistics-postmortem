import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("GEMINI_API_KEY not set in .env")
    raise SystemExit

genai.configure(api_key=api_key)

print("Available models:")
for m in genai.list_models():
    # m.name will look like "models/gemini-1.5-flash" etc.
    print(m.name, "=>", m.supported_generation_methods)