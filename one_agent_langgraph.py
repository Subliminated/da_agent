from langgraph.graph import StateGraph, END
#from lite_llm import completion
from tools import agent_class, rag_func
import os

# Configure LiteLLM to use Ollama
#os.environ["LITELLM_MODEL"] = "ollama/openchat"  # or "ollama/phi3"
#os.environ["LITELLM_API_BASE"] = "http://localhost:11434"
#os.environ["LITELLM_API_KEY"] = "ollama"  # doesn't matter for Ollama

# Load vectorstore and retriever
vectorstore, retriever = rag_func.load_vectorstore(f"./swe_vector_db")

# === Define LangGraph Nodes ===

SYS_PROMPT_HEADER = """You are a strategic workforce expert assisting Banking executives conduct workforce modelling. Conduct yourself professionally. 
Your objective is to gather specific requirement and assist users with thinking to produce a forecast of future headcount

Your current goal is: """

SCOPE_QUESTIONS = [
    {
        "key": "business_units",
        "system": "You are helping the user identify scope for workforce planning forecasting. Ask questions clearly and focus on one question at a time. Outcome: Gather clear requirements for forecasting",
        "prompt": "Ask questions like: What are the major business units you are interested in forecasting? (e.g. Retail Banking, Wealth Management)"
    },
    {
        "key": "job_families",
        "system": "You are helping the user identify scope for workforce planning forecasting. Ask questions clearly and focus on one question at a time. Outcome: Gather clear requirements for forecasting",
        "prompt": "Ask questions like: What job families or key roles make up your workforce? (e.g. Engineering, Operations, Customer Service)"
    }
]

ASSUMPTION_QUESTIONS = [
    {
        "key": "attrition_rate",
        "system": "You're collecting assumptions about attrition. Outcome: Time-based levers that feed into forecast models.",
        "prompt": "What is your expected annual attrition rate between now and 2030? (e.g. 10%)"
    },
    {
        "key": "growth_rate",
        "system": "You're collecting assumptions about business growth. Outcome: Time-based levers that feed into forecast models.",
        "prompt": "What is your projected annual growth rate for your business? (e.g. 5%)"
    },
    {
        "key": "hiring_plan",
        "system": "You're collecting assumptions about hiring growth. Outcome: Time-based levers that feed into forecast models.",
        "prompt": "What is your hiring plan to support this growth? (e.g. number of hires, job families)"
    },
    {
        "key": "automation_impact",
        "system": "You're collecting assumptions about automation. Outcome: Time-based levers that feed into forecast models.",
        "prompt": "How will automation or AI change your workforce? Will it eliminate or support any job families?"
    }
]
#######
def ask_and_validate(state, key, system, prompt):
    # Get Rag context from vectorstore for the system
    rag_context = ""
    if retriever:
        response = rag_func.rag_retrieval(SYS_PROMPT_HEADER + system, retriever)  # Ensure retriever is initialized
        if response:
            rag_context = "\n\nHere is some Context:\n" + response

    # Incorporate memory for the agent - only for the current phase
    agent = agent_class.LiteLLM(system_prompt=SYS_PROMPT_HEADER + system + rag_context)

    #Normal Mode: Agent asks a question -> waits for user input
    #response = agent_class.generate_response_stateless(prompt, sys_prompt=SYS_PROMPT_HEADER+system) # without memory
    response = agent.generate_response(prompt)
    print(f"\n[Orion 🧠]:", response)
    user_input = input("\n[You 😎]: ").strip()
        
    #Good response guardrail: Ask a question, ask for clarification
    while True:
        if any(i in user_input.lower() for i in ["skip", "n/a", "continue", "next"]):
            print("[Orion 🔄]: Skipping this question.")
            return state
        
        # Clarification Mode: User input is a question, re-ask the original question
        if "?" in user_input:
            # Add RAG
            rag_context = rag_func.rag_retrieval(user_input, retriever)
            clarification_prompt = f"""You asked the user: "{prompt}"
            They responded with a question: "{user_input}"
            Please answer their question as a helpful assistant and then re-ask the original question.

            Here is some context to help answer their question: {rag_context}
            """
            clarification = agent.generate_response(clarification_prompt)
            print(f"\n[Orion ℹ️ Clarification]: {clarification}")
            user_input = input("\n[You 😎]: ").strip()
            continue  # Re-ask the original question
            
        # Evaluation module
        #response = agent_class.generate_response_stateless(prompt, sys_prompt=SYS_PROMPT_HEADER+system)
        response = agent.generate_response(prompt)
        critique_prompt = f"""You asked: "{prompt}"
        The user replied: "{user_input}"

        Has the user clearly answered the question?

        If YES, say only: YES
        If not, say: NO and then follow up politely with a better question or clarification (Assume you are responding directly)."
        """
        critique = agent_class.generate_response_stateless(critique_prompt, sys_prompt=SYS_PROMPT_HEADER+"Evaluate user response")
        
        
        if critique.strip().lower().startswith("yes"):
            print(f"\nUSER RESPONSE EVALUATION: YES")
            state[key] = user_input
            return state
        else:
            print(f"\nUSER RESPONSE EVALUATION: NO\n")
            follow_up = critique.split("NO", 1)[-1].strip()
            print(f"\n[Orion 🤔]:", follow_up)
            user_input = input("\n[You 😎]: ").strip()

