from google import genai

client = genai.Client(api_key="AIzaSyB8k3lwmI3HaHJ9r2FXTb6ge4sPnjC6Ga8")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Hello"
)

print(response.text)