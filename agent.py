import time
from fetcher import get_all_headlines  # Phase 1 se news mangwana
from brain import analyze_news         # Phase 2 se dimaag lagwana

def run_news_pulse_agent():
    print("\n" + "="*50)
    print("🤖 NEWSPULSE AI: AUTONOMOUS AGENT IS LIVE")
    print("="*50)

    # 1. Internet se saari headlines uthao
    print("[LOG] Fetching latest headlines from X, NewsAPI, and Finnhub...")
    headlines = get_all_headlines()
    
    if not headlines:
        print("[!] No headlines found. Check your Internet/APIs.")
        return

    print(f"[LOG] Successfully fetched {len(headlines)} headlines. Starting AI Analysis...\n")

    # 2. Har headline ko AI ke paas bhejo analyze karne ke liye
    for i, news in enumerate(headlines, 1):
        print(f"[{i}] Analyzing: {news[:75]}...")
        
        # AI Analysis calling
        analysis = analyze_news(news)
        
        if analysis:
            score = analysis.get('panic_score', 0)
            rec = analysis.get('recommendation', 'HOLD')
            company = analysis.get('company', 'Unknown')
            
            # Console par result dikhao
            print(f"    >>> Result: {company} | Score: {score} | Action: {rec}")

            # 3. Agar Panic Score 80+ hai toh RED ALERT!
            if score >= 80:
                print(f"\n🚨🚨 CRITICAL EVENT DETECTED! 🚨🚨")
                print(f"TARGET: {company}")
                print(f"AI DECISION: IMMEDIATE {rec}")
                print(f"REASON: {analysis.get('reason')}")
                print("-" * 40 + "\n")
        
        # Groq ki free limit na cross ho isliye 1 second ka gap
        time.sleep(1)

if __name__ == "__main__":
    # Ye agent har 10 minute mein scan karega (loop)
    while True:
        run_news_pulse_agent()
        print("\n[INFO] Scan complete. Next scan in 10 minutes...")
        time.sleep(600) # 600 seconds = 10 minutes