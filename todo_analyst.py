from app.core.orchestrator import Architect
from app.core.logger import setup_logger

logger = setup_logger("CLI")

def run_architect():
    """Main interactive loop for the Architect CLI."""
    architect = Architect()
    
    # 1. Fetch Initial State
    state = architect.fetch_state()
    
    # 2. Initialize Chat (implicit in Orchestrator logic or explicit call)
    # The orchestrator handles init on first analyze if not done, 
    # but we want to prep the LLM with the context first if we pass it 
    # or just rely on analyze doing it.
    
    logger.info("The Architect is ready.")
    print("Type your request (or 'exit' to quit):")
    
    while True:
        user_input = input("\n> ")
        if user_input.lower() in ['exit', 'quit']:
            break
            
        print("🤖 Architect is thinking...")
        try:
            # 3. Analyze
            result = architect.analyze(state, user_input)
            
            print(f"\n🧠 Analysis: {result['thought']}")
            
            actions = result['actions']
            if actions:
                print(f"\n⚠️ Proposed {len(actions)} actions:")
                for i, action in enumerate(actions, 1):
                    # Robust printing handling optional fields
                    details = action.get('content') or action.get('name') or action.get('id') or str(action)
                    print(f"{i}. {action['type']}: {details}")
                    
                confirm = input("\nExecute these changes? (y/n): ")
                if confirm.lower() == 'y':
                    # 4. Execute
                    results = architect.execute(actions)
                    
                    # Print results if needed, or just summary
                    # for res in results: logger.info(res['message'])
                    
                    # 5. Refresh State
                    logger.info("Refreshing state from Todoist...")
                    state = architect.fetch_state()
                    
                    # 6. Sync State
                    architect.sync_state(state)
                    
                    print("\n✨ Done! Ready for next command.")
                else:
                    print("Cancelled.")
            else:
                print("\nNo actions proposed.")
                
        except Exception as e:
            logger.error(f"Error in loop: {e}")

if __name__ == "__main__":
    run_architect()
