# mock_parser.py

def get_intent_mock(user_query):
    # This function simulates Gemini's JSON response
    query = user_query.lower()
    
    if "tomato" in query:
        return {"status": "ready", "data": {"product": "Tomato", "category": "Grocery", "attributes": {"weight": "1kg"}}}
    
    elif "iphone" in query:
        # Simulate a missing detail (storage)
        return {
            "status": "clarification", 
            "question": "Which storage variant do you want: 128GB, 256GB, or 512GB?",
            "missing_attributes": ["storage"]
        }
    
    else:
        return {"status": "reject", "reason": "Not shopping related"}