import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_news(headline):
    
    prompt = f"""
    You are a professional stock market analyst. Analyze the following headline and provide a structured JSON response.
    
    Headline: "{headline}"
    
    Instructions:
    1. Identify the 'company' name. If no specific company, write 'Market'.
    2. Provide a 'panic_score' from 0 to 100 (where 100 is a total crash/black swan).
    3. Determine the 'impact': "NEGATIVE", "POSITIVE", or "NEUTRAL".
    4. Recommendation: "SELL" (if score > 75), "BUY" (if score < 20), or "HOLD".
    5. Give a short 1-line 'reason'.

    Return ONLY a valid JSON object.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile", # Sabse tez aur smart model
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"AI Error: {e}")
        return None

if __name__ == "__main__":
    test_news = "Hindenburg report claims massive financial fraud in Adani Group"
    print(f"Testing AI with: {test_news}")
    result = analyze_news(test_news)
    print(json.dumps(result, indent=4))