######

def intro_node(state):
    system = "You are Orion, an assistant helping HR leaders plan for the 2030 workforce. Be welcoming and clear."
    user = "Introduce yourself and ask if they’d like to begin building a workforce forecast for 2030. Remind them that they can skip a question by typing 'skip' or 'n/a' or exit the conversation by typing 'exit'."
    print("\n[Orion 👋]: ",agent_class.generate_response_stateless(user,sys_prompt=system))
    response = input("You: ").strip().lower()
    return {"next": "scope"} if "y" in response else {"next": END}

def scope_node(state):
    idx = state.get("__scope_index", 0)
    if idx >= len(SCOPE_QUESTIONS):
        return {"next": "assumptions_loop", "state": state}

    q = SCOPE_QUESTIONS[idx]
    state = ask_and_validate(state, q["key"], q["system"], q["prompt"])
    state["__scope_index"] = idx + 1
    return {"next": "scope", "state": state}

def assumptions_node(state):
    idx = state.get("__assumption_index", 0)
    if idx >= len(ASSUMPTION_QUESTIONS):
        return {"next": "risks", "state": state}

    q = ASSUMPTION_QUESTIONS[idx]
    state = ask_and_validate(state, q["key"], q["system"], q["prompt"])
    state["__assumption_index"] = idx + 1
    return {"next": "assumptions", "state": state}

def risks_node(state):
    risks = ask_and_validate(
        state,
        key="risks",
        system="You're identifying workforce risks. Outcome: Branching scenarios or confidence intervals in forecasts.",
        prompt="What are your biggest talent risks between now and 2030? For example, Policy shifts, technology changes, economic downturns, labor market risk etc. How might these impact your workforce planning?"
    )
    state["risks"] = risks
    return {"next": "summary", "state": state}

def summary_node(state):
    system = "You are summarizing the user's workforce planning inputs clearly and concisely."
    user = f"Summarize these points:\n{state}\nPresent it as a 3-point executive summary."
    #summary = llm_response(system, user)
    summary = agent_class.generate_response_stateless(user,sys_prompt=system)
    print("\n[Orion 📝]:", summary)

    print("\nWould you like to:\n1. Proceed to modeling\n2. Make edits\n3. Exit")
    next_action = input("You (model/edit/exit): ").strip().lower()
    if "edit" in next_action:
        return {"next": "scope", "state": state}
    elif "model" in next_action:
        print("\n[Orion 🚀]: Awesome! I’ll pass this to the forecasting engine next.")
        return {"next": END, "state": state}
    else:
        return {"next": END, "state": state}
    
# === LangGraph Construction ===
state_schema = dict  # or use a custom TypedDict if you want type safety

builder = StateGraph(state_schema)
builder.add_node("intro", intro_node)
builder.add_node("scope", scope_node)
builder.add_node("assumptions", assumptions_node)
builder.add_node("risks", risks_node)
builder.add_node("summary", summary_node)

builder.set_entry_point("intro")
builder.add_edge("intro", "scope")
builder.add_edge("scope", "scope")
builder.add_edge("scope", "assumptions")
builder.add_edge("assumptions", "assumptions")
builder.add_edge("assumptions", "risks")
builder.add_edge("risks", "summary")
builder.add_edge("summary", END)

graph = builder.compile()

# === Run the Graph ===

print("\n=== Workforce Planning CLI ===")
state = {}
for event in graph.stream(state):
    if isinstance(event, dict) and "state" in event:
        state.update(event["state"])
