from database import engine

try:
    connection = engine.connect()
    print("✅ Database Connected Successfully!")
    connection.close()
except Exception as e:
    print("❌ Database Connection Failed")
    print(e